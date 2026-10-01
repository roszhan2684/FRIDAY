#!/usr/bin/env bash
# FRIDAY — Train "hey friday" wake word verifier
# Usage: bash scripts/train_wakeword.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
VENV="$PROJECT_ROOT/.venv"
FRIDAY_HOME="$HOME/.friday"
SAMPLES_DIR="$FRIDAY_HOME/wake_samples/positive"
NEG_DIR="$FRIDAY_HOME/wake_samples/negative"
MODEL_DIR="$FRIDAY_HOME/models"
MODEL_OUT="$MODEL_DIR/hey_friday_verifier.pkl"

source "$VENV/bin/activate"
export PYTHONPATH="$PROJECT_ROOT"

mkdir -p "$SAMPLES_DIR" "$NEG_DIR" "$MODEL_DIR"

echo ""
echo "======================================"
echo "  FRIDAY — Hey Friday Wake Word Setup "
echo "======================================"
echo ""

# ─── Check existing samples ───────────────────────────────────────────────────
EXISTING=$(ls "$SAMPLES_DIR"/sample_*.wav 2>/dev/null | wc -l | tr -d ' ')

if [ "$EXISTING" -ge 30 ]; then
    echo "  Found $EXISTING existing samples."
    echo -n "  Re-record? [y/N]: "
    read -r REDO
    if [[ ! "$REDO" =~ ^[Yy]$ ]]; then
        echo "  Skipping recording — using existing $EXISTING samples."
        echo ""
        SKIP_RECORD=1
    fi
fi

# ─── Write recording script to temp file ─────────────────────────────────────
if [ "${SKIP_RECORD:-0}" != "1" ]; then

RECORD_PY=$(mktemp /tmp/friday_record_XXXX.py)
cat > "$RECORD_PY" << 'PYEOF'
import sys, wave
import numpy as np
import sounddevice as sd
from pathlib import Path

SAMPLES_DIR = Path(sys.argv[1])
RATE        = 16000
DURATION    = 2.0
TARGET      = 30

existing = sorted(SAMPLES_DIR.glob("sample_*.wav"))
start_n  = len(existing) + 1

print(f"  You will say 'hey friday' {TARGET} times.")
print(f"  Speak naturally. Vary tone slightly.")
print("")
print("  Press ENTER to begin...", flush=True)
input()

print("")
recorded = 0
n = start_n

while recorded < TARGET:
    print(f"  [{n:02d}/30] Press ENTER then say 'hey friday'  ", end="", flush=True)
    input()
    print("  >>> Recording... say it NOW", flush=True)

    audio = sd.rec(int(DURATION * RATE), samplerate=RATE, channels=1, dtype="int16")
    sd.wait()

    rms = float(np.sqrt(np.mean(audio.astype(np.float32) ** 2)))
    if rms < 100:
        print(f"  Too quiet (level={rms:.0f}). Speak louder, try again.\n")
        continue

    out = SAMPLES_DIR / f"sample_{n:03d}.wav"
    with wave.open(str(out), "wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(RATE)
        wf.writeframes(audio.tobytes())

    print(f"  Saved  (level={rms:.0f})\n")
    recorded += 1
    n += 1

print(f"  Done — {recorded} samples recorded.\n")
PYEOF

python3 "$RECORD_PY" "$SAMPLES_DIR"
REC_EXIT=$?
rm -f "$RECORD_PY"
[ $REC_EXIT -ne 0 ] && echo "ERROR: Recording failed" && exit 1

fi  # end skip_record

# ─── Check sample count ───────────────────────────────────────────────────────
TOTAL=$(ls "$SAMPLES_DIR"/sample_*.wav 2>/dev/null | wc -l | tr -d ' ')
echo "Positive samples: $TOTAL"
[ "$TOTAL" -lt 15 ] && echo "ERROR: Need 15+ samples. Run again." && exit 1

# ─── Generate negative clips using macOS TTS ─────────────────────────────────
NEG_TOTAL=$(ls "$NEG_DIR"/*.wav 2>/dev/null | wc -l | tr -d ' ')

if [ "$NEG_TOTAL" -lt 10 ]; then
    echo ""
    echo ">>> Generating negative clips (macOS TTS)..."

    NEG_PY=$(mktemp /tmp/friday_neg_XXXX.py)
    cat > "$NEG_PY" << 'PYEOF'
import subprocess, os, sys
from pathlib import Path

NEG_DIR = Path(sys.argv[1])

# Variety of phrases that are NOT "hey friday"
PHRASES = [
    "open safari", "good morning boss", "coding mode",
    "what time is it", "morning mode activated",
    "open my resume", "remind me to call mom",
    "add milk to the shopping list", "play some music",
    "search youtube for tutorials", "how was my day",
    "interview mode", "let us code today", "open github",
    "good evening how are you", "study mode on",
    "open VS code and terminal", "what is on my calendar",
    "I want to watch a movie tonight", "open my portfolio",
]

for i, phrase in enumerate(PHRASES):
    aiff = f"/tmp/friday_neg_{i:03d}.aiff"
    wav  = NEG_DIR / f"neg_{i:03d}.wav"
    if wav.exists():
        continue
    # Generate AIFF using macOS say
    r = subprocess.run(
        ["say", "-v", "Samantha", "-r", "140", phrase, "-o", aiff],
        capture_output=True
    )
    if r.returncode != 0 or not Path(aiff).exists():
        print(f"  Skipped: {phrase}")
        continue
    # Convert to 16kHz 16-bit mono WAV using afconvert (built into macOS)
    subprocess.run(
        ["afconvert", "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", aiff, str(wav)],
        capture_output=True
    )
    try:
        os.unlink(aiff)
    except Exception:
        pass
    print(f"  Generated: {wav.name}")

total = len(list(NEG_DIR.glob("*.wav")))
print(f"  Total negative clips: {total}")
PYEOF

    python3 "$NEG_PY" "$NEG_DIR"
    rm -f "$NEG_PY"
fi

NEG_TOTAL=$(ls "$NEG_DIR"/*.wav 2>/dev/null | wc -l | tr -d ' ')
echo "Negative clips: $NEG_TOTAL"

# ─── Train verifier ───────────────────────────────────────────────────────────
echo ""
echo ">>> TRAINING PHASE  (1-2 minutes)..."
echo ""

TRAIN_PY=$(mktemp /tmp/friday_train_XXXX.py)
cat > "$TRAIN_PY" << 'PYEOF'
import sys, glob
from pathlib import Path
import numpy as np
import openwakeword
from openwakeword.custom_verifier_model import train_custom_verifier

samples_dir = Path(sys.argv[1])
neg_dir     = Path(sys.argv[2])
model_dir   = Path(sys.argv[3])
final_path = model_dir / "hey_friday_verifier.pkl"

# Build LISTS of file paths (not directories — that was the bug)
positive_files = sorted(samples_dir.glob("sample_*.wav"))
negative_files = sorted(neg_dir.glob("*.wav"))

if not positive_files:
    print("ERROR: No positive WAV files found")
    sys.exit(1)
if not negative_files:
    print("ERROR: No negative WAV files found")
    sys.exit(1)

print(f"  Positive : {len(positive_files)} files")
print(f"  Negative : {len(negative_files)} files")
print(f"  Output   : {final_path}")
print("")

# ── Direct training with threshold=0.0 ───────────────────────────────────────
# train_custom_verifier uses threshold=0.5 internally, which gives 0 features
# because "hey friday" doesn't strongly activate hey_jarvis. We bypass this
# by calling get_reference_clip_features directly with threshold=0.0.
try:
    from openwakeword.model import Model
    from openwakeword.custom_verifier_model import (
        get_reference_clip_features,
        train_verifier_model,
    )
    import pickle
    from tqdm import tqdm

    oww = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

    print("  Extracting positive features...")
    pos_feats = np.vstack([
        get_reference_clip_features(str(f), oww, "hey_jarvis", N=5, threshold=0.0)
        for f in tqdm(positive_files, desc="  Positive clips")
    ])
    print(f"  Positive feature shape: {pos_feats.shape}")

    print("  Extracting negative features...")
    neg_feats = np.vstack([
        get_reference_clip_features(str(f), oww, "hey_jarvis", N=2, threshold=0.0)
        for f in tqdm(negative_files, desc="  Negative clips")
    ])
    print(f"  Negative feature shape: {neg_feats.shape}")

    if pos_feats.shape[0] == 0 or neg_feats.shape[0] == 0:
        print("  ERROR: Feature extraction returned empty arrays")
        sys.exit(1)

    all_features = np.vstack([pos_feats, neg_feats])
    labels = np.array([1]*pos_feats.shape[0] + [0]*neg_feats.shape[0])

    print(f"\n  Training on {all_features.shape[0]} total frames...")
    verifier = train_verifier_model(all_features, labels)

    with open(str(final_path), "wb") as f:
        pickle.dump(verifier, f)

    with open(str(model_dir / "hey_friday_base_model.txt"), "w") as f:
        f.write("hey_jarvis")

except Exception as exc:
    print(f"  ERROR: {exc}")
    import traceback; traceback.print_exc()
    sys.exit(1)

if final_path.exists():
    print(f"\n  Model saved : {final_path}")
    print(f"  Size        : {final_path.stat().st_size:,} bytes")
else:
    print(f"  ERROR: Model file not found at {final_path}")
    sys.exit(1)
PYEOF

python3 "$TRAIN_PY" "$SAMPLES_DIR" "$NEG_DIR" "$MODEL_DIR"
TRAIN_EXIT=$?
rm -f "$TRAIN_PY"

[ $TRAIN_EXIT -ne 0 ] && echo "ERROR: Training failed" && exit 1

# ─── Done ─────────────────────────────────────────────────────────────────────
echo ""
echo "======================================"
echo "  TRAINING COMPLETE"
echo "======================================"
echo ""
echo "  Model: $MODEL_OUT"
echo ""
echo "  Restart FRIDAY now:"
echo ""
echo "    cd /Users/roszhanraj/Sunday"
echo "    make stop && make start"
echo ""
echo "  Then say:  hey friday"
echo ""
