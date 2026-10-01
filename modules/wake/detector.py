"""Wake word detection — VAD + embedding template matching.

Architecture (no base model needed):
  1. RMS energy detects speech onset (>500 = speaking)
  2. Capture audio until silence (~600ms quiet = done)
  3. Compute openwakeword embeddings of captured audio
  4. Cosine similarity against stored "hey friday" template
  5. If similarity >= threshold (0.957) → wake callback

Training:
  30 positive "hey friday" recordings → similarity 0.992–0.997
  20 negative (random speech) recordings → similarity 0.872–0.922
  Threshold 0.957 gives clean separation with no overlap.

Retrain: bash scripts/train_wakeword.sh
"""
from __future__ import annotations
import logging
import os
import queue
import threading
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

RATE        = 16000
CHUNK       = 1280            # 80ms at 16kHz
TEMPLATE    = Path.home() / ".friday/models/hey_friday_template.npy"
SIMILARITY_THRESHOLD = 0.957  # separates hey_friday (>0.99) from other speech (<0.92)

# Speech activity detection
RMS_SPEECH  = 500    # RMS above this → speech started
RMS_SILENCE = 200    # RMS below this → silence
SILENCE_CHUNKS_END  = 8    # ~640ms of silence ends the utterance
MIN_SPEECH_CHUNKS   = 4    # ~320ms minimum to count as a word
MAX_SPEECH_CHUNKS   = 50   # ~4 seconds hard cap


class WakeWordDetector:
    def __init__(self, model_path: str | None = None, threshold: float | None = None):
        self._model_path = model_path
        self._threshold  = threshold if threshold is not None else SIMILARITY_THRESHOLD
        self._template   = None     # (1536,) normalised mean embedding of training samples
        self._oww        = None     # openwakeword Model for computing embeddings
        self._running    = False
        self._thread: threading.Thread | None = None
        self._on_wake_callback = None
        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=200)

    # ─── Loading ──────────────────────────────────────────────────────────────

    def _load(self) -> None:
        """Load embedding model + template. Falls back gracefully if missing."""
        try:
            from openwakeword.model import Model  # type: ignore
            self._oww = Model(wakeword_models=["alexa"], inference_framework="onnx")
            logger.info("Embedding model loaded (alexa)")
        except Exception as exc:
            logger.warning("openwakeword load failed: %s", exc)
            self._oww = None

        if TEMPLATE.exists():
            self._template = np.load(str(TEMPLATE)).astype(np.float32)
            logger.info(
                "Hey-friday template loaded (similarity threshold=%.3f)",
                self._threshold,
            )
        else:
            logger.warning(
                "No hey-friday template found at %s. "
                "Run scripts/train_wakeword.sh to train your wake word.",
                TEMPLATE,
            )
            self._template = None

    # ─── Lifecycle ────────────────────────────────────────────────────────────

    def set_callback(self, callback) -> None:
        self._on_wake_callback = callback

    def start(self) -> None:
        self._load()
        self._running = True
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="wake-detector"
        )
        self._thread.start()
        logger.info("Wake word detector started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    # ─── Audio loop ───────────────────────────────────────────────────────────

    def _run_loop(self) -> None:
        try:
            import sounddevice as sd  # type: ignore
        except ImportError:
            logger.error("sounddevice not installed — microphone unavailable.")
            return

        def audio_callback(indata: np.ndarray, frames: int, time, status) -> None:
            if status:
                logger.debug("sounddevice status: %s", status)
            self._audio_queue.put(indata[:, 0].copy())

        try:
            stream = sd.InputStream(
                samplerate=RATE, channels=1, dtype="int16",
                blocksize=CHUNK, callback=audio_callback,
            )
        except Exception as exc:
            logger.error("Could not open microphone: %s", exc)
            return

        logger.info("Microphone open — listening for 'hey friday'")

        # State machine
        in_speech = False
        speech_buf: list[np.ndarray] = []
        silence_count = 0

        with stream:
            while self._running:
                try:
                    chunk = self._audio_queue.get(timeout=0.5)
                except queue.Empty:
                    continue

                rms = float(np.sqrt(np.mean(chunk.astype(np.float32) ** 2)))

                if not in_speech:
                    if rms >= RMS_SPEECH:
                        in_speech = True
                        speech_buf = [chunk]
                        silence_count = 0
                else:
                    speech_buf.append(chunk)

                    if rms < RMS_SILENCE:
                        silence_count += 1
                    else:
                        silence_count = 0

                    ended = (
                        silence_count >= SILENCE_CHUNKS_END
                        or len(speech_buf) >= MAX_SPEECH_CHUNKS
                    )

                    if ended:
                        if len(speech_buf) >= MIN_SPEECH_CHUNKS:
                            audio = np.concatenate(speech_buf)
                            self._check_wake(audio)
                        in_speech = False
                        speech_buf = []
                        silence_count = 0

    # ─── Wake check ───────────────────────────────────────────────────────────

    def _check_wake(self, audio: np.ndarray) -> None:
        """Compute embedding similarity. Fire wake callback if it matches template."""
        if self._template is None or self._oww is None:
            # No template → pass everything through (useful during dev)
            logger.debug("No template — treating all speech as wake word")
            self._fire(audio.tobytes())
            return

        try:
            import tempfile, wave
            from openwakeword.custom_verifier_model import get_reference_clip_features  # type: ignore

            # Write to temp WAV
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp = f.name
            with wave.open(tmp, "wb") as wf:
                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(RATE)
                wf.writeframes(audio.tobytes())

            # Compute embedding
            feats = get_reference_clip_features(tmp, self._oww, "alexa", N=10, threshold=0.0)
            os.unlink(tmp)

            if feats.shape[0] == 0:
                return  # no features extracted (too quiet or too short)

            emb = feats.mean(axis=0).flatten().astype(np.float32)
            norm = np.linalg.norm(emb)
            if norm == 0:
                return
            emb /= norm

            similarity = float(np.dot(emb, self._template))
            logger.debug("Wake similarity: %.4f (threshold=%.3f)", similarity, self._threshold)

            if similarity >= self._threshold:
                logger.info(
                    "Wake word confirmed — similarity=%.4f >= threshold=%.3f",
                    similarity, self._threshold,
                )
                self._fire(audio.tobytes())

        except Exception as exc:
            logger.exception("Wake check error: %s", exc)

    def _fire(self, audio_bytes: bytes) -> None:
        if self._on_wake_callback:
            threading.Thread(
                target=self._on_wake_callback,
                args=(audio_bytes,),
                daemon=True,
            ).start()
