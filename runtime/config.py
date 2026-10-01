"""Runtime configuration loaded from config/friday.yaml + env overrides."""
from __future__ import annotations
import os
from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings
import yaml


class Settings(BaseSettings):
    # Runtime
    host: str = "127.0.0.1"
    port: int = 7700

    # Audio
    sample_rate: int = 16000
    chunk_frames: int = 1280
    silence_threshold_seconds: float = 1.5
    max_capture_seconds: float = 15.0

    # STT
    whisper_model: str = "mlx-community/whisper-medium-mlx"
    whisper_language: str = "en"
    confidence_threshold: float = 0.75

    # LLM
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2:3b"
    ollama_timeout: int = 10

    # TTS
    tts_voice: str = "Samantha"
    tts_rate: int = 185
    murf_voice_id: str = "en-US-judith"
    murf_style: str = "Conversational"
    murf_api_key: str = ""          # Set via FRIDAY_MURF_API_KEY in .env

    # Wake word
    wake_model_path: str = "~/.friday/models/hey_friday.onnx"
    wake_threshold: float = 0.5

    # Features
    learning_enabled: bool = True
    confirm_risky_actions: bool = True
    debug: bool = False

    # Backend sync (Phase 0 cloud)
    backend_url: str = "http://127.0.0.1:7800"   # set to "" to disable sync
    backend_key: str = "friday-dev-key-2025"

    class Config:
        env_prefix = "FRIDAY_"
        env_file = ".env"


def _load_yaml_config() -> dict:
    yaml_path = Path(__file__).parent.parent / "config" / "friday.yaml"
    if yaml_path.exists():
        with open(yaml_path) as f:
            return yaml.safe_load(f) or {}
    return {}


def _build_settings() -> Settings:
    yaml_cfg = _load_yaml_config()
    flat = {}
    for section in yaml_cfg.values():
        if isinstance(section, dict):
            flat.update(section)
    return Settings(**{k: v for k, v in flat.items() if v is not None})


settings: Settings = _build_settings()
