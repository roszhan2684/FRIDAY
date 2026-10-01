# FRIDAY

> *"Local-first, voice-first, self-owned macOS personal assistant."*

FRIDAY runs entirely on your Mac. No cloud. No subscriptions. No data leaving your machine.
It listens for your wake word, understands your commands, executes actions on your Mac, and gets smarter every time you use it.

---

## Architecture

```
SwiftUI App (Menu Bar + Overlay)
    ↕ WebSocket / HTTP — localhost:7700
Python Runtime (FastAPI)
    ├── Wake Word  (openwakeword — Metal)
    ├── STT        (mlx-whisper — Metal-accelerated)
    ├── LLM        (Ollama — llama3.2:3b local)
    ├── TTS        (macOS say — Samantha Neural)
    ├── Memory     (SQLite — local)
    └── Automation (mdfind + osascript + open)
```

---

## Requirements

- macOS 13+ on Apple Silicon (M1/M2/M3/M4)
- Python 3.11+
- Xcode 15+ (for the Swift app)
- ~4GB disk space for models

---

## Setup

```bash
# 1. Clone and run setup
git clone <your-repo>
cd friday
bash scripts/setup.sh

# 2. Grant macOS permissions (Terminal):
#    System Settings → Privacy → Microphone → ✓ Terminal
#    System Settings → Privacy → Accessibility → ✓ Terminal
#    System Settings → Privacy → Full Disk Access → ✓ Terminal

# 3. Start the runtime
bash scripts/start.sh

# 4. Open the Xcode project and run the Swift app
open apps/macos/Friday/Friday.xcodeproj
```

---

## Wake Word

By default FRIDAY uses `hey_mycroft` as a placeholder until you train a custom model.

```bash
# Train your custom "hey friday" model (~30 min, 50 recordings)
bash scripts/train_wakeword.sh
```

---

## Voice Commands (v1)

| Say | Action |
|-----|--------|
| "Hey Friday, open my resume" | Finds and opens your resume |
| "Morning mode" | Runs Morning Mode routine |
| "Coding mode" | Opens Cursor, Terminal, Spotify |
| "Open Spotify" | Launches Spotify |
| "Open github.com" | Opens in browser |
| "Job hunt mode" | Opens LinkedIn, resume, mail |
| "Interview mode" | Opens Notes + LeetCode |

---

## Learning

FRIDAY learns from every interaction:

- **Alias learning** — after you open a file, it remembers `"resume"` → `/path/to/your/resume.pdf`
- **Correction learning** — if voice confidence is low, type the correction. Saved for future training.
- **Pattern detection** — if you run the same two commands repeatedly, FRIDAY suggests a routine.

View what FRIDAY has learned: click the menu bar icon → (coming in v1 Settings panel)

---

## Routines (Prebuilt)

| Routine | Trigger |
|---------|---------|
| Morning Mode | "morning mode", "good morning" |
| Coding Mode | "coding mode", "let us code" |
| Job Hunt Mode | "job hunt mode", "job hunting" |
| Interview Mode | "interview mode", "interview prep" |

---

## Configuration

Edit `config/friday.yaml` to change models, voice, or thresholds.
Override any setting with `FRIDAY_` env vars (e.g. `FRIDAY_OLLAMA_MODEL=llama3.1:8b`).

---

## Development

```bash
# Activate venv
source .venv/bin/activate

# Run tests
pytest tests/ -v

# Type-check
mypy runtime/ modules/ shared/ --ignore-missing-imports

# Lint
ruff check .
```

---

## Project Structure

```
friday/
├── apps/macos/        SwiftUI menu bar app
├── runtime/           FastAPI runtime server
├── modules/
│   ├── wake/          Wake word detection
│   ├── stt/           Speech-to-text
│   ├── llm/           Intent planning (Ollama)
│   ├── tts/           Text-to-speech
│   ├── memory/        Memory store + learner
│   └── automation/    macOS actions + file search
├── shared/            Pydantic schemas + constants
├── database/          SQLite layer + migrations
├── config/            friday.yaml
├── scripts/           setup, start, train
└── tests/             pytest test suite
```

---

## Roadmap

| Phase | Status |
|-------|--------|
| Foundation (DB, runtime, Swift app) | 🔲 Week 1–2 |
| Voice pipeline (wake, STT, TTS) | 🔲 Week 3–4 |
| Intent + Action (LLM, tools, file search) | 🔲 Week 5–6 |
| Memory + Learning | 🔲 Week 7–8 |
| Routines + Personalization | 🔲 Week 9–10 |
| Polish + v1 ship | 🔲 Week 11–12 |

---

## Privacy

Everything stays on your Mac. The database lives at `~/.friday/friday.db`.
Audio is never stored — only transcript hashes and text pairs are saved for corrections.

To reset all learned memory:
```
Hey Friday, clear all memory
```

---

*Built for one user only. No SaaS. No cloud. Yours.*
