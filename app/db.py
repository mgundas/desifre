"""SQLite şeması ve veri erişimi."""
from __future__ import annotations

import json
import sqlite3
import time
import uuid
from contextlib import contextmanager

from . import config
from .util import tr_lower

QUEUED, RUNNING, DONE, FAILED, CANCELLED = "beklemede", "işleniyor", "tamamlandı", "hata", "iptal"

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
  id TEXT PRIMARY KEY,
  status TEXT NOT NULL,
  options TEXT NOT NULL DEFAULT '{}',
  progress REAL NOT NULL DEFAULT 0,
  stage TEXT NOT NULL DEFAULT '',
  error TEXT NOT NULL DEFAULT '',
  notice TEXT NOT NULL DEFAULT '',
  created_at REAL NOT NULL,
  started_at REAL,
  finished_at REAL,
  media_path TEXT NOT NULL,
  preview_path TEXT NOT NULL DEFAULT '',
  orig_name TEXT NOT NULL DEFAULT '',
  size INTEGER NOT NULL DEFAULT 0,
  position REAL NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS transcripts (
  job_id TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
  title TEXT NOT NULL,
  title_lc TEXT NOT NULL DEFAULT '',
  language TEXT NOT NULL DEFAULT '',
  duration REAL NOT NULL DEFAULT 0,
  model TEXT NOT NULL DEFAULT '',
  is_video INTEGER NOT NULL DEFAULT 0,
  segments TEXT NOT NULL DEFAULT '[]',
  speakers TEXT NOT NULL DEFAULT '{}',
  search_text TEXT NOT NULL DEFAULT '',
  speaker_count INTEGER NOT NULL DEFAULT 0,
  updated_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status, position);
"""


@contextmanager
def conn():
    c = sqlite3.connect(config.data_dir() / "desifre.db", timeout=30)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def init() -> None:
    with conn() as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(SCHEMA)


def recover_after_restart() -> int:
    """Yarım kalan işleri tekrar kuyruğa alır."""
    with conn() as c:
        cur = c.execute(
            "UPDATE jobs SET status=?, progress=0, stage='', started_at=NULL WHERE status=?", (QUEUED, RUNNING)
        )
        return cur.rowcount


def _next_position(c) -> float:
    row = c.execute("SELECT MAX(position) AS m FROM jobs").fetchone()
    return (row["m"] or 0) + 1


def create_job(orig_name: str, media_path: str, size: int, options: dict, title: str) -> str:
    job_id = uuid.uuid4().hex
    now = time.time()
    with conn() as c:
        c.execute(
            "INSERT INTO jobs (id,status,options,created_at,media_path,orig_name,size,position) VALUES (?,?,?,?,?,?,?,?)",
            (job_id, QUEUED, json.dumps(options, ensure_ascii=False), now, media_path, orig_name, size, _next_position(c)),
        )
        c.execute(
            "INSERT INTO transcripts (job_id,title,title_lc,updated_at) VALUES (?,?,?,?)",
            (job_id, title, tr_lower(title), now),
        )
    return job_id


def _job_dict(r: sqlite3.Row) -> dict:
    d = dict(r)
    d["options"] = json.loads(d.get("options") or "{}")
    now = time.time()
    if d["status"] == RUNNING and d.get("started_at"):
        d["elapsed"] = now - d["started_at"]
    elif d.get("started_at") and d.get("finished_at"):
        d["elapsed"] = d["finished_at"] - d["started_at"]
    else:
        d["elapsed"] = 0
    pct = d.get("progress") or 0
    d["eta"] = (d["elapsed"] / pct * (100 - pct)) if d["status"] == RUNNING and pct >= 3 else None
    d.pop("media_path", None)
    d.pop("preview_path", None)
    return d


JOB_SELECT = """SELECT j.*, t.title, t.duration, t.language, t.model, t.speaker_count, t.is_video
                FROM jobs j JOIN transcripts t ON t.job_id=j.id"""


def get_job(job_id: str, raw: bool = False) -> dict | None:
    with conn() as c:
        r = c.execute(JOB_SELECT + " WHERE j.id=?", (job_id,)).fetchone()
    if not r:
        return None
    if raw:
        d = dict(r)
        d["options"] = json.loads(d["options"] or "{}")
        return d
    return _job_dict(r)


def list_jobs(statuses: list[str] | None = None) -> list[dict]:
    with conn() as c:
        if statuses:
            q = ",".join("?" * len(statuses))
            rows = c.execute(JOB_SELECT + f" WHERE j.status IN ({q}) ORDER BY j.position", statuses).fetchall()
        else:
            rows = c.execute(JOB_SELECT + " ORDER BY j.position").fetchall()
    return [_job_dict(r) for r in rows]


def list_active(finished_after: float, include_failed: bool = False) -> list[dict]:
    """Bekleyen ve çalışan işler ile belirtilen zamandan sonra biten işler (kütüphanenin tamamını yüklemez)."""
    extra = "j.status != ?" if include_failed else "j.status IN (?, ?)"
    args = (DONE,) if include_failed else (QUEUED, RUNNING)
    with conn() as c:
        rows = c.execute(JOB_SELECT + f" WHERE {extra} OR j.finished_at > ? ORDER BY j.position", (*args, finished_after)).fetchall()
    return [_job_dict(r) for r in rows]


def next_queued() -> dict | None:
    with conn() as c:
        r = c.execute(JOB_SELECT + " WHERE j.status=? ORDER BY j.position LIMIT 1", (QUEUED,)).fetchone()
    if not r:
        return None
    d = dict(r)
    d["options"] = json.loads(d["options"] or "{}")
    return d


def update_job(job_id: str, **fields) -> None:
    if not fields:
        return
    sets = ",".join(f"{k}=?" for k in fields)
    with conn() as c:
        c.execute(f"UPDATE jobs SET {sets} WHERE id=?", (*fields.values(), job_id))


def claim_job(job_id: str) -> bool:
    """Sırası gelen işi 'işleniyor' yapar. Arada iptal edildiyse False."""
    with conn() as c:
        cur = c.execute(
            "UPDATE jobs SET status=?, started_at=?, progress=0, stage='', error='', notice='' WHERE id=? AND status=?",
            (RUNNING, time.time(), job_id, QUEUED),
        )
        return cur.rowcount == 1


def finish_job(job_id: str, status: str, error: str = "") -> None:
    extra = {"progress": 100} if status == DONE else {}
    update_job(job_id, status=status, error=error, finished_at=time.time(), stage="", **extra)


def cancel_queued(job_id: str) -> bool:
    with conn() as c:
        cur = c.execute(
            "UPDATE jobs SET status=?, finished_at=? WHERE id=? AND status=?", (CANCELLED, time.time(), job_id, QUEUED)
        )
        return cur.rowcount == 1


def retry_job(job_id: str) -> bool:
    with conn() as c:
        pos = _next_position(c)
        cur = c.execute(
            "UPDATE jobs SET status=?, progress=0, stage='', error='', notice='', started_at=NULL, finished_at=NULL, position=? "
            "WHERE id=? AND status IN (?,?)",
            (QUEUED, pos, job_id, FAILED, CANCELLED),
        )
        return cur.rowcount == 1


def reorder(ids: list[str]) -> None:
    """Beklemedeki işleri verilen sıraya koyar."""
    with conn() as c:
        rows = c.execute("SELECT id, position FROM jobs WHERE status=? ORDER BY position", (QUEUED,)).fetchall()
        queued = {r["id"] for r in rows}
        slots = sorted(r["position"] for r in rows)
        wanted = [i for i in ids if i in queued]
        wanted += [r["id"] for r in rows if r["id"] not in wanted]
        for slot, jid in zip(slots, wanted):
            c.execute("UPDATE jobs SET position=? WHERE id=?", (slot, jid))


def delete_job(job_id: str) -> dict | None:
    with conn() as c:
        r = c.execute("SELECT media_path, preview_path FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not r:
            return None
        c.execute("DELETE FROM jobs WHERE id=?", (job_id,))
        return dict(r)


def clear_media(job_id: str) -> None:
    update_job(job_id, media_path="", preview_path="")


# ---- transcripts ----

def _search_text(segments: list[dict]) -> str:
    return tr_lower(" ".join(s.get("text", "") for s in segments))


def save_result(job_id: str, *, language: str, duration: float, model: str, is_video: bool,
                segments: list[dict], speakers: dict) -> None:
    with conn() as c:
        c.execute(
            "UPDATE transcripts SET language=?, duration=?, model=?, is_video=?, segments=?, speakers=?, "
            "search_text=?, speaker_count=?, updated_at=? WHERE job_id=?",
            (language, duration, model, int(is_video), json.dumps(segments, ensure_ascii=False),
             json.dumps(speakers, ensure_ascii=False), _search_text(segments), len(speakers), time.time(), job_id),
        )


def get_transcript(job_id: str) -> dict | None:
    with conn() as c:
        r = c.execute(
            "SELECT t.*, j.status, j.orig_name, j.created_at, j.options, j.media_path, j.notice, j.error FROM transcripts t "
            "JOIN jobs j ON j.id=t.job_id WHERE t.job_id=?", (job_id,)
        ).fetchone()
    if not r:
        return None
    d = dict(r)
    d["segments"] = json.loads(d["segments"])
    d["speakers"] = json.loads(d["speakers"])
    d["options"] = json.loads(d["options"] or "{}")
    d["is_video"] = bool(d["is_video"])
    d["has_media"] = bool(d.pop("media_path"))
    d.pop("search_text", None)
    d.pop("title_lc", None)
    return d


def update_transcript(job_id: str, title: str | None, segments: list[dict] | None, speakers: dict | None) -> bool:
    sets, vals = ["updated_at=?"], [time.time()]
    if title is not None:
        sets += ["title=?", "title_lc=?"]
        vals += [title, tr_lower(title)]
    if segments is not None:
        used = {s.get("speaker") for s in segments if s.get("speaker")}
        sets += ["segments=?", "search_text=?", "speaker_count=?"]
        vals += [json.dumps(segments, ensure_ascii=False), _search_text(segments), len(used)]
    if speakers is not None:
        sets += ["speakers=?"]
        vals += [json.dumps(speakers, ensure_ascii=False)]
    with conn() as c:
        cur = c.execute(f"UPDATE transcripts SET {','.join(sets)} WHERE job_id=?", (*vals, job_id))
        return cur.rowcount == 1


def list_library(q: str = "", sort: str = "date", order: str = "desc") -> list[dict]:
    cols = {"date": "j.created_at", "title": "t.title_lc", "duration": "t.duration"}
    col = cols.get(sort, "j.created_at")
    direction = "ASC" if order == "asc" else "DESC"
    sql = JOB_SELECT
    args: list = []
    if q.strip():
        needle = "%" + tr_lower(q.strip()).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
        sql += " WHERE (t.title_lc LIKE ? ESCAPE '\\' OR t.search_text LIKE ? ESCAPE '\\')"
        args += [needle, needle]
    sql += f" ORDER BY {col} {direction}"
    with conn() as c:
        rows = c.execute(sql, args).fetchall()
    return [_job_dict(r) for r in rows]
