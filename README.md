# 🎙 Voice Cloner — XTTS v2

Клонує ваш голос і генерує чисте студійне аудіо. macOS app з вбудованими моделями — працює з коробки.

## Швидкий старт

### Варіант А — Запуск без збірки (для розробки)
```bash
./setup.sh                        # встановлює залежності (~10 хв)
source .venv/bin/activate
python3 app.py                    # запускає GUI
```

### Варіант Б — Збірка інсталера (для розповсюдження)
```bash
chmod +x create_installer.sh
./create_installer.sh             # робить ВСЕ автоматично (~30 хв)
open Voice_Cloner_Installer.dmg   # відкриває інсталер
```
Перетягніть **Voice Cloner** → **Applications** → готово!

---

## Системні вимоги

| Вимога | Мінімум | Рекомендовано |
|--------|---------|---------------|
| Чіп | Apple M1 | M1 Pro / M2+ |
| RAM | 16 GB | 32 GB |
| Диск | ~5 GB (моделі + app) | ~8 GB |
| Python | 3.10 | 3.12 |
| macOS | 12+ | 13+ |

```bash
# Встановити Python 3.12 якщо його немає:
brew install python@3.12
```

---

## Структура проєкту

```
voice-cloner/
├── app.py                  ← GUI додаток (Tkinter, темна тема)
├── voice_cloner.py         ← CLI версія
├── download_models.py      ← Завантаження моделей у models/
├── setup.sh                ← Встановлення залежностей
├── build_app.sh            ← Збірка Voice Cloner.app
├── create_installer.sh     ← Збірка повного DMG-інсталера
├── requirements.txt
├── models/                 ← Моделі (створюється автоматично)
│   ├── xtts_v2/            ← ~1.8 GB
│   └── whisper/            ← ~1.5 GB
├── samples/                ← Зразки голосу
└── output/                 ← Результати генерації
```

---

## Режими роботи

### 🖥 GUI (app.py)

Темний інтерфейс з двома вкладками:

**🗣 Clone** — текст → мовлення вашим голосом
- Введіть текст
- Оберіть мову
- Натисніть "Згенерувати"

**🔄 STS (Speech-to-Speech)** — перегенерація брудного запису
- Завантажте аудіо
- Натисніть "Транскрибувати" (Whisper розпізнає текст)
- Виправте текст за потреби
- Натисніть "Згенерувати" (XTTS v2 створить чистий запис)

### 💻 CLI (voice_cloner.py)

```bash
# Клонування голосу
python3 voice_cloner.py clone --text "Привіт" --voice samples/my_voice.wav

# Speech-to-Speech
python3 voice_cloner.py sts --input dirty.wav --voice samples/my_voice.wav

# Інтерактивний режим
python3 voice_cloner.py interactive
```

**Параметри:**

| Параметр | Опис | За замовчуванням |
|----------|------|-----------------|
| `--lang` | Мова: `uk`, `en`, `de`, `fr`, `es`, `it`, `pl`, `pt` | `uk` |
| `--whisper-model` | Розмір Whisper: `tiny`, `base`, `small`, `medium`, `large` | `medium` |
| `--output` | Шлях для збереження | `output/<type>_<timestamp>.wav` |

---

## Скрипти збірки

### `setup.sh` — встановлення середовища
- Знаходить Python 3.10-3.13
- Створює віртуальне середовище `.venv`
- Встановлює залежності
- Перевіряє MPS (Apple Silicon GPU)
- Завантажує XTTS v2 у кеш

### `create_installer.sh` — повна збірка інсталера

| Крок | Опис | Час (1-й раз) | Повторно |
|------|------|--------------|----------|
| 1/6 | Пошук Python | 1с | 1с |
| 2/6 | venv + залежності | ~5 хв | ⚡ ~10с |
| 3/6 | Перевірка GPU | 1с | 1с |
| 4/6 | Завантаження моделей (3.5 GB) | ~10 хв | ⚡ 0с |
| 5/6 | Збірка .app (PyInstaller) | ~10 хв | ~10 хв |
| 6/6 | Створення DMG | ~2 хв | ~2 хв |

> **При повторних збірках** (вдосконалення коду) перезбираються лише .app та DMG — моделі та venv використовуються з кешу.

---

## Поради для запису зразка голосу

- **Тривалість:** 30-60 секунд (мінімум 10 сек)
- **Що говорити:** звичайний текст, різноманітні речення
- **Приміщення:** максимально тихе, без ехо
- **Мікрофон:** 15-20 см від обличчя
- **Формат:** WAV (найкраще) або MP3
- **Зберегти:** у папку `samples/`

---

## Технології

| Компонент | Технологія |
|-----------|-----------|
| Клонування голосу | [Coqui XTTS v2](https://github.com/coqui-ai/TTS) |
| Транскрипція | [OpenAI Whisper](https://github.com/openai/whisper) |
| ML фреймворк | PyTorch (MPS backend для Apple Silicon) |
| GUI | Tkinter (нативний macOS) |
| Запис аудіо | sounddevice + soundfile |
| Збірка .app | PyInstaller |
| Інсталер | hdiutil (DMG) |
