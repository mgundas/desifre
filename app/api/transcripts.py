"""Kütüphane, düzenleyici verisi, ortam dosyası ve dışa aktarma uç noktaları."""
from __future__ import annotations

import mimetypes
import re
import shutil
import time
import urllib.parse
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, Response

from .. import config, db, events
from ..export import docx_export, json_csv, srt_vtt, txt
from ..export.segmenter import Rules, build_cues
from ..util import sanitize_filename

router = APIRouter(prefix="/api")

_ASCII = str.maketrans("çğıöşüÇĞİÖŞÜâîûÂÎÛ", "cgiosuCGIOSUaiuAIU")
MAX_SEGMENTS = 50000


def clean_segments(raw) -> list[dict]:
    if not isinstance(raw, list) or len(raw) > MAX_SEGMENTS:
        raise HTTPException(400, "Bölümler geçersiz.")
    out = []
    for i, s in enumerate(raw):
        if not isinstance(s, dict):
            raise HTTPException(400, "Bölümler geçersiz.")
        try:
            start, end = float(s["start"]), float(s["end"])
        except (KeyError, TypeError, ValueError):
            raise HTTPException(400, "Bölüm zamanları geçersiz.")
        words = []
        for w in s.get("words") or []:
            try:
                words.append({
                    "word": str(w["word"]),
                    "start": None if w.get("start") is None else float(w["start"]),
                    "end": None if w.get("end") is None else float(w["end"]),
                    **({"score": float(w["score"])} if w.get("score") is not None else {}),
                })
            except (KeyError, TypeError, ValueError):
                continue
        spk = s.get("speaker")
        out.append({
            "id": str(s.get("id") or f"s{i}"), "start": start, "end": max(end, start),
            "speaker": str(spk) if spk else None, "text": str(s.get("text", "")), "words": words,
        })
    return out


def clean_speakers(raw) -> dict:
    if not isinstance(raw, dict):
        raise HTTPException(400, "Konuşmacılar geçersiz.")
    out = {}
    for k, v in raw.items():
        v = v if isinstance(v, dict) else {}
        color = str(v.get("color") or "")
        out[str(k)] = {"name": str(v.get("name") or "")[:80], "color": color if re.fullmatch(r"#[0-9a-fA-F]{6}", color) else ""}
    return out


@router.get("/transcripts")
def library(q: str = "", sort: str = "date", order: str = "desc"):
    return {"items": db.list_library(q, sort, order)}


@router.get("/transcripts/{tid}")
def get_transcript(tid: str):
    tr = db.get_transcript(tid)
    if not tr:
        raise HTTPException(404, "Kayıt bulunamadı.")
    return tr


@router.put("/transcripts/{tid}")
def save_transcript(tid: str, body: dict):
    title = body.get("title")
    if title is not None:
        title = str(title).strip()[:200] or "Adsız kayıt"
    segments = clean_segments(body["segments"]) if "segments" in body else None
    speakers = clean_speakers(body["speakers"]) if "speakers" in body else None
    if not db.update_transcript(tid, title, segments, speakers):
        raise HTTPException(404, "Kayıt bulunamadı.")
    events.bump()
    return {"ok": True, "saved_at": time.time()}


@router.delete("/transcripts/{tid}")
def delete_transcript(tid: str, delete_media: bool = True):
    job = db.get_job(tid, raw=True)
    if not job:
        raise HTTPException(404, "Kayıt bulunamadı.")
    if job["status"] == db.RUNNING:
        raise HTTPException(409, "Çalışan bir iş silinemez. Önce iptal edin.")
    paths = db.delete_job(tid)
    base = config.data_dir()
    if paths:
        media = base / paths["media_path"] if paths["media_path"] else None
        if media and media.exists():
            if delete_media:
                media.unlink(missing_ok=True)
            else:
                kept = base / "kept_media"
                kept.mkdir(exist_ok=True)
                name = sanitize_filename(job["orig_name"], default=media.name)
                target, n = kept / name, 1
                while target.exists():
                    target = kept / f"{Path(name).stem} ({n}){Path(name).suffix}"
                    n += 1
                shutil.move(str(media), str(target))
        if paths["preview_path"]:
            (base / paths["preview_path"]).unlink(missing_ok=True)
    events.bump()
    return {"ok": True}


@router.get("/transcripts/{tid}/media")
def media(tid: str):
    job = db.get_job(tid, raw=True)
    if not job or not (job["media_path"] or job["preview_path"]):
        raise HTTPException(404, "Ortam dosyası bulunamadı.")
    rel = job["preview_path"] or job["media_path"]
    path = config.data_dir() / rel
    if not path.exists():
        raise HTTPException(404, "Ortam dosyası bulunamadı.")
    ctype = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if path.suffix == ".m4a":
        ctype = "audio/mp4"
    return FileResponse(path, media_type=ctype, headers={"Cache-Control": "no-store"})


@router.post("/cues")
def cues(body: dict):
    segments = clean_segments(body.get("segments"))
    rules = {**config.load()["subtitle"], **(body.get("rules") or {})}
    return {"cues": build_cues(segments, Rules.from_dict(rules))}


def _truthy(v: str | None, default: bool) -> bool:
    if v is None:
        return default
    return v.lower() in ("1", "true", "evet", "on")


def _content_disposition(filename: str) -> str:
    ascii_name = filename.translate(_ASCII).encode("ascii", "replace").decode().replace("?", "_").replace('"', "")
    return f"attachment; filename=\"{ascii_name}\"; filename*=UTF-8''{urllib.parse.quote(filename)}"


@router.get("/transcripts/{tid}/export/{fmt}")
def export(tid: str, fmt: str, request: Request):
    tr = db.get_transcript(tid)
    if not tr:
        raise HTTPException(404, "Kayıt bulunamadı.")
    settings = config.load()
    q = request.query_params
    segs, spk = tr["segments"], tr["speakers"]
    timestamps = _truthy(q.get("timestamps"), True)
    show_spk = _truthy(q.get("speakers"), True)
    rules = dict(settings["subtitle"])
    for key, cast in (("max_chars", int), ("max_lines", int), ("max_dur", float), ("min_dur", float)):
        if q.get(key):
            try:
                rules[key] = cast(q[key])
            except ValueError:
                raise HTTPException(400, "Altyazı kuralları geçersiz.")
    prefix = _truthy(q.get("speaker_prefix"), bool(rules.get("speaker_prefix")))
    bom = _truthy(q.get("bom"), bool(settings["bom"]))

    if fmt == "txt":
        body, ctype, use_bom = txt.to_txt(segs, spk, timestamps, show_spk), "text/plain", True
    elif fmt == "srt":
        body, ctype, use_bom = srt_vtt.to_srt(segs, spk, rules, prefix), "application/x-subrip", True
    elif fmt == "vtt":
        body, ctype, use_bom = srt_vtt.to_vtt(segs, spk, rules, prefix), "text/vtt", False
    elif fmt == "csv":
        body, ctype, use_bom = json_csv.to_csv(segs, spk, settings["csv_delimiter"]), "text/csv", True
    elif fmt == "json":
        body, ctype, use_bom = json_csv.to_json(tr), "application/json", False
    elif fmt == "docx":
        data = docx_export.to_docx(tr, timestamps, show_spk)
        return Response(data, media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        headers={"Content-Disposition": _content_disposition(sanitize_filename(tr["title"]) + ".docx")})
    else:
        raise HTTPException(404, "Bilinmeyen dışa aktarma biçimi.")
    raw = body.encode("utf-8")
    if use_bom and bom:
        raw = b"\xef\xbb\xbf" + raw
    return Response(raw, media_type=f"{ctype}; charset=utf-8",
                    headers={"Content-Disposition": _content_disposition(sanitize_filename(tr["title"]) + "." + fmt)})
