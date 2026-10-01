"""Text-to-speech with Murf.ai as primary backend.

Primary:  Murf.ai API  (high-quality neural voice, streams MP3)
Fallback: macOS `say`  (zero setup, works offline)

API key loaded from MURF_API_KEY env var or config.
"""
from __future__ import annotations
import logging
import os
import subprocess
import tempfile
import threading

import httpx

from shared.constants import TTS_VOICE, TTS_RATE

logger = logging.getLogger(__name__)

MURF_STREAM_URL = "https://global.api.murf.ai/v1/speech/stream"
_speak_lock = threading.Lock()


class Speaker:
    def __init__(
        self,
        voice: str = TTS_VOICE,
        rate: int = TTS_RATE,
        murf_api_key: str | None = None,
        murf_voice_id: str = "en-US-judith",
        murf_style: str = "Conversational",
    ):
        self._voice = voice                    # macOS say voice (fallback)
        self._rate = rate
        self._murf_api_key = murf_api_key or os.environ.get("MURF_API_KEY", "")
        self._murf_voice_id = murf_voice_id
        self._murf_style = murf_style
        self._current_proc: subprocess.Popen | None = None
        self._backend = "murf" if self._murf_api_key else "macos"
        logger.info("TTS backend: %s | voice: %s | style: %s", self._backend, murf_voice_id, murf_style)

    def speak(self, text: str, blocking: bool = False) -> None:
        if not text.strip():
            return

        def _run():
            with _speak_lock:
                if self._murf_api_key:
                    success = self._speak_murf(text)
                    if success:
                        return
                    logger.warning("Murf TTS failed — falling back to macOS say")
                self._speak_macos(text)

        if blocking:
            _run()
        else:
            threading.Thread(target=_run, daemon=True, name="tts-speaker").start()

    def stop(self) -> None:
        if self._current_proc:
            self._current_proc.terminate()

    # ─── Murf ─────────────────────────────────────────────────────────────────

    def _speak_murf(self, text: str) -> bool:
        """Stream audio from Murf.ai, write to temp file, play with afplay."""
        try:
            with httpx.Client(timeout=30.0) as client:
                response = client.post(
                    MURF_STREAM_URL,
                    headers={
                        "api-key": self._murf_api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "voiceId": self._murf_voice_id,
                        "style": self._murf_style,
                        "text": text,
                        "locale": "en-US",
                        "model": "FALCON",
                        "format": "MP3",
                        "sampleRate": 24000,
                        "channelType": "MONO",
                    },
                )

            if response.status_code != 200:
                logger.error("Murf API error %d: %s", response.status_code, response.text[:200])
                return False

            audio_bytes = response.content
            if not audio_bytes:
                logger.error("Murf returned empty audio")
                return False

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                f.write(audio_bytes)
                tmp_path = f.name

            try:
                self._current_proc = subprocess.Popen(
                    ["afplay", tmp_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._current_proc.wait()
            finally:
                self._current_proc = None
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

            return True

        except httpx.TimeoutException:
            logger.error("Murf TTS request timed out")
            return False
        except Exception as exc:
            logger.error("Murf TTS error: %s", exc)
            return False

    # ─── macOS fallback ───────────────────────────────────────────────────────

    def _speak_macos(self, text: str) -> None:
        try:
            self._current_proc = subprocess.Popen(
                ["say", "-v", self._voice, "-r", str(self._rate), text],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._current_proc.wait()
        except Exception as exc:
            logger.error("macOS say error: %s", exc)
        finally:
            self._current_proc = None

    # ─── Config helpers ───────────────────────────────────────────────────────

    def set_murf_voice(self, voice_id: str, style: str | None = None) -> None:
        self._murf_voice_id = voice_id
        if style:
            self._murf_style = style

    def set_murf_api_key(self, key: str) -> None:
        self._murf_api_key = key
        self._backend = "murf" if key else "macos"

    @staticmethod
    def list_macos_voices() -> list[str]:
        try:
            result = subprocess.run(["say", "-v", "?"], capture_output=True, text=True)
            return [line.split()[0] for line in result.stdout.splitlines() if line.strip()]
        except Exception:
            return ["Samantha"]
