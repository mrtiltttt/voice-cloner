#!/bin/bash
# ============================================================
# Voice Cloner Setup — XTTS v2 + Whisper
# Для MacBook Pro M1 Pro (Apple Silicon)
# ============================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "🎙  Voice Cloner — Setup"
echo "========================"
echo ""

# --- 1. Перевірка Python ---
PYTHON=""
for py in python3.12 python3.11 python3.10 python3; do
    if command -v "$py" &>/dev/null; then
        version=$("$py" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        major=$("$py" -c "import sys; print(sys.version_info.major)")
        minor=$("$py" -c "import sys; print(sys.version_info.minor)")
        if [ "$major" -eq 3 ] && [ "$minor" -ge 10 ] && [ "$minor" -le 13 ]; then
            PYTHON="$py"
            echo "✅ Знайдено Python $version ($py)"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "❌ Потрібен Python 3.10-3.13"
    echo "   Встановіть: brew install python@3.12"
    exit 1
fi

# --- 2. Створення віртуального середовища ---
if [ -d "$VENV_DIR" ]; then
    echo "♻️  Віртуальне середовище вже існує, перевикористовую..."
else
    echo "📦 Створюю віртуальне середовище..."
    "$PYTHON" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
echo "✅ Віртуальне середовище активовано"

# --- 3. Оновлення pip ---
echo ""
echo "📥 Оновлюю pip..."
pip install --upgrade pip --quiet

# --- 4. Встановлення залежностей ---
echo ""
echo "📥 Встановлюю залежності (це може зайняти 5-10 хвилин)..."
pip install -r "$SCRIPT_DIR/requirements.txt" --quiet

# --- 5. Перевірка MPS (Apple Silicon GPU) ---
echo ""
echo "🔍 Перевіряю Apple Silicon GPU (MPS)..."
python3 -c "
import torch
if torch.backends.mps.is_available():
    print('✅ MPS (Apple Silicon GPU) доступний — обчислення будуть прискорені!')
    device = torch.device('mps')
    x = torch.ones(3, device=device)
    print(f'   Тестовий тензор на MPS: {x}')
else:
    print('⚠️  MPS недоступний — буде використано CPU (повільніше)')
"

# --- 6. Перевірка Whisper ---
echo ""
echo "🔍 Перевіряю Whisper..."
python3 -c "import whisper; print('✅ Whisper встановлено')"

# --- 7. Попереднє завантаження моделі XTTS v2 ---
echo ""
echo "📥 Завантажую модель XTTS v2 (~1.8 GB, це одноразово)..."
python3 -c "
from TTS.api import TTS
print('   Ініціалізую TTS з XTTS v2...')
tts = TTS('tts_models/multilingual/multi-dataset/xtts_v2')
print('✅ Модель XTTS v2 завантажена та кешована!')
"

# --- 8. Створення папок ---
mkdir -p "$SCRIPT_DIR/samples"
mkdir -p "$SCRIPT_DIR/output"

# --- Готово! ---
echo ""
echo "========================================"
echo "🎉 Все готово!"
echo "========================================"
echo ""
echo "Як використовувати:"
echo ""
echo "  1. Активуйте середовище:"
echo "     source $VENV_DIR/bin/activate"
echo ""
echo "  2. Клонування голосу (текст → мовлення вашим голосом):"
echo "     python3 voice_cloner.py clone --text 'Привіт, це мій голос' --voice samples/my_voice.wav"
echo ""
echo "  3. Speech-to-Speech (перегенерація брудного запису):"
echo "     python3 voice_cloner.py sts --input dirty_recording.wav --voice samples/my_voice.wav"
echo ""
echo "  4. Інтерактивний режим:"
echo "     python3 voice_cloner.py interactive"
echo ""
