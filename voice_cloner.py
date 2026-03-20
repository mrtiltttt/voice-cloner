#!/usr/bin/env python3
"""
🎙 Voice Cloner — XTTS v2 + Whisper Speech-to-Speech Pipeline
================================================================
Клонує ваш голос і перегенерує мовлення з нуля — чисто та якісно.

Режими:
  clone       — Текст → Мовлення вашим голосом
  sts         — Speech-to-Speech: брудний запис → чистий запис вашим голосом
  interactive — Інтерактивне меню

Приклади:
  python voice_cloner.py clone --text "Привіт світ" --voice samples/my_voice.wav
  python voice_cloner.py sts --input dirty.wav --voice samples/my_voice.wav
  python voice_cloner.py interactive
"""

import argparse
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Patch transformers 5.x compatibility (must run BEFORE any TTS import)
from patch_transformers import apply_patches
apply_patches()

# ── Кольори для терміналу ─────────────────────────────────────
class C:
    BOLD = "\033[1m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    CYAN = "\033[96m"
    MAGENTA = "\033[95m"
    RESET = "\033[0m"

def log(msg, color=C.GREEN):
    print(f"{color}{msg}{C.RESET}")

def log_step(step, msg):
    print(f"\n{C.CYAN}{'─' * 50}{C.RESET}")
    print(f"{C.BOLD}{C.MAGENTA}  [{step}] {msg}{C.RESET}")
    print(f"{C.CYAN}{'─' * 50}{C.RESET}")

# ── Глобальні змінні ──────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent.resolve()
SAMPLES_DIR = SCRIPT_DIR / "samples"
OUTPUT_DIR = SCRIPT_DIR / "output"
SUPPORTED_AUDIO = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wma"}

# ── Ледаче завантаження моделей ───────────────────────────────
_tts_model = None
_whisper_model = None

def get_device():
    """Визначає найкращий пристрій: MPS (Apple Silicon) > CUDA > CPU."""
    import torch
    if torch.backends.mps.is_available():
        return "mps"
    elif torch.cuda.is_available():
        return "cuda"
    return "cpu"

def get_tts():
    """Завантажує XTTS v2 модель (кешується)."""
    global _tts_model
    if _tts_model is None:
        from TTS.api import TTS
        device = get_device()
        log(f"📥 Завантажую XTTS v2 на {device.upper()}...", C.YELLOW)
        start = time.time()
        _tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)
        elapsed = time.time() - start
        log(f"✅ Модель завантажена за {elapsed:.1f}с", C.GREEN)
    return _tts_model

def get_whisper(model_size="medium"):
    """Завантажує Whisper модель для транскрипції."""
    global _whisper_model
    if _whisper_model is None:
        import whisper
        log(f"📥 Завантажую Whisper ({model_size})...", C.YELLOW)
        start = time.time()
        _whisper_model = whisper.load_model(model_size)
        elapsed = time.time() - start
        log(f"✅ Whisper завантажено за {elapsed:.1f}с", C.GREEN)
    return _whisper_model

# ── Генерація назви файлу ─────────────────────────────────────
def make_output_path(prefix="cloned", ext=".wav"):
    """Генерує унікальне ім'я файлу у папці output/."""
    OUTPUT_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = OUTPUT_DIR / f"{prefix}_{timestamp}{ext}"
    return str(path)

# ── Валідація файлів ──────────────────────────────────────────
def validate_audio_file(path, label="Файл"):
    """Перевіряє що аудіофайл існує і має підтримуване розширення."""
    p = Path(path)
    if not p.exists():
        log(f"❌ {label} не знайдено: {path}", C.RED)
        sys.exit(1)
    if p.suffix.lower() not in SUPPORTED_AUDIO:
        log(f"❌ Непідтримуваний формат: {p.suffix}", C.RED)
        log(f"   Підтримувані: {', '.join(sorted(SUPPORTED_AUDIO))}", C.YELLOW)
        sys.exit(1)
    size_mb = p.stat().st_size / (1024 * 1024)
    log(f"✅ {label}: {p.name} ({size_mb:.1f} MB)")
    return str(p.resolve())

# ── РЕЖИМ 1: Clone (Text → Speech) ───────────────────────────
def cmd_clone(text, voice_path, output_path=None, language="uk"):
    """
    Генерує мовлення з тексту, використовуючи клонований голос.
    
    Args:
        text: Текст для озвучення
        voice_path: Шлях до зразка голосу (30-60 сек WAV)
        output_path: Шлях для збереження результату
        language: Мова тексту (uk, en, de, fr, es, ...)
    """
    log_step("1/3", "Валідація вхідних даних")
    voice_path = validate_audio_file(voice_path, "Зразок голосу")
    
    if not text or not text.strip():
        log("❌ Текст не може бути порожнім!", C.RED)
        sys.exit(1)
    
    log(f"📝 Текст ({len(text)} символів): {text[:100]}{'...' if len(text) > 100 else ''}")
    log(f"🌐 Мова: {language}")
    
    if output_path is None:
        output_path = make_output_path("clone")
    
    log_step("2/3", "Генерація мовлення з XTTS v2")
    tts = get_tts()
    
    log("🔄 Генерую аудіо вашим голосом...", C.YELLOW)
    start = time.time()
    
    tts.tts_to_file(
        text=text,
        speaker_wav=voice_path,
        language=language,
        file_path=output_path,
    )
    
    elapsed = time.time() - start
    
    log_step("3/3", "Готово!")
    size_mb = Path(output_path).stat().st_size / (1024 * 1024)
    log(f"🎵 Результат: {output_path}")
    log(f"📊 Розмір: {size_mb:.2f} MB")
    log(f"⏱  Час генерації: {elapsed:.1f}с")
    
    return output_path

# ── РЕЖИМ 2: Speech-to-Speech ────────────────────────────────
def cmd_sts(input_path, voice_path, output_path=None, language="uk", whisper_model="medium"):
    """
    Speech-to-Speech: транскрибує брудний запис і перегенерує чисто.
    
    Args:
        input_path: Брудний запис для конвертації
        voice_path: Зразок голосу (30-60 сек чистого мовлення)
        output_path: Шлях для результату
        language: Мова
        whisper_model: Розмір Whisper моделі (tiny/base/small/medium/large)
    """
    log_step("1/5", "Валідація вхідних даних")
    input_path = validate_audio_file(input_path, "Вхідний запис")
    voice_path = validate_audio_file(voice_path, "Зразок голосу")
    
    if output_path is None:
        output_path = make_output_path("sts")
    
    # Крок 2: Транскрипція з Whisper
    log_step("2/5", "Транскрипція з Whisper")
    whisper_m = get_whisper(whisper_model)
    
    log("🔄 Розпізнаю мовлення...", C.YELLOW)
    start = time.time()
    result = whisper_m.transcribe(input_path, language=language)
    transcript = result["text"].strip()
    elapsed = time.time() - start
    
    log(f"✅ Транскрипція ({elapsed:.1f}с):")
    log(f"   📝 \"{transcript[:200]}{'...' if len(transcript) > 200 else ''}\"", C.CYAN)
    
    if not transcript:
        log("❌ Whisper не зміг розпізнати мовлення!", C.RED)
        sys.exit(1)
    
    # Крок 3: Підтвердження або редагування тексту
    log_step("3/5", "Перевірка тексту")
    print(f"\n{C.YELLOW}Повний транскрибований текст:{C.RESET}")
    print(f"{C.CYAN}{transcript}{C.RESET}\n")
    
    user_input = input(f"{C.BOLD}Натисніть Enter щоб продовжити, або введіть виправлений текст: {C.RESET}").strip()
    if user_input:
        transcript = user_input
        log("📝 Використовую ваш виправлений текст", C.GREEN)
    
    # Крок 4: Генерація з XTTS v2
    log_step("4/5", "Перегенерація голосу з XTTS v2")
    tts = get_tts()
    
    log("🔄 Генерую чисте аудіо вашим голосом...", C.YELLOW)
    start = time.time()
    
    tts.tts_to_file(
        text=transcript,
        speaker_wav=voice_path,
        language=language,
        file_path=output_path,
    )
    
    elapsed = time.time() - start
    
    # Крок 5: Результат
    log_step("5/5", "Готово!")
    size_mb = Path(output_path).stat().st_size / (1024 * 1024)
    log(f"🎵 Результат: {output_path}")
    log(f"📊 Розмір: {size_mb:.2f} MB")
    log(f"⏱  Час генерації: {elapsed:.1f}с")
    
    return output_path

# ── РЕЖИМ 3: Інтерактивний ───────────────────────────────────
def cmd_interactive():
    """Інтерактивний режим з меню."""
    print(f"""
{C.BOLD}{C.MAGENTA}╔══════════════════════════════════════════╗
║     🎙  Voice Cloner — XTTS v2          ║
║     Speech-to-Speech Pipeline            ║
╚══════════════════════════════════════════╝{C.RESET}
""")
    
    # Показати доступні зразки голосу
    samples = list_samples()
    
    while True:
        print(f"""
{C.BOLD}Оберіть режим:{C.RESET}
  {C.CYAN}1{C.RESET} — 🗣  Clone: Текст → Мовлення вашим голосом
  {C.CYAN}2{C.RESET} — 🔄 STS: Брудний запис → Чистий запис вашим голосом
  {C.CYAN}3{C.RESET} — 📂 Показати зразки голосу
  {C.CYAN}4{C.RESET} — ℹ️  Поради щодо запису зразка голосу
  {C.CYAN}q{C.RESET} — 🚪 Вийти
""")
        choice = input(f"{C.BOLD}Ваш вибір: {C.RESET}").strip().lower()
        
        if choice == "1":
            interactive_clone()
        elif choice == "2":
            interactive_sts()
        elif choice == "3":
            list_samples()
        elif choice == "4":
            show_recording_tips()
        elif choice in ("q", "quit", "exit"):
            log("👋 До побачення!", C.GREEN)
            break
        else:
            log("❌ Невідома опція, спробуйте знову", C.RED)

def list_samples():
    """Показує доступні зразки голосу."""
    samples = [f for f in SAMPLES_DIR.iterdir() if f.suffix.lower() in SUPPORTED_AUDIO]
    if samples:
        log(f"\n📂 Зразки голосу ({len(samples)}):", C.CYAN)
        for i, s in enumerate(sorted(samples), 1):
            size_mb = s.stat().st_size / (1024 * 1024)
            print(f"   {C.BOLD}{i}{C.RESET}. {s.name} ({size_mb:.1f} MB)")
    else:
        log(f"\n📂 Папка samples/ порожня", C.YELLOW)
        log(f"   Покладіть WAV-файл з вашим голосом (30-60 сек) у:", C.YELLOW)
        log(f"   {SAMPLES_DIR}/", C.CYAN)
    return samples

def pick_voice_sample():
    """Дозволяє обрати зразок голосу з меню або ввести шлях."""
    samples = [f for f in SAMPLES_DIR.iterdir() if f.suffix.lower() in SUPPORTED_AUDIO]
    
    if samples:
        sorted_samples = sorted(samples)
        log("\n📂 Доступні зразки:", C.CYAN)
        for i, s in enumerate(sorted_samples, 1):
            size_mb = s.stat().st_size / (1024 * 1024)
            print(f"   {C.BOLD}{i}{C.RESET}. {s.name} ({size_mb:.1f} MB)")
        
        choice = input(f"\n{C.BOLD}Номер зразка або шлях до файлу: {C.RESET}").strip()
        
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(sorted_samples):
                return str(sorted_samples[idx])
        except ValueError:
            pass
        
        return choice
    else:
        log("📂 Папка samples/ порожня — введіть повний шлях до файлу", C.YELLOW)
        return input(f"{C.BOLD}Шлях до зразка голосу: {C.RESET}").strip()

def interactive_clone():
    """Інтерактивний режим клонування."""
    print(f"\n{C.BOLD}🗣  Clone: Текст → Мовлення вашим голосом{C.RESET}\n")
    
    voice = pick_voice_sample()
    if not voice:
        return
    
    text = input(f"\n{C.BOLD}📝 Введіть текст для озвучення:\n{C.RESET}").strip()
    if not text:
        log("❌ Текст порожній!", C.RED)
        return
    
    lang = input(f"{C.BOLD}🌐 Мова (uk/en/de/fr/es/...) [uk]: {C.RESET}").strip() or "uk"
    
    try:
        result = cmd_clone(text, voice, language=lang)
        log(f"\n🎧 Прослухайте: open \"{result}\"", C.MAGENTA)
    except Exception as e:
        log(f"❌ Помилка: {e}", C.RED)

def interactive_sts():
    """Інтерактивний режим Speech-to-Speech."""
    print(f"\n{C.BOLD}🔄 STS: Брудний запис → Чистий запис{C.RESET}\n")
    
    input_file = input(f"{C.BOLD}📁 Шлях до брудного запису: {C.RESET}").strip()
    if not input_file:
        return
    
    voice = pick_voice_sample()
    if not voice:
        return
    
    lang = input(f"{C.BOLD}🌐 Мова (uk/en/de/fr/es/...) [uk]: {C.RESET}").strip() or "uk"
    
    whisper_size = input(
        f"{C.BOLD}🧠 Whisper модель (tiny/base/small/medium/large) [medium]: {C.RESET}"
    ).strip() or "medium"
    
    try:
        result = cmd_sts(input_file, voice, language=lang, whisper_model=whisper_size)
        log(f"\n🎧 Прослухайте: open \"{result}\"", C.MAGENTA)
    except Exception as e:
        log(f"❌ Помилка: {e}", C.RED)

def show_recording_tips():
    """Показує поради для запису зразка голосу."""
    print(f"""
{C.BOLD}{C.CYAN}═══════════════════════════════════════════
  💡 Поради для запису зразка голосу
═══════════════════════════════════════════{C.RESET}

{C.BOLD}Тривалість:{C.RESET}
  • Мінімум 10 секунд, ідеально 30-60 секунд
  • Довший зразок = краща якість клонування

{C.BOLD}Що говорити:{C.RESET}
  • Звичайний текст — наприклад, прочитайте абзац з книги
  • Різноманітні речення з різними звуками
  • Говоріть природно, з вашими звичними інтонаціями

{C.BOLD}Як записувати:{C.RESET}
  • Максимально тихе приміщення
  • Мікрофон на 15-20 см від обличчя
  • Уникайте фонового шуму
  • Формат: WAV (найкраще) або MP3

{C.BOLD}Де зберегти:{C.RESET}
  • Покладіть файл у папку: {C.GREEN}samples/{C.RESET}
  • Назвіть щось на кшталт: {C.GREEN}my_voice.wav{C.RESET}

{C.BOLD}Запис через термінал (macOS):{C.RESET}
  {C.GREEN}# Запис 30 секунд через вбудований мікрофон
  # Натисніть Ctrl+C щоб зупинити раніше
  rec samples/my_voice.wav trim 0 30{C.RESET}
  
  Або через QuickTime Player → File → New Audio Recording
""")

# ── CLI ──────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="🎙 Voice Cloner — XTTS v2 + Whisper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Приклади:
  %(prog)s clone --text "Привіт, мене звати Ростислав" --voice samples/my_voice.wav
  %(prog)s clone --text "Hello world" --voice samples/my_voice.wav --lang en
  %(prog)s sts --input dirty_recording.wav --voice samples/my_voice.wav
  %(prog)s sts --input podcast.mp3 --voice samples/my_voice.wav --whisper-model large
  %(prog)s interactive
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Режим роботи")
    
    # --- clone ---
    p_clone = subparsers.add_parser("clone", help="Текст → Мовлення вашим голосом")
    p_clone.add_argument("--text", "-t", required=True, help="Текст для озвучення")
    p_clone.add_argument("--voice", "-v", required=True, help="Зразок голосу (WAV/MP3)")
    p_clone.add_argument("--output", "-o", help="Шлях для результату (за замовчуванням: output/clone_*.wav)")
    p_clone.add_argument("--lang", "-l", default="uk", help="Мова (за замовчуванням: uk)")
    
    # --- sts ---
    p_sts = subparsers.add_parser("sts", help="Speech-to-Speech конвертація")
    p_sts.add_argument("--input", "-i", required=True, help="Брудний запис для конвертації")
    p_sts.add_argument("--voice", "-v", required=True, help="Зразок голосу (WAV/MP3)")
    p_sts.add_argument("--output", "-o", help="Шлях для результату")
    p_sts.add_argument("--lang", "-l", default="uk", help="Мова (за замовчуванням: uk)")
    p_sts.add_argument("--whisper-model", "-w", default="medium",
                        choices=["tiny", "base", "small", "medium", "large"],
                        help="Розмір Whisper моделі (за замовчуванням: medium)")
    
    # --- interactive ---
    subparsers.add_parser("interactive", help="Інтерактивний режим")
    
    args = parser.parse_args()
    
    if args.command is None:
        # Без аргументів → інтерактивний режим
        cmd_interactive()
    elif args.command == "clone":
        cmd_clone(args.text, args.voice, args.output, args.lang)
    elif args.command == "sts":
        cmd_sts(args.input, args.voice, args.output, args.lang, args.whisper_model)
    elif args.command == "interactive":
        cmd_interactive()

if __name__ == "__main__":
    main()
