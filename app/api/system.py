"""Sistem bilgisi: GPU, ffmpeg, indirilmiş modeller, disk kullanımı."""
from __future__ import annotations

import os
import platform
import shutil
from pathlib import Path

from fastapi import APIRouter

from .. import config
from ..pipeline import audio, gpu

router = APIRouter(prefix="/api")

FALLBACK_REPOS = {
    "large-v3": "Systran/faster-whisper-large-v3", "large-v3-turbo": "mobiuslabs/faster-whisper-large-v3-turbo",
    "medium": "Systran/faster-whisper-medium", "small": "Systran/faster-whisper-small",
    "base": "Systran/faster-whisper-base", "tiny": "Systran/faster-whisper-tiny",
}


def model_repo(name: str) -> str:
    try:
        from faster_whisper.utils import _MODELS
        return _MODELS.get(name) or FALLBACK_REPOS[name]
    except Exception:
        return FALLBACK_REPOS[name]


def hf_cache_dir() -> Path:
    try:
        from huggingface_hub import constants
        return Path(constants.HF_HUB_CACHE)
    except Exception:
        return Path.home() / ".cache" / "huggingface" / "hub"


def dir_size(p: Path) -> int:
    total = 0
    for root, _, files in os.walk(p):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def downloaded_models() -> list[dict]:
    cache = hf_cache_dir()
    out = []
    for name in config.MODELS:
        d = cache / ("models--" + model_repo(name).replace("/", "--"))
        ok = any(d.glob("snapshots/*/model.bin")) if d.exists() else False
        out.append({"name": name, "downloaded": ok, "size": dir_size(d) if ok else 0})
    return out


@router.get("/system")
def system_info():
    info = gpu.gpu_info()
    cuda = gpu.cuda_available()
    ff = audio.ffmpeg_path()
    data = config.data_dir()
    usage = shutil.disk_usage(data)
    try:
        import ctranslate2
        ct2 = ctranslate2.__version__
    except Exception:
        ct2 = None
    try:
        import whisperx  # noqa: F401
        from importlib.metadata import version
        wx = version("whisperx")
    except Exception:
        wx = None
    return {
        "gpu": info, "cuda_available": cuda, "ffmpeg": bool(ff) and bool(audio.ffprobe_path()),
        "ffmpeg_path": ff, "models": downloaded_models(), "python": platform.python_version(),
        "ctranslate2": ct2, "whisperx": wx,
        "storage": {
            "path": str(data), "uploads_bytes": dir_size(config.uploads_dir()),
            "total_bytes": dir_size(data), "disk_free_bytes": usage.free, "disk_total_bytes": usage.total,
        },
    }
