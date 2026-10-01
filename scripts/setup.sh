#!/usr/bin/env bash
# FRIDAY — Full environment setup script
# Run once after cloning: bash scripts/setup.sh

set -euo pipefail

YELLOW='\033[0;33m'
GREEN='\033[0;32m'
RED='\033[0;31m'
RESET='\033[0m'

info()    { echo -e "${GREEN}[FRIDAY]${RESET} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
error()   { echo -e "${RED}[ERROR]${RESET} $*"; exit 1; }

info "Setting up FRIDAY..."

# ─── Check macOS ─────────────────────────────────────────────────────────────
[[ "$(uname)" == "Darwin" ]] || error "FRIDAY requires macOS."

# ─── Check Apple Silicon ──────────────────────────────────────────────────────
if [[ "$(uname -m)" == "arm64" ]]; then
    info "Apple Silicon detected — Metal acceleration will be used for STT."
else
    warn "Intel Mac detected — mlx-whisper will not be available. Using faster-whisper on CPU."
fi

# ─── Homebrew ─────────────────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
    info "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# ─── Python 3.11 ──────────────────────────────────────────────────────────────
if ! command -v python3.11 &>/dev/null; then
    info "Installing Python 3.11..."
    brew install python@3.11
fi

PYTHON=$(command -v python3.11 || command -v python3)
info "Using Python: $PYTHON ($($PYTHON --version))"

# ─── PortAudio (required by PyAudio) ─────────────────────────────────────────
if ! brew list portaudio &>/dev/null; then
    info "Installing PortAudio..."
    brew install portaudio
fi

# ─── Ollama ───────────────────────────────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
    info "Installing Ollama..."
    brew install ollama
fi

# ─── Pull LLM model ───────────────────────────────────────────────────────────
info "Pulling Ollama model: llama3.2:3b (this will take a few minutes)..."
ollama pull llama3.2:3b || warn "Ollama pull failed — make sure Ollama is running: ollama serve"

# ─── Python virtual environment ───────────────────────────────────────────────
VENV_DIR="$(pwd)/.venv"
if [ ! -d "$VENV_DIR" ]; then
    info "Creating Python virtual environment..."
    $PYTHON -m venv "$VENV_DIR"
fi

info "Activating venv and installing dependencies..."
source "$VENV_DIR/bin/activate"
pip install --upgrade pip --quiet
pip install -r runtime/requirements.txt

# ─── FRIDAY home directory ────────────────────────────────────────────────────
FRIDAY_HOME="$HOME/.friday"
mkdir -p "$FRIDAY_HOME/models"
mkdir -p "$FRIDAY_HOME/datasets"
mkdir -p "$FRIDAY_HOME/logs"
info "FRIDAY home directory: $FRIDAY_HOME"

# ─── Init database ────────────────────────────────────────────────────────────
info "Initialising database..."
PYTHONPATH="$(pwd)" python -c "from database.db import init_db; init_db(); print('Database ready.')"

# ─── Wake word model ──────────────────────────────────────────────────────────
info "Downloading openwakeword models..."
python -c "
import openwakeword
openwakeword.utils.download_models()
print('Wake word models downloaded.')
" || warn "Could not download wake word models — will use fallback."

# ─── macOS permissions hint ───────────────────────────────────────────────────
echo ""
info "FRIDAY setup complete!"
echo ""
echo -e "${YELLOW}IMPORTANT — macOS Permissions Required:${RESET}"
echo "  1. Microphone:     System Settings → Privacy → Microphone → Allow Terminal"
echo "  2. Accessibility:  System Settings → Privacy → Accessibility → Allow Terminal"
echo "  3. Full Disk:      System Settings → Privacy → Full Disk Access → Allow Terminal"
echo ""
echo -e "${GREEN}To start FRIDAY:${RESET}"
echo "  bash scripts/start.sh"
echo ""
echo -e "${GREEN}To train your custom wake word (recommended):${RESET}"
echo "  bash scripts/train_wakeword.sh"
