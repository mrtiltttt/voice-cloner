#!/bin/bash
# ============================================================
# Build Voice Cloner.app — з вбудованими моделями
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "🔨 Building Voice Cloner.app (з моделями)..."
echo ""

# Check venv
if [ ! -d ".venv" ]; then
    echo "❌ Спочатку запустіть ./setup.sh"
    exit 1
fi

source .venv/bin/activate

# --- Step 1: Download models if not present ---
if [ ! -d "models/xtts_v2" ] || [ ! -d "models/whisper" ]; then
    echo "📥 Моделі не знайдено — завантажую..."
    echo ""
    python3 download_models.py
    echo ""
fi

# Verify models exist
if [ ! -f "models/xtts_v2/config.json" ]; then
    echo "❌ XTTS v2 модель не знайдена в models/xtts_v2/"
    echo "   Запустіть: python3 download_models.py"
    exit 1
fi

if [ ! -d "models/whisper" ]; then
    echo "❌ Whisper модель не знайдена в models/whisper/"
    echo "   Запустіть: python3 download_models.py"
    exit 1
fi

MODEL_SIZE=$(du -sh models/ | cut -f1)
echo "📦 Моделі: $MODEL_SIZE"
echo ""

# --- Step 2: Check PyInstaller ---
if ! command -v pyinstaller &>/dev/null; then
    echo "📥 Встановлюю PyInstaller..."
    pip install pyinstaller --quiet
fi

# --- Step 3: Clean previous builds ---
rm -rf build dist "Voice Cloner.app"

# --- Step 4: Build ---
echo "🏗  Збираю .app (це може зайняти 5-10 хвилин)..."
echo ""

pyinstaller \
    --name "Voice Cloner" \
    --windowed \
    --noconfirm \
    --clean \
    --onedir \
    --icon NONE \
    --add-data "models:models" \
    --add-data "samples:samples" \
    --add-data "output:output" \
    --hidden-import "TTS" \
    --hidden-import "TTS.api" \
    --hidden-import "TTS.utils" \
    --hidden-import "TTS.tts.configs.xtts_config" \
    --hidden-import "TTS.tts.models.xtts" \
    --hidden-import "whisper" \
    --hidden-import "sounddevice" \
    --hidden-import "soundfile" \
    --hidden-import "torch" \
    --hidden-import "torchaudio" \
    --hidden-import "numpy" \
    --hidden-import "scipy" \
    --hidden-import "encodec" \
    --collect-all "TTS" \
    --collect-all "whisper" \
    --exclude-module "matplotlib" \
    --exclude-module "PIL" \
    --exclude-module "cv2" \
    --exclude-module "IPython" \
    --exclude-module "jupyter" \
    app.py

# Move .app to project root
if [ -d "dist/Voice Cloner.app" ]; then
    mv "dist/Voice Cloner.app" .
    
    APP_SIZE=$(du -sh "Voice Cloner.app" | cut -f1)
    
    echo ""
    echo "========================================"
    echo "✅ Voice Cloner.app створено!"
    echo "========================================"
    echo ""
    echo "📊 Розмір: $APP_SIZE"
    echo "📦 Моделі вбудовані — працює з коробки!"
    echo ""
    echo "Запустіть: open 'Voice Cloner.app'"
    echo ""
    
    # Cleanup
    rm -rf build dist *.spec
else
    echo ""
    echo "❌ Помилка збірки. Перевірте лог вище."
    echo ""
    echo "💡 Альтернатива — запустіть без збірки:"
    echo "   source .venv/bin/activate"
    echo "   python3 app.py"
fi
