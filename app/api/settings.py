"""Ayarlar, Hugging Face belirteci testi ve dil listesi."""
from __future__ import annotations

import urllib.error
import urllib.request
from pathlib import Path

from fastapi import APIRouter, HTTPException

from .. import config
from ..languages import language_list

router = APIRouter(prefix="/api")

GATED = ["pyannote/speaker-diarization-3.1", "pyannote/segmentation-3.0"]


def _validate(body: dict) -> dict:
    out: dict = {}
    d = config.DEFAULTS
    if "language" in body:
        from ..languages import LANGUAGES
        if body["language"] != "auto" and body["language"] not in LANGUAGES:
            raise HTTPException(400, "Geçersiz dil.")
        out["language"] = body["language"]
    if "model" in body:
        if body["model"] not in config.MODELS:
            raise HTTPException(400, "Geçersiz model.")
        out["model"] = body["model"]
    if "compute_type" in body:
        if body["compute_type"] not in config.COMPUTE_TYPES:
            raise HTTPException(400, "Geçersiz hesaplama türü.")
        out["compute_type"] = body["compute_type"]
    if "device" in body:
        if body["device"] not in ("auto", "cuda", "cpu"):
            raise HTTPException(400, "Geçersiz aygıt.")
        out["device"] = body["device"]
    if "task" in body:
        if body["task"] not in ("transcribe", "translate"):
            raise HTTPException(400, "Geçersiz görev.")
        out["task"] = body["task"]
    if "batch_size" in body:
        try:
            out["batch_size"] = max(1, min(64, int(body["batch_size"])))
        except (TypeError, ValueError):
            raise HTTPException(400, "Toplu işlem boyutu sayı olmalı.")
    if "max_upload_mb" in body:
        try:
            out["max_upload_mb"] = max(1, min(102400, int(body["max_upload_mb"])))
        except (TypeError, ValueError):
            raise HTTPException(400, "En büyük yükleme boyutu sayı olmalı.")
    for k in ("vad", "align", "diarize", "bom", "allow_lan"):
        if k in body:
            out[k] = bool(body[k])
    if "csv_delimiter" in body:
        if body["csv_delimiter"] not in (";", ",", "\t"):
            raise HTTPException(400, "Geçersiz CSV ayırıcı.")
        out["csv_delimiter"] = body["csv_delimiter"]
    if "diarization_model" in body:
        out["diarization_model"] = str(body["diarization_model"]).strip() or d["diarization_model"]
    if "hf_token" in body and body["hf_token"] is not None:
        out["hf_token"] = str(body["hf_token"]).strip()
    if isinstance(body.get("subtitle"), dict):
        sub = body["subtitle"]
        clean = {}
        try:
            if "max_chars" in sub:
                clean["max_chars"] = max(10, min(120, int(sub["max_chars"])))
            if "max_lines" in sub:
                clean["max_lines"] = max(1, min(4, int(sub["max_lines"])))
            if "max_dur" in sub:
                clean["max_dur"] = max(1.0, min(30.0, float(sub["max_dur"])))
            if "min_dur" in sub:
                clean["min_dur"] = max(0.0, min(10.0, float(sub["min_dur"])))
        except (TypeError, ValueError):
            raise HTTPException(400, "Altyazı kuralları sayı olmalı.")
        if "speaker_prefix" in sub:
            clean["speaker_prefix"] = bool(sub["speaker_prefix"])
        out["subtitle"] = clean
    return out


def _state() -> dict:
    s = config.public(config.load())
    s["data_dir"] = str(config.data_dir())
    pending = config.get_bootstrap_dir()
    s["data_dir_pending"] = pending if pending and str(Path(pending)) != str(config.data_dir()) else None
    s["models"] = config.MODELS
    s["compute_types"] = config.COMPUTE_TYPES
    return s


@router.get("/settings")
def get_settings():
    return _state()


@router.put("/settings")
def put_settings(body: dict):
    values = _validate(body)
    if "min_dur" in values.get("subtitle", {}) and "max_dur" in values.get("subtitle", {}):
        if values["subtitle"]["min_dur"] > values["subtitle"]["max_dur"]:
            raise HTTPException(400, "En kısa süre, en uzun süreden büyük olamaz.")
    restart = False
    if "data_dir" in body:
        new = str(body["data_dir"] or "").strip()
        if new:
            try:
                Path(new).mkdir(parents=True, exist_ok=True)
            except OSError:
                raise HTTPException(400, "Klasör oluşturulamadı. Yolu kontrol edin.")
        config.set_bootstrap_dir(new or None)
        restart = True
    config.save(values)
    state = _state()
    state["restart_required"] = restart or "allow_lan" in values
    return state


def _head(url: str, token: str) -> int:
    req = urllib.request.Request(url, method="HEAD", headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


@router.post("/settings/hf-test")
def hf_test(body: dict):
    token = (body.get("token") or "").strip() or config.load()["hf_token"]
    if not token:
        return {"ok": False, "message": "Henüz bir belirteç girilmedi."}
    try:
        who = _head("https://huggingface.co/api/whoami-v2", token)
        if who in (401, 403):
            return {"ok": False, "message": "Belirteç geçersiz. Lütfen yeniden kopyalayıp deneyin."}
        for repo in GATED:
            code = _head(f"https://huggingface.co/{repo}/resolve/main/config.yaml", token)
            if code == 403:
                return {"ok": False, "message": f"Belirteç geçerli, ancak '{repo}' sayfasındaki koşullar henüz kabul edilmemiş."}
            if code >= 400 and code != 404:
                return {"ok": False, "message": "Hugging Face beklenmedik bir yanıt verdi. Biraz sonra yeniden deneyin."}
    except (urllib.error.URLError, TimeoutError, OSError):
        return {"ok": False, "message": "Hugging Face'e ulaşılamadı. İnternet bağlantınızı kontrol edin."}
    return {"ok": True, "message": "Belirteç geçerli ve konuşmacı modeli koşulları kabul edilmiş."}


@router.get("/languages")
def languages():
    return {"languages": language_list()}
