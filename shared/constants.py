"""System-wide constants for FRIDAY."""

RUNTIME_HOST = "127.0.0.1"
RUNTIME_PORT = 7700
RUNTIME_BASE_URL = f"http://{RUNTIME_HOST}:{RUNTIME_PORT}"
RUNTIME_WS_URL = f"ws://{RUNTIME_HOST}:{RUNTIME_PORT}/ws"

CONFIDENCE_THRESHOLD = 0.75          # Below this → prompt for typed correction
WAKE_WORDS = ["hey friday", "friday"]
AUDIO_SAMPLE_RATE = 16000
AUDIO_CHUNK_FRAMES = 1280            # openwakeword expects 80ms chunks at 16kHz
SILENCE_THRESHOLD_SECONDS = 1.5     # Stop capturing after this much silence
MAX_CAPTURE_SECONDS = 15.0           # Hard cap on command capture

FRIDAY_HOME = "~/.friday"
DB_PATH = "~/.friday/friday.db"
MODELS_PATH = "~/.friday/models"
DATASETS_PATH = "~/.friday/datasets"
LOGS_PATH = "~/.friday/logs"

OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_MODEL = "llama3.2:latest"
OLLAMA_TIMEOUT_SECONDS = 45

WHISPER_MODEL = "mlx-community/whisper-medium-mlx"  # Metal-accelerated
WHISPER_FALLBACK_MODEL = "base.en"                  # CPU fallback

TTS_VOICE = "Samantha"      # macOS Neural voice
TTS_RATE = 185              # words per minute

SAFE_TOOLS = frozenset({
    "open_file", "open_app", "open_url", "reveal_in_finder",
    "switch_app", "search_files", "show_history", "respond_only",
    "run_routine", "search_youtube", "lookup_movie", "search_web",
    "run_custom_command", "open_url_chrome_profile",
    "create_reminder", "query_reminders", "snooze_reminder", "complete_reminder",
    "add_shopping_item", "query_shopping_list", "check_shopping_item", "clear_shopping_list",
    "query_schedule", "get_briefing",
    # Phase 6
    "capture_note", "show_notes", "daily_reflection",
    "open_job_sites", "research_company",
})

CONFIRM_TOOLS = frozenset({
    "delete_file", "send_email", "create_routine", "clear_memory",
    "set_preference",
})

BLOCKED_TOOLS: frozenset[str] = frozenset()
