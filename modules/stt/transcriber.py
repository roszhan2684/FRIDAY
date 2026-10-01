"""Speech-to-text using mlx-whisper (Metal-accelerated on Apple Silicon).

Falls back to faster-whisper on CPU if mlx is unavailable.
Returns a Transcript with calibrated confidence.
"""
from __future__ import annotations
import hashlib
import io
import logging
import time
from pathlib import Path

import numpy as np

from shared.schemas import Transcript
from shared.constants import (
    WHISPER_MODEL,
    WHISPER_FALLBACK_MODEL,
    AUDIO_SAMPLE_RATE,
    CONFIDENCE_THRESHOLD,
)

logger = logging.getLogger(__name__)


class Transcriber:
    def __init__(self, model_id: str = WHISPER_MODEL, language: str = "en"):
        self._model_id = model_id
        self._language = language
        self._model = None
        self._backend = None

    def load(self) -> None:
        """Load the STT model. Called once at startup."""
        try:
            import mlx_whisper  # type: ignore
            self._backend = "mlx"
            # Force model into memory now so first real command is instant
            logger.info("STT backend: mlx-whisper (%s) — warming up...", self._model_id)
            _silence = np.zeros(16000, dtype=np.float32)
            mlx_whisper.transcribe(_silence, path_or_hf_repo=self._model_id, language="en")
            logger.info("STT model warm")
        except ImportError:
            try:
                from faster_whisper import WhisperModel  # type: ignore
                self._model = WhisperModel(
                    WHISPER_FALLBACK_MODEL,
                    device="cpu",
                    compute_type="int8",
                )
                self._backend = "faster-whisper"
                logger.warning(
                    "mlx-whisper not available — using faster-whisper on CPU. "
                    "Install mlx-whisper for Metal acceleration."
                )
            except ImportError:
                logger.error(
                    "No STT backend available. Install mlx-whisper or faster-whisper."
                )
                self._backend = None

    def transcribe(self, audio_bytes: bytes) -> Transcript:
        """
        Transcribe raw PCM audio bytes (16kHz, int16, mono).
        Returns Transcript with text and confidence score.
        """
        audio_hash = hashlib.sha256(audio_bytes).hexdigest()[:16]
        duration = len(audio_bytes) / (AUDIO_SAMPLE_RATE * 2)  # int16 = 2 bytes

        audio_np = np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0

        if self._backend == "mlx":
            return self._transcribe_mlx(audio_np, audio_hash, duration)
        elif self._backend == "faster-whisper":
            return self._transcribe_faster_whisper(audio_np, audio_hash, duration)
        else:
            return Transcript(
                text="",
                confidence=0.0,
                audio_hash=audio_hash,
                duration_seconds=duration,
                model="none",
            )

    def _transcribe_mlx(self, audio_np: np.ndarray, audio_hash: str, duration: float) -> Transcript:
        import mlx_whisper  # type: ignore

        result = mlx_whisper.transcribe(
            audio_np,
            path_or_hf_repo=self._model_id,
            language=self._language,
            word_timestamps=False,
        )

        text = result.get("text", "").strip()
        confidence = self._estimate_confidence(result, duration)

        return Transcript(
            text=text,
            confidence=confidence,
            audio_hash=audio_hash,
            duration_seconds=duration,
            model=self._model_id,
        )

    def _transcribe_faster_whisper(
        self, audio_np: np.ndarray, audio_hash: str, duration: float
    ) -> Transcript:
        segments, info = self._model.transcribe(
            audio_np,
            language=self._language,
            beam_size=5,
        )
        segments = list(segments)
        text = " ".join(s.text.strip() for s in segments)
        avg_logprob = (
            sum(s.avg_logprob for s in segments) / len(segments) if segments else -1.0
        )
        confidence = self._logprob_to_confidence(avg_logprob)

        return Transcript(
            text=text,
            confidence=confidence,
            audio_hash=audio_hash,
            duration_seconds=duration,
            model=WHISPER_FALLBACK_MODEL,
        )

    def _estimate_confidence(self, result: dict, duration: float) -> float:
        """
        Derive a 0–1 confidence score from whisper output.
        mlx-whisper doesn't expose per-segment logprobs directly,
        so we use a heuristic: no_speech_prob + text length reasonableness.
        """
        segments = result.get("segments", [])
        if not segments:
            return 0.1

        no_speech = segments[0].get("no_speech_prob", 0.0)
        text = result.get("text", "")
        word_count = len(text.split())

        # Penalise if text is implausibly short or long for the duration
        expected_words = duration * 2.5  # average speaking rate ~2.5 wps
        length_ratio = word_count / max(expected_words, 1)
        length_penalty = 1.0 - abs(1.0 - min(length_ratio, 2.0)) * 0.2

        base = max(0.0, 1.0 - no_speech)
        return round(min(1.0, base * length_penalty), 3)

    @staticmethod
    def _logprob_to_confidence(avg_logprob: float) -> float:
        """Map average log-probability to a 0–1 confidence score."""
        import math
        # avg_logprob is typically in range [-1, 0]; -1 is bad, 0 is perfect
        clamped = max(-2.0, min(0.0, avg_logprob))
        return round(math.exp(clamped), 3)
