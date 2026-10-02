"""Yükleme ve kuyruk uç noktaları."""
from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel

from .. import config, db, events
from ..languages import LANGUAGES
from ..util import safe_ext, sanitize_filename

router = APIRouter(prefix="/api")

CHUNK = 1024 * 1024


def clean_options(raw: dict, settings: dict) -> dict:
    """Yükleme seçeneklerini doğrular, eksikleri ayarlardan doldurur."""
    lang = raw.get("language", settings["language"])
    if lang != "auto" and lang not in LANGUAGES:
        raise HTTPException(400, "Geçersiz dil seçimi.")
    model = raw.get("model", settings["model"])
    if model not in config.MODELS:
        raise HTTPException(400, "Geçersiz model seçimi.")
    task = raw.get("task", settings["task"])
    if task not in ("transcribe", "translate"):
        raise HTTPException(400, "Geçersiz görev seçimi.")
    out = {
        "language": lang, "model": model, "task": task,
        "diarize": bool(raw.get("diarize", settings["diarize"])),
        "initial_prompt": str(raw.get("initial_prompt") or "")[:1000],
    }
    for key in ("min_speakers", "max_speakers"):
        v = raw.get(key)
        out[key] = int(v) if isinstance(v, (int, float)) and 1 <= int(v) <= 20 else None
    if out["min_speakers"] and out["max_speakers"] and out["min_speakers"] > out["max_speakers"]:
        raise HTTPException(400, "En az konuşmacı sayısı, en çok sayıdan büyük olamaz.")
    return out


@router.post("/jobs")
async def create_job(request: Request, filename: str, options: str = "{}"):
    """Ham gövde olarak tek dosya alır (akış halinde diske yazar) ve kuyruğa ekler."""
    settings = config.load()
    ext = safe_ext(filename, config.ALLOWED_EXTS)
    if not ext:
        raise HTTPException(415, "Dosya biçimi desteklenmiyor.")
    try:
        opts = clean_options(json.loads(options or "{}"), settings)
    except ValueError:
        raise HTTPException(400, "Seçenekler okunamadı.")
    max_bytes = int(settings["max_upload_mb"]) * 1024 * 1024
    declared = request.headers.get("content-length")
    if declared and declared.isdigit() and int(declared) > max_bytes:
        raise HTTPException(413, f"Dosya çok büyük. En çok {settings['max_upload_mb']} MB yüklenebilir.")

    rel = f"uploads/{uuid.uuid4().hex}.{ext}"
    dest = config.uploads_dir().parent / rel
    size = 0
    try:
        with open(dest, "wb") as f:
            async for chunk in request.stream():
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(413, f"Dosya çok büyük. En çok {settings['max_upload_mb']} MB yüklenebilir.")
                await run_in_threadpool(f.write, chunk)
        if size == 0:
            raise HTTPException(400, "Dosya boş.")
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    safe_name = sanitize_filename(Path(filename).name, default=f"kayit.{ext}")
    title = sanitize_filename(Path(safe_name).stem, default="Kayıt")
    job_id = db.create_job(safe_name, rel, size, opts, title)
    events.bump()
    request.app.state.worker.wake()
    return {"id": job_id}


@router.get("/jobs")
def list_jobs(scope: str = "queue"):
    if scope == "queue":
        return {"jobs": db.list_active(time.time() - 24 * 3600, include_failed=True)}
    return {"jobs": db.list_jobs()}


@router.get("/jobs/{job_id}")
def get_job(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "İş bulunamadı.")
    return job


@router.post("/jobs/reorder")
def reorder(body: dict):
    ids = body.get("ids")
    if not isinstance(ids, list):
        raise HTTPException(400, "Geçersiz sıralama.")
    db.reorder([str(i) for i in ids])
    events.bump()
    return {"ok": True}


@router.post("/jobs/{job_id}/cancel")
def cancel(job_id: str, request: Request):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "İş bulunamadı.")
    if db.cancel_queued(job_id) or request.app.state.worker.cancel_running(job_id):
        events.bump()
        return {"ok": True}
    raise HTTPException(409, "Bu iş artık iptal edilemez.")


@router.post("/jobs/{job_id}/retry")
def retry(job_id: str, request: Request):
    if not db.get_job(job_id):
        raise HTTPException(404, "İş bulunamadı.")
    if not db.retry_job(job_id):
        raise HTTPException(409, "Yalnızca başarısız ya da iptal edilmiş işler yeniden denenebilir.")
    events.bump()
    request.app.state.worker.wake()
    return {"ok": True}
