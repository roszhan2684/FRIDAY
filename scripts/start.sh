#!/usr/bin/env bash
# FRIDAY — Start all services
# Usage: bash scripts/start.sh

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RESET='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV="$PROJECT_ROOT/.venv"

info() { echo -e "${GREEN}[FRIDAY]${RESET} $*"; }
warn() { echo -e "${YELLOW}[WARN]${RESET}  $*"; }

cd "$PROJECT_ROOT"

# ─── Activate venv ────────────────────────────────────────────────────────────
if [ -d "$VENV" ]; then
    source "$VENV/bin/activate"
else
    warn "Virtual environment not found. Run: bash scripts/setup.sh"
    exit 1
fi

# ─── Check Ollama ─────────────────────────────────────────────────────────────
if ! curl -s http://localhost:11434/api/tags &>/dev/null; then
    info "Starting Ollama in background..."
    ollama serve &>/tmp/ollama.log &
    sleep 2
fi

# ─── Start Python runtime ─────────────────────────────────────────────────────
info "Starting FRIDAY runtime on http://127.0.0.1:7700"
export PYTHONPATH="$PROJECT_ROOT"
python -m runtime.main
