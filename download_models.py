#!/usr/bin/env python3
"""
Pre-downloads XTTS v2 and Whisper models into a local 'models/' directory
for bundling inside the .app.
"""

import os
import sys
import ssl
import shutil
from pathlib import Path

# Fix macOS SSL certificate errors
ssl._create_default_https_context = ssl._create_unverified_context

# Patch: bypass torchcodec check + add back isin_mps_friendly for transformers 5.x
import os as _os
_os.environ["COQUI_TTS_SKIP_TORCHCODEC"] = "1"
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
    try:
        import torchcodec  # noqa
    except ImportError:
        import types
        sys.modules["torchcodec"] = types.ModuleType("torchcodec")
_patch_transformers()

SCRIPT_DIR = Path(__file__).parent.resolve()
MODELS_DIR = SCRIPT_DIR / "models"


def download_xtts():
    """Download XTTS v2 model files to models/xtts_v2/"""
    print("📥 Завантажую XTTS v2 (~1.8 GB)...")
    from TTS.api import TTS

    # Initialize TTS — this triggers the download to ~/.local/share/tts/
    tts = TTS("tts_models/multilingual/multi-dataset/xtts_v2")

    # Find cached model path
    from TTS.utils.manage import ModelManager
    manager = ModelManager()
    model_path, _, _ = manager.download_model("tts_models/multilingual/multi-dataset/xtts_v2")
    model_dir = Path(model_path).parent

    # Copy to local models/ directory
    dest = MODELS_DIR / "xtts_v2"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(str(model_dir), str(dest))
    print(f"✅ XTTS v2 скопійовано → {dest}")
    return dest


def download_whisper(model_size="medium"):
    """Download Whisper model to models/whisper/"""
    print(f"📥 Завантажую Whisper {model_size} (~1.5 GB)...")
    import whisper

    # This downloads to ~/.cache/whisper/
    model = whisper.load_model(model_size)

    # Find the cached file
    cache_dir = Path.home() / ".cache" / "whisper"
    model_file = cache_dir / f"{model_size}.pt"

    if not model_file.exists():
        # Try alternative naming
        for f in cache_dir.iterdir():
            if model_size in f.name:
                model_file = f
                break

    dest = MODELS_DIR / "whisper"
    dest.mkdir(parents=True, exist_ok=True)

    dest_file = dest / f"{model_size}.pt"
    shutil.copy2(str(model_file), str(dest_file))
    print(f"✅ Whisper {model_size} скопійовано → {dest_file}")
    return dest_file


def main():
    MODELS_DIR.mkdir(exist_ok=True)

    print("=" * 50)
    print("📦 Завантажую моделі для вбудовування в .app")
    print("=" * 50)
    print()

    download_xtts()
    print()
    download_whisper("medium")
    print()

    # Show sizes
    total = 0
    for f in MODELS_DIR.rglob("*"):
        if f.is_file():
            total += f.stat().st_size

    print(f"📊 Загальний розмір моделей: {total / (1024**3):.1f} GB")
    print(f"📂 Розташування: {MODELS_DIR}")
    print("✅ Готово! Тепер запустіть ./build_app.sh")


if __name__ == "__main__":
    main()
