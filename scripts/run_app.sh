#!/usr/bin/env bash
# FRIDAY — Build and launch the Swift macOS app
# Requires: Xcode command line tools (xcode-select --install)
# Usage: bash scripts/run_app.sh

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="$PROJECT_ROOT/apps/macos"

GREEN='\033[0;32m'; YELLOW='\033[0;33m'; RESET='\033[0m'
info() { echo -e "${GREEN}[FRIDAY]${RESET} $*"; }
warn() { echo -e "${YELLOW}[WARN]${RESET}  $*"; }

cd "$APP_DIR"

info "Building FRIDAY Swift app..."
swift build -c release 2>&1 | grep -v "^Build complete" | grep -E "error:|warning:|Build" || true

BINARY=".build/release/Friday"
if [ ! -f "$BINARY" ]; then
    warn "Release build failed — trying debug build..."
    swift build
    BINARY=".build/debug/Friday"
fi

if [ ! -f "$BINARY" ]; then
    echo "Build failed. Check errors above."
    exit 1
fi

info "Launching FRIDAY..."
echo ""
echo "  Hotkey: Cmd+Shift+F to open FRIDAY"
echo "  Menu bar: look for the waveform icon ≋"
echo "  To stop: killall Friday"
echo ""
"$BINARY"
