#!/usr/bin/env python3
"""
🎙 Voice Cloner — macOS App
============================
Native macOS application for voice cloning using XTTS v2 + Whisper.
"""

import multiprocessing
multiprocessing.freeze_support()

# Patch: bypass torchcodec check + add back isin_mps_friendly for transformers 5.x
import os
os.environ["COQUI_TTS_SKIP_TORCHCODEC"] = "1"
def _patch_transformers():
    try:
        from transformers.pytorch_utils import isin_mps_friendly  # noqa
    except ImportError:
        import torch, transformers.pytorch_utils as _pu
        def isin_mps_friendly(elements, test_elements):
            if elements.device.type == "mps" or (hasattr(test_elements, "device") and test_elements.device.type == "mps"):
                return elements.unsqueeze(-1).eq(test_elements).any(-1)
            return torch.isin(elements, test_elements)
        _pu.isin_mps_friendly = isin_mps_friendly
    # Bypass torchcodec import in TTS
    try:
        import torchcodec  # noqa
    except ImportError:
        import types
        sys.modules["torchcodec"] = types.ModuleType("torchcodec")
_patch_transformers()

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import os
import sys
import time
import subprocess
import wave
from pathlib import Path
from datetime import datetime

# ── Paths ─────────────────────────────────────────────────────
APP_NAME = "Voice Cloner"

# Detect if running from PyInstaller bundle
if getattr(sys, 'frozen', False):
    BUNDLE_DIR = Path(sys._MEIPASS)
    SCRIPT_DIR = Path(os.path.dirname(sys.executable)).resolve()
else:
    BUNDLE_DIR = Path(__file__).parent.resolve()
    SCRIPT_DIR = BUNDLE_DIR

MODELS_DIR = BUNDLE_DIR / "models"
SAMPLES_DIR = SCRIPT_DIR / "samples"
OUTPUT_DIR = SCRIPT_DIR / "output"
SAMPLES_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

SUPPORTED_AUDIO = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac"}

# ── Lazy model loading ────────────────────────────────────────
_tts_model = None
_whisper_model = None


def get_device():
    import torch
    if torch.backends.mps.is_available():
        return "mps"
    elif torch.cuda.is_available():
        return "cuda"
    return "cpu"


def _find_bundled_xtts():
    """Check for bundled XTTS v2 model in models/xtts_v2/."""
    model_dir = MODELS_DIR / "xtts_v2"
    config_file = model_dir / "config.json"
    if config_file.exists():
        return str(model_dir)
    return None


def _find_bundled_whisper(model_size="medium"):
    """Check for bundled Whisper model in models/whisper/."""
    model_file = MODELS_DIR / "whisper" / f"{model_size}.pt"
    if model_file.exists():
        return str(model_file)
    return None


def get_tts(callback=None):
    global _tts_model
    if _tts_model is None:
        from TTS.api import TTS
        device = get_device()

        bundled = _find_bundled_xtts()
        if bundled:
            if callback:
                callback("📦 Завантажую вбудовану XTTS v2...")
            config_path = os.path.join(bundled, "config.json")
            _tts_model = TTS(model_path=bundled, config_path=config_path).to(device)
        else:
            if callback:
                callback("📥 Завантажую XTTS v2 (~1.8 GB)...")
            _tts_model = TTS("tts_models/multilingual/multi-dataset/xtts_v2").to(device)

        if callback:
            callback("✅ XTTS v2 готова!")
    return _tts_model


def get_whisper(model_size="medium", callback=None):
    global _whisper_model
    if _whisper_model is None:
        import whisper

        bundled = _find_bundled_whisper(model_size)
        if bundled:
            if callback:
                callback(f"📦 Завантажую вбудований Whisper {model_size}...")
            import torch
            # Load from bundled .pt file directly
            _whisper_model = whisper.load_model(model_size, download_root=str(MODELS_DIR / "whisper"))
        else:
            if callback:
                callback(f"📥 Завантажую Whisper {model_size} (~1.5 GB)...")
            _whisper_model = whisper.load_model(model_size)

        if callback:
            callback("✅ Whisper готовий!")
    return _whisper_model


# ── Colors ────────────────────────────────────────────────────
class Theme:
    BG = "#1a1a2e"
    BG_CARD = "#16213e"
    BG_INPUT = "#0f3460"
    BG_HOVER = "#1a4080"
    ACCENT = "#e94560"
    ACCENT_HOVER = "#ff6b81"
    SUCCESS = "#2ecc71"
    WARNING = "#f39c12"
    TEXT = "#eaeaea"
    TEXT_DIM = "#8899aa"
    TEXT_DARK = "#556677"
    BORDER = "#233554"
    PURPLE = "#a855f7"
    PURPLE_HOVER = "#c084fc"


# ── Main App ──────────────────────────────────────────────────
class VoiceClonerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("720x780")
        self.root.minsize(640, 700)
        self.root.configure(bg=Theme.BG)

        # State
        self.voice_sample_path = tk.StringVar(value="")
        self.is_recording = False
        self.recording_data = []
        self.current_output = None
        self.is_processing = False

        # macOS menu bar
        self._setup_menu()

        # Build UI
        self._build_ui()

        # Drag & drop hint
        self.root.after(100, self._check_args)

    # ── Menu Bar ──────────────────────────────────────────────
    def _setup_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Cut", accelerator="⌘X",
                             command=lambda: self.root.focus_get().event_generate("<<Cut>>"))
        edit_menu.add_command(label="Copy", accelerator="⌘C",
                             command=lambda: self.root.focus_get().event_generate("<<Copy>>"))
        edit_menu.add_command(label="Paste", accelerator="⌘V",
                             command=lambda: self.root.focus_get().event_generate("<<Paste>>"))
        edit_menu.add_command(label="Select All", accelerator="⌘A",
                             command=lambda: self.root.focus_get().event_generate("<<SelectAll>>"))

    def _check_args(self):
        if len(sys.argv) > 1 and Path(sys.argv[1]).exists():
            self.voice_sample_path.set(sys.argv[1])
            self._update_voice_label()

    # ── Build UI ──────────────────────────────────────────────
    def _build_ui(self):
        # Main scrollable area
        main = tk.Frame(self.root, bg=Theme.BG)
        main.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Header
        self._build_header(main)

        # Voice sample section
        self._build_voice_section(main)

        # Notebook (tabs)
        self._build_tabs(main)

        # Status bar
        self._build_status(main)

    def _build_header(self, parent):
        hdr = tk.Frame(parent, bg=Theme.BG)
        hdr.pack(fill=tk.X, pady=(5, 15))

        tk.Label(hdr, text="🎙", font=("SF Pro Display", 32),
                 bg=Theme.BG, fg=Theme.TEXT).pack(side=tk.LEFT, padx=(0, 10))

        title_frame = tk.Frame(hdr, bg=Theme.BG)
        title_frame.pack(side=tk.LEFT)

        tk.Label(title_frame, text="Voice Cloner",
                 font=("SF Pro Display", 22, "bold"),
                 bg=Theme.BG, fg=Theme.TEXT).pack(anchor="w")

        tk.Label(title_frame, text="XTTS v2 + Whisper · Apple Silicon",
                 font=("SF Pro Text", 11),
                 bg=Theme.BG, fg=Theme.TEXT_DIM).pack(anchor="w")

    # ── Voice Sample ──────────────────────────────────────────
    def _build_voice_section(self, parent):
        card = tk.Frame(parent, bg=Theme.BG_CARD, highlightbackground=Theme.BORDER,
                        highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 12))

        inner = tk.Frame(card, bg=Theme.BG_CARD)
        inner.pack(fill=tk.X, padx=16, pady=14)

        tk.Label(inner, text="🎤 Зразок голосу",
                 font=("SF Pro Text", 13, "bold"),
                 bg=Theme.BG_CARD, fg=Theme.TEXT).pack(anchor="w")

        tk.Label(inner, text="30-60 секунд чистого мовлення для клонування",
                 font=("SF Pro Text", 10),
                 bg=Theme.BG_CARD, fg=Theme.TEXT_DIM).pack(anchor="w", pady=(2, 10))

        # Voice file label
        self.voice_label = tk.Label(inner, text="Файл не обрано",
                                    font=("SF Mono", 11),
                                    bg=Theme.BG_INPUT, fg=Theme.TEXT_DIM,
                                    padx=12, pady=8, anchor="w")
        self.voice_label.pack(fill=tk.X, pady=(0, 10))

        # Buttons row
        btn_row = tk.Frame(inner, bg=Theme.BG_CARD)
        btn_row.pack(fill=tk.X)

        self._make_button(btn_row, "📁 Обрати файл", self._pick_voice_file,
                          Theme.BG_INPUT, Theme.BG_HOVER).pack(side=tk.LEFT, padx=(0, 8))

        self.record_btn = self._make_button(btn_row, "⏺ Записати", self._toggle_recording,
                                            Theme.ACCENT, Theme.ACCENT_HOVER)
        self.record_btn.pack(side=tk.LEFT, padx=(0, 8))

        self._make_button(btn_row, "📂 Папка samples", self._open_samples_folder,
                          Theme.BG_INPUT, Theme.BG_HOVER).pack(side=tk.LEFT)

        # Recording timer
        self.rec_timer_label = tk.Label(inner, text="",
                                        font=("SF Mono", 11),
                                        bg=Theme.BG_CARD, fg=Theme.ACCENT)
        self.rec_timer_label.pack(anchor="w", pady=(6, 0))

    # ── Tabs ──────────────────────────────────────────────────
    def _build_tabs(self, parent):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Custom.TNotebook", background=Theme.BG, borderwidth=0)
        style.configure("Custom.TNotebook.Tab",
                        background=Theme.BG_CARD, foreground=Theme.TEXT_DIM,
                        padding=[16, 8], font=("SF Pro Text", 12))
        style.map("Custom.TNotebook.Tab",
                  background=[("selected", Theme.BG_INPUT)],
                  foreground=[("selected", Theme.TEXT)])

        nb = ttk.Notebook(parent, style="Custom.TNotebook")
        nb.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Clone tab
        clone_frame = tk.Frame(nb, bg=Theme.BG)
        nb.add(clone_frame, text="  🗣 Clone  ")
        self._build_clone_tab(clone_frame)

        # STS tab
        sts_frame = tk.Frame(nb, bg=Theme.BG)
        nb.add(sts_frame, text="  🔄 STS  ")
        self._build_sts_tab(sts_frame)

    def _build_clone_tab(self, parent):
        card = tk.Frame(parent, bg=Theme.BG_CARD, highlightbackground=Theme.BORDER,
                        highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True, padx=2, pady=10)

        inner = tk.Frame(card, bg=Theme.BG_CARD)
        inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=14)

        tk.Label(inner, text="Текст для озвучення",
                 font=("SF Pro Text", 12, "bold"),
                 bg=Theme.BG_CARD, fg=Theme.TEXT).pack(anchor="w", pady=(0, 6))

        self.clone_text = tk.Text(inner, height=6, font=("SF Pro Text", 12),
                                  bg=Theme.BG_INPUT, fg=Theme.TEXT,
                                  insertbackground=Theme.TEXT,
                                  selectbackground=Theme.ACCENT,
                                  relief="flat", padx=10, pady=8,
                                  wrap="word")
        self.clone_text.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        self.clone_text.insert("1.0", "Привіт! Це тестове повідомлення для клонування голосу.")

        # Language selector
        lang_row = tk.Frame(inner, bg=Theme.BG_CARD)
        lang_row.pack(fill=tk.X, pady=(0, 12))

        tk.Label(lang_row, text="🌐 Мова:", font=("SF Pro Text", 11),
                 bg=Theme.BG_CARD, fg=Theme.TEXT).pack(side=tk.LEFT, padx=(0, 8))

        self.clone_lang = ttk.Combobox(lang_row, values=["uk", "en", "de", "fr", "es", "it", "pl", "pt"],
                                       state="readonly", width=6, font=("SF Pro Text", 11))
        self.clone_lang.set("uk")
        self.clone_lang.pack(side=tk.LEFT)

        # Generate button
        self.clone_btn = self._make_button(inner, "✨ Згенерувати", self._run_clone,
                                           Theme.PURPLE, Theme.PURPLE_HOVER)
        self.clone_btn.pack(fill=tk.X, ipady=6)

    def _build_sts_tab(self, parent):
        card = tk.Frame(parent, bg=Theme.BG_CARD, highlightbackground=Theme.BORDER,
                        highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True, padx=2, pady=10)

        inner = tk.Frame(card, bg=Theme.BG_CARD)
        inner.pack(fill=tk.BOTH, expand=True, padx=16, pady=14)

        tk.Label(inner, text="Аудіо для конвертації",
                 font=("SF Pro Text", 12, "bold"),
                 bg=Theme.BG_CARD, fg=Theme.TEXT).pack(anchor="w", pady=(0, 6))

        tk.Label(inner, text="Оберіть брудний/шумний запис для перегенерації чистим голосом",
                 font=("SF Pro Text", 10),
                 bg=Theme.BG_CARD, fg=Theme.TEXT_DIM).pack(anchor="w", pady=(0, 8))

        # Input file
        input_row = tk.Frame(inner, bg=Theme.BG_CARD)
        input_row.pack(fill=tk.X, pady=(0, 10))

        self.sts_input_label = tk.Label(input_row, text="Файл не обрано",
                                        font=("SF Mono", 11),
                                        bg=Theme.BG_INPUT, fg=Theme.TEXT_DIM,
                                        padx=12, pady=8, anchor="w")
        self.sts_input_label.pack(fill=tk.X, side=tk.TOP, pady=(0, 8))

        self._make_button(input_row, "📁 Обрати аудіо", self._pick_sts_input,
                          Theme.BG_INPUT, Theme.BG_HOVER).pack(anchor="w")

        self.sts_input_path = ""

        # Whisper model
        whisper_row = tk.Frame(inner, bg=Theme.BG_CARD)
        whisper_row.pack(fill=tk.X, pady=(5, 5))

        tk.Label(whisper_row, text="🧠 Whisper:", font=("SF Pro Text", 11),
                 bg=Theme.BG_CARD, fg=Theme.TEXT).pack(side=tk.LEFT, padx=(0, 8))

        self.sts_whisper = ttk.Combobox(whisper_row,
                                        values=["tiny", "base", "small", "medium", "large"],
                                        state="readonly", width=10, font=("SF Pro Text", 11))
        self.sts_whisper.set("medium")
        self.sts_whisper.pack(side=tk.LEFT)

        tk.Label(whisper_row, text="(medium — оптимальний баланс)",
                 font=("SF Pro Text", 10),
                 bg=Theme.BG_CARD, fg=Theme.TEXT_DIM).pack(side=tk.LEFT, padx=(8, 0))

        # Language
        lang_row = tk.Frame(inner, bg=Theme.BG_CARD)
        lang_row.pack(fill=tk.X, pady=(5, 12))

        tk.Label(lang_row, text="🌐 Мова:", font=("SF Pro Text", 11),
                 bg=Theme.BG_CARD, fg=Theme.TEXT).pack(side=tk.LEFT, padx=(0, 8))

        self.sts_lang = ttk.Combobox(lang_row, values=["uk", "en", "de", "fr", "es", "it", "pl", "pt"],
                                     state="readonly", width=6, font=("SF Pro Text", 11))
        self.sts_lang.set("uk")
        self.sts_lang.pack(side=tk.LEFT)

        # Transcription preview
        tk.Label(inner, text="Транскрипція (можна редагувати):",
                 font=("SF Pro Text", 11),
                 bg=Theme.BG_CARD, fg=Theme.TEXT_DIM).pack(anchor="w", pady=(5, 4))

        self.sts_transcript = tk.Text(inner, height=4, font=("SF Pro Text", 11),
                                      bg=Theme.BG_INPUT, fg=Theme.TEXT,
                                      insertbackground=Theme.TEXT,
                                      selectbackground=Theme.ACCENT,
                                      relief="flat", padx=10, pady=6,
                                      wrap="word")
        self.sts_transcript.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        # Buttons
        btn_row = tk.Frame(inner, bg=Theme.BG_CARD)
        btn_row.pack(fill=tk.X)

        self.sts_transcribe_btn = self._make_button(btn_row, "📝 Транскрибувати",
                                                     self._run_transcribe,
                                                     Theme.BG_INPUT, Theme.BG_HOVER)
        self.sts_transcribe_btn.pack(side=tk.LEFT, padx=(0, 8), fill=tk.X, expand=True)

        self.sts_generate_btn = self._make_button(btn_row, "✨ Згенерувати",
                                                   self._run_sts_generate,
                                                   Theme.PURPLE, Theme.PURPLE_HOVER)
        self.sts_generate_btn.pack(side=tk.LEFT, fill=tk.X, expand=True)

    # ── Status Bar ────────────────────────────────────────────
    def _build_status(self, parent):
        status_frame = tk.Frame(parent, bg=Theme.BG_CARD, highlightbackground=Theme.BORDER,
                                highlightthickness=1)
        status_frame.pack(fill=tk.X, pady=(0, 5))

        inner = tk.Frame(status_frame, bg=Theme.BG_CARD)
        inner.pack(fill=tk.X, padx=14, pady=10)

        # Progress bar
        style = ttk.Style()
        style.configure("Custom.Horizontal.TProgressbar",
                        troughcolor=Theme.BG_INPUT,
                        background=Theme.ACCENT,
                        borderwidth=0, thickness=6)

        self.progress = ttk.Progressbar(inner, mode="indeterminate",
                                         style="Custom.Horizontal.TProgressbar")
        self.progress.pack(fill=tk.X, pady=(0, 6))

        # Status + result row
        bottom_row = tk.Frame(inner, bg=Theme.BG_CARD)
        bottom_row.pack(fill=tk.X)

        self.status_label = tk.Label(bottom_row, text="⏳ Готовий до роботи",
                                     font=("SF Pro Text", 11),
                                     bg=Theme.BG_CARD, fg=Theme.TEXT_DIM,
                                     anchor="w")
        self.status_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.play_btn = self._make_button(bottom_row, "▶️ Відтворити", self._play_result,
                                          Theme.SUCCESS, "#27ae60")
        self.play_btn.pack(side=tk.RIGHT, padx=(8, 0))
        self.play_btn.pack_forget()  # hidden initially

        self.open_btn = self._make_button(bottom_row, "📂 Показати", self._open_output_folder,
                                          Theme.BG_INPUT, Theme.BG_HOVER)
        self.open_btn.pack(side=tk.RIGHT)
        self.open_btn.pack_forget()

    # ── Button helper ─────────────────────────────────────────
    def _make_button(self, parent, text, command, bg, bg_hover):
        btn = tk.Label(parent, text=text, font=("SF Pro Text", 12, "bold"),
                       bg=bg, fg="white", padx=14, pady=6, cursor="hand2")
        btn.bind("<Button-1>", lambda e: command())
        btn.bind("<Enter>", lambda e: btn.config(bg=bg_hover))
        btn.bind("<Leave>", lambda e: btn.config(bg=bg))
        btn._bg = bg
        btn._bg_hover = bg_hover
        return btn

    def _set_button_enabled(self, btn, enabled):
        if enabled:
            btn.config(fg="white", cursor="hand2", bg=btn._bg)
            btn.bind("<Button-1>", lambda e: None)  # will be re-bound
        else:
            btn.config(fg=Theme.TEXT_DARK, cursor="", bg=Theme.TEXT_DARK)

    # ── Voice file picker ─────────────────────────────────────
    def _pick_voice_file(self):
        path = filedialog.askopenfilename(
            title="Оберіть зразок голосу",
            initialdir=str(SAMPLES_DIR),
            filetypes=[("Audio", "*.wav *.mp3 *.flac *.m4a *.ogg *.aac"),
                       ("All", "*.*")]
        )
        if path:
            self.voice_sample_path.set(path)
            self._update_voice_label()

    def _update_voice_label(self):
        p = Path(self.voice_sample_path.get())
        if p.exists():
            size = p.stat().st_size / (1024 * 1024)
            self.voice_label.config(text=f"✅ {p.name} ({size:.1f} MB)",
                                    fg=Theme.SUCCESS)
        else:
            self.voice_label.config(text="Файл не обрано", fg=Theme.TEXT_DIM)

    def _pick_sts_input(self):
        path = filedialog.askopenfilename(
            title="Оберіть аудіо для конвертації",
            filetypes=[("Audio", "*.wav *.mp3 *.flac *.m4a *.ogg *.aac"),
                       ("All", "*.*")]
        )
        if path:
            self.sts_input_path = path
            p = Path(path)
            size = p.stat().st_size / (1024 * 1024)
            self.sts_input_label.config(text=f"✅ {p.name} ({size:.1f} MB)",
                                        fg=Theme.SUCCESS)

    def _open_samples_folder(self):
        subprocess.run(["open", str(SAMPLES_DIR)])

    def _open_output_folder(self):
        if self.current_output and Path(self.current_output).exists():
            subprocess.run(["open", "-R", self.current_output])
        else:
            subprocess.run(["open", str(OUTPUT_DIR)])

    # ── Recording ─────────────────────────────────────────────
    def _toggle_recording(self):
        if self.is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        try:
            import sounddevice as sd
            import numpy as np
        except ImportError:
            messagebox.showerror("Помилка", "Встановіть sounddevice:\npip install sounddevice")
            return

        self.is_recording = True
        self.recording_data = []
        self.rec_start_time = time.time()

        self.record_btn.config(text="⏹ Зупинити", bg="#e74c3c")

        self.sample_rate = 44100

        def callback(indata, frames, time_info, status):
            if self.is_recording:
                self.recording_data.append(indata.copy())

        try:
            self.rec_stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                callback=callback
            )
            self.rec_stream.start()
            self._update_rec_timer()
            self._set_status("⏺ Запис...")
        except Exception as e:
            self.is_recording = False
            self.record_btn.config(text="⏺ Записати", bg=Theme.ACCENT)
            messagebox.showerror("Помилка мікрофону", str(e))

    def _update_rec_timer(self):
        if self.is_recording:
            elapsed = time.time() - self.rec_start_time
            self.rec_timer_label.config(text=f"⏺ {elapsed:.0f}с")
            self.root.after(200, self._update_rec_timer)

    def _stop_recording(self):
        self.is_recording = False
        self.record_btn.config(text="⏺ Записати", bg=Theme.ACCENT)

        if hasattr(self, "rec_stream"):
            self.rec_stream.stop()
            self.rec_stream.close()

        if not self.recording_data:
            self.rec_timer_label.config(text="")
            return

        import numpy as np
        import soundfile as sf

        audio = np.concatenate(self.recording_data, axis=0)
        duration = len(audio) / self.sample_rate

        # Save
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = SAMPLES_DIR / f"recording_{timestamp}.wav"
        sf.write(str(output_path), audio, self.sample_rate)

        self.voice_sample_path.set(str(output_path))
        self._update_voice_label()
        self.rec_timer_label.config(text=f"✅ Записано {duration:.0f}с → {output_path.name}")
        self._set_status(f"✅ Голос записано ({duration:.0f}с)")

    # ── Status helpers ────────────────────────────────────────
    def _set_status(self, text, color=None):
        self.status_label.config(text=text, fg=color or Theme.TEXT_DIM)

    def _start_progress(self):
        self.progress.start(15)
        self.is_processing = True

    def _stop_progress(self):
        self.progress.stop()
        self.is_processing = False

    def _show_result(self, path):
        self.current_output = path
        self.play_btn.pack(side=tk.RIGHT, padx=(8, 0))
        self.open_btn.pack(side=tk.RIGHT)

    def _play_result(self):
        if self.current_output and Path(self.current_output).exists():
            subprocess.run(["open", self.current_output])

    # ── Validate voice sample ─────────────────────────────────
    def _validate_voice(self):
        path = self.voice_sample_path.get()
        if not path or not Path(path).exists():
            messagebox.showwarning("Зразок голосу",
                                   "Спочатку оберіть або запишіть зразок голосу!")
            return None
        return path

    # ── Clone ─────────────────────────────────────────────────
    def _run_clone(self):
        if self.is_processing:
            return

        voice = self._validate_voice()
        if not voice:
            return

        text = self.clone_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Текст", "Введіть текст для озвучення!")
            return

        lang = self.clone_lang.get()

        def worker():
            try:
                self.root.after(0, lambda: self._start_progress())
                self.root.after(0, lambda: self._set_status("🔄 Завантажую модель..."))

                tts = get_tts(callback=lambda msg: self.root.after(0, lambda: self._set_status(msg)))

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = str(OUTPUT_DIR / f"clone_{timestamp}.wav")

                self.root.after(0, lambda: self._set_status("🔄 Генерую мовлення..."))

                tts.tts_to_file(
                    text=text,
                    speaker_wav=voice,
                    language=lang,
                    file_path=output_path,
                )

                size = Path(output_path).stat().st_size / (1024 * 1024)
                self.root.after(0, lambda: self._stop_progress())
                self.root.after(0, lambda: self._set_status(
                    f"✅ Готово! {Path(output_path).name} ({size:.1f} MB)", Theme.SUCCESS))
                self.root.after(0, lambda: self._show_result(output_path))

            except Exception as e:
                self.root.after(0, lambda: self._stop_progress())
                self.root.after(0, lambda: self._set_status(f"❌ {e}", Theme.ACCENT))

        threading.Thread(target=worker, daemon=True).start()

    # ── STS: Transcribe ──────────────────────────────────────
    def _run_transcribe(self):
        if self.is_processing:
            return

        if not self.sts_input_path or not Path(self.sts_input_path).exists():
            messagebox.showwarning("Файл", "Оберіть аудіофайл для транскрипції!")
            return

        whisper_size = self.sts_whisper.get()
        lang = self.sts_lang.get()

        def worker():
            try:
                self.root.after(0, lambda: self._start_progress())
                self.root.after(0, lambda: self._set_status("🔄 Завантажую Whisper..."))

                model = get_whisper(whisper_size,
                                    callback=lambda msg: self.root.after(0, lambda: self._set_status(msg)))

                self.root.after(0, lambda: self._set_status("🔄 Розпізнаю мовлення..."))

                result = model.transcribe(self.sts_input_path, language=lang)
                transcript = result["text"].strip()

                self.root.after(0, lambda: self._stop_progress())
                self.root.after(0, lambda: self._insert_transcript(transcript))
                self.root.after(0, lambda: self._set_status(
                    f"✅ Транскрибовано ({len(transcript)} символів)", Theme.SUCCESS))

            except Exception as e:
                self.root.after(0, lambda: self._stop_progress())
                self.root.after(0, lambda: self._set_status(f"❌ {e}", Theme.ACCENT))

        threading.Thread(target=worker, daemon=True).start()

    def _insert_transcript(self, text):
        self.sts_transcript.delete("1.0", tk.END)
        self.sts_transcript.insert("1.0", text)

    # ── STS: Generate ─────────────────────────────────────────
    def _run_sts_generate(self):
        if self.is_processing:
            return

        voice = self._validate_voice()
        if not voice:
            return

        transcript = self.sts_transcript.get("1.0", tk.END).strip()
        if not transcript:
            messagebox.showwarning("Транскрипція",
                                   "Спочатку транскрибуйте аудіо або введіть текст вручну!")
            return

        lang = self.sts_lang.get()

        def worker():
            try:
                self.root.after(0, lambda: self._start_progress())
                self.root.after(0, lambda: self._set_status("🔄 Завантажую XTTS v2..."))

                tts = get_tts(callback=lambda msg: self.root.after(0, lambda: self._set_status(msg)))

                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                output_path = str(OUTPUT_DIR / f"sts_{timestamp}.wav")

                self.root.after(0, lambda: self._set_status("🔄 Перегенерую голос..."))

                tts.tts_to_file(
                    text=transcript,
                    speaker_wav=voice,
                    language=lang,
                    file_path=output_path,
                )

                size = Path(output_path).stat().st_size / (1024 * 1024)
                self.root.after(0, lambda: self._stop_progress())
                self.root.after(0, lambda: self._set_status(
                    f"✅ Готово! {Path(output_path).name} ({size:.1f} MB)", Theme.SUCCESS))
                self.root.after(0, lambda: self._show_result(output_path))

            except Exception as e:
                self.root.after(0, lambda: self._stop_progress())
                self.root.after(0, lambda: self._set_status(f"❌ {e}", Theme.ACCENT))

        threading.Thread(target=worker, daemon=True).start()

    # ── Run ───────────────────────────────────────────────────
    def run(self):
        self.root.mainloop()


# ── Entry Point ───────────────────────────────────────────────
if __name__ == "__main__":
    app = VoiceClonerApp()
    app.run()
