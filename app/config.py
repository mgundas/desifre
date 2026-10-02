"""Ayarların yüklenmesi ve kaydedilmesi (JSON dosyası)."""
from __future__ import annotations

import copy
import json
import os
import threading
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
BOOTSTRAP = APP_DIR / "bootstrap.json"
PORT = int(os.environ.get("DESIFRE_PORT", "7860"))

AUDIO_EXTS = {"mp3", "wav", "m4a", "aac", "ogg", "opus", "flac", "wma"}
VIDEO_EXTS = {"mp4", "mkv", "mov", "webm", "avi"}
ALLOWED_EXTS = AUDIO_EXTS | VIDEO_EXTS
MODELS = ["large-v3", "large-v3-turbo", "medium", "small", "base", "tiny"]
COMPUTE_TYPES = ["auto", "int8_float16", "float16", "int8", "float32"]

DEFAULTS: dict = {
    "language": "tr",
    "model": "large-v3",
    "compute_type": "auto",
    "batch_size": 8,
    "device": "auto",
    "vad": True,
    "align": True,
    "diarize": False,
    "task": "transcribe",
    "hf_token": "",
    "diarization_model": "pyannote/speaker-diarization-3.1",
    "bom": True,
    "csv_delimiter": ";",
    "allow_lan": False,
    "max_upload_mb": 4096,
    "subtitle": {"max_chars": 42, "max_lines": 2, "max_dur": 7.0, "min_dur": 1.0, "speaker_prefix": False},
}

_lock = threading.Lock()


def data_dir() -> Path:
    env = os.environ.get("DESIFRE_DATA")
    p = Path(env) if env else APP_DIR / "data"
    if not env and BOOTSTRAP.exists():
        try:
            d = json.loads(BOOTSTRAP.read_text(encoding="utf-8")).get("data_dir")
            if d:
                p = Path(d)
        except (OSError, ValueError):
            pass
    p.mkdir(parents=True, exist_ok=True)
    return p


def uploads_dir() -> Path:
    p = data_dir() / "uploads"
    p.mkdir(parents=True, exist_ok=True)
    return p


def work_dir() -> Path:
    p = data_dir() / "work"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _settings_path() -> Path:
    return data_dir() / "settings.json"


def _merge(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in extra.items():
        if k not in base:
            continue
        if isinstance(base[k], dict) and isinstance(v, dict):
            out[k] = _merge(base[k], v)
        else:
            out[k] = v
    return out


def load() -> dict:
    with _lock:
        p = _settings_path()
        if p.exists():
            try:
                return _merge(DEFAULTS, json.loads(p.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                pass
        return copy.deepcopy(DEFAULTS)


def save(values: dict) -> dict:
    current = load()
    merged = _merge(current, values)
    with _lock:
        _settings_path().write_text(json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8")
    return merged


def public(settings: dict) -> dict:
    """Arayüze gönderilecek ayarlar: belirteç maskelenir."""
    out = copy.deepcopy(settings)
    token = out.pop("hf_token", "") or ""
    out["hf_token_set"] = bool(token)
    out["hf_token_masked"] = (token[:3] + "…" + token[-3:]) if len(token) > 8 else ("•" * len(token))
    return out


def get_bootstrap_dir() -> str | None:
    try:
        return json.loads(BOOTSTRAP.read_text(encoding="utf-8")).get("data_dir")
    except (OSError, ValueError):
        return None


def set_bootstrap_dir(path: str | None) -> None:
    data = {"data_dir": path} if path else {}
    BOOTSTRAP.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
