#!/bin/bash
# ============================================================
#  Voice Cloner — Повна збірка інсталера
#  Один скрипт робить ВСЕ: venv → моделі → .app → DMG
#
#  Запуск на M1 Pro 32GB:
#    chmod +x create_installer.sh
#    ./create_installer.sh
#
#  Результат: Voice_Cloner_Installer.dmg
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

APP_NAME="Voice Cloner"
DMG_NAME="Voice_Cloner_Installer"
DMG_PATH="$SCRIPT_DIR/$DMG_NAME.dmg"
DMG_TMP="$SCRIPT_DIR/.dmg_tmp"
VENV_DIR="$SCRIPT_DIR/.venv"

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║  🎙 Voice Cloner — Installer Builder         ║"
echo "║  Збірка повного DMG-інсталера                ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# ── Step 1: Python ────────────────────────────────────────────
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  [1/6] 🐍 Пошук Python 3.10-3.13..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

PYTHON=""
for py in python3.12 python3.11 python3.10 python3.13 python3; do
    if command -v "$py" &>/dev/null; then
        ver=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$("$py" -c "import sys; print(sys.version_info.major)")
        minor=$("$py" -c "import sys; print(sys.version_info.minor)")
        if [ "$major" -eq 3 ] && [ "$minor" -ge 10 ] && [ "$minor" -le 13 ]; then
            PYTHON="$py"
            echo "✅ Знайдено Python $ver ($py)"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo ""
    echo "❌ Потрібен Python 3.10-3.13!"
    echo ""
    echo "   Встановіть:"
    echo "   brew install python@3.12"
    echo ""
    echo "   Потім запустіть цей скрипт знову."
    exit 1
fi

# Delete old venv to prevent stale packages
if [ -d "$VENV_DIR" ]; then
    echo "🗑  Видаляю старе середовище..."
    rm -rf "$VENV_DIR"
fi

echo "📦 Створюю .venv..."
"$PYTHON" -m venv "$VENV_DIR"

source "$VENV_DIR/bin/activate"
pip install --upgrade pip --quiet

echo "📥 Встановлюю залежності (це може зайняти 5-10 хвилин)..."
pip install -r "$SCRIPT_DIR/requirements.txt"

# Verify correct versions
echo ""
echo "🔍 Перевірка версій..."
python3 patch_transformers.py
python3 -c "
import sys; sys.path.insert(0, '.')
from patch_transformers import apply_patches; apply_patches()
import transformers, TTS
print(f'   transformers: {transformers.__version__}')
print(f'   coqui-tts:    {TTS.__version__}')
from transformers.pytorch_utils import isin_mps_friendly
print('✅ Версії сумісні (isin_mps_friendly ✓)')
"
echo "✅ Залежності встановлено"

# ── Step 3: Check MPS ────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  [3/6] 🔍 Перевірка Apple Silicon GPU..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

python3 -c "
import torch
if torch.backends.mps.is_available():
    print('✅ MPS (Apple Silicon GPU) доступний')
else:
    print('⚠️  MPS недоступний — CPU буде використано')
"

# ── Step 4: Download Models ───────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  [4/6] 📥 Завантаження моделей (~3.5 GB)..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [ -f "models/xtts_v2/config.json" ] && [ -d "models/whisper" ]; then
    echo "♻️  Моделі вже завантажено"
else
    python3 download_models.py
fi

MODEL_SIZE=$(du -sh models/ | cut -f1)
echo "✅ Моделі: $MODEL_SIZE"

# ── Step 5: Build .app ────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  [5/6] 🏗  Збірка Voice Cloner.app..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "        (це може зайняти 10-15 хвилин)"
echo ""

# Clean
rm -rf build dist "$APP_NAME.app" *.spec

pyinstaller \
    --name "$APP_NAME" \
    --windowed \
    --noconfirm \
    --clean \
    --onedir \
    --icon NONE \
    --add-data "models:models" \
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
    --exclude-module "pytest" \
    --exclude-module "setuptools" \
    app.py 2>&1 | tail -20

if [ ! -d "dist/$APP_NAME.app" ]; then
    echo ""
    echo "❌ Помилка збірки .app!"
    echo "   Перевірте лог вище. Як тимчасове рішення:"
    echo "   source .venv/bin/activate && python3 app.py"
    exit 1
fi

echo "✅ $APP_NAME.app зібрано"
APP_SIZE=$(du -sh "dist/$APP_NAME.app" | cut -f1)
echo "📊 Розмір: $APP_SIZE"

# ── Step 6: Create DMG ────────────────────────────────────────
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  [6/6] 💿 Створення DMG-інсталера..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Clean old
rm -rf "$DMG_TMP" "$DMG_PATH"

# Create temp folder for DMG contents
mkdir -p "$DMG_TMP"

# Copy .app
cp -R "dist/$APP_NAME.app" "$DMG_TMP/"

# Create symlink to /Applications
ln -s /Applications "$DMG_TMP/Applications"

# Create background readme
cat > "$DMG_TMP/.README.txt" << 'EOF'
Voice Cloner — XTTS v2 + Whisper
═════════════════════════════════

Перетягніть "Voice Cloner" у папку Applications.

Після встановлення:
1. Відкрийте Voice Cloner з Launchpad або Applications
2. Запишіть зразок голосу (30-60 секунд)
3. Введіть текст або завантажте аудіо
4. Натисніть "Згенерувати"

Моделі вже вбудовані — працює без інтернету!
EOF

# Calculate DMG size (app size + 50MB padding)
APP_SIZE_MB=$(du -sm "dist/$APP_NAME.app" | cut -f1)
DMG_SIZE_MB=$((APP_SIZE_MB + 50))

# Create DMG
echo "📦 Створюю DMG ($DMG_SIZE_MB MB)..."

hdiutil create \
    -volname "$APP_NAME" \
    -srcfolder "$DMG_TMP" \
    -ov \
    -format UDZO \
    -imagekey zlib-level=9 \
    "$DMG_PATH" \
    2>/dev/null

# Cleanup
rm -rf "$DMG_TMP" build dist *.spec

if [ -f "$DMG_PATH" ]; then
    DMG_FINAL_SIZE=$(du -sh "$DMG_PATH" | cut -f1)
    
    echo ""
    echo "╔══════════════════════════════════════════════╗"
    echo "║  ✅ ГОТОВО!                                   ║"
    echo "╚══════════════════════════════════════════════╝"
    echo ""
    echo "  💿 Інсталер: $DMG_PATH"
    echo "  📊 Розмір:   $DMG_FINAL_SIZE"
    echo ""
    echo "  Як встановити:"
    echo "  1. Відкрити:  open '$DMG_NAME.dmg'"
    echo "  2. Перетягнути Voice Cloner → Applications"
    echo "  3. Закрити DMG"
    echo "  4. Запустити з Launchpad!"
    echo ""
    echo "  📦 Моделі вбудовані — працює без інтернету"
    echo ""
else
    echo ""
    echo "❌ Не вдалося створити DMG"
fi
