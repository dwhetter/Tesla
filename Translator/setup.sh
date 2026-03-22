#!/usr/bin/env bash
# setup.sh — Install dependencies and download a whisper model
set -e

echo "=== Language Tutor Setup ==="
echo

# ── 1. Homebrew packages ────────────────────────────────────────────────────
echo "Installing Homebrew packages..."
brew install cmake sox whisper-cpp

# ── 2. Whisper model ────────────────────────────────────────────────────────
MODEL_DIR="$HOME/.whisper-models"
MODEL_FILE="$MODEL_DIR/ggml-base.bin"

mkdir -p "$MODEL_DIR"

if [ -f "$MODEL_FILE" ]; then
    echo "Whisper base model already present: $MODEL_FILE"
else
    echo
    echo "Downloading whisper 'base' multilingual model (~142 MB)..."
    curl -L \
        "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin" \
        -o "$MODEL_FILE" \
        --progress-bar
    echo "Model saved to $MODEL_FILE"
fi

# ── 3. Build ─────────────────────────────────────────────────────────────────
echo
echo "Building language_tutor..."
mkdir -p build
cmake -S . -B build -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel

# ── 4. Instructions ─────────────────────────────────────────────────────────
echo
echo "=== Setup complete! ==="
echo
echo "1. Copy and fill in your API key:"
echo "     cp .env.example .env"
echo "     # Edit .env — set ANTHROPIC_API_KEY"
echo "     source .env"
echo
echo "2. Run the tutor:"
echo "     ./build/language_tutor [language] [difficulty 1-5]"
echo "     ./build/language_tutor Spanish 2"
echo "     ./build/language_tutor French"
echo "     ./build/language_tutor Japanese 3"
echo
echo "First time on macOS: grant microphone access to Terminal when prompted."
