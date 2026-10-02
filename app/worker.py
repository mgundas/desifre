"""Tek işçi iş parçacığı: kuyruktaki işleri sırayla çalıştırır."""
from __future__ import annotations

import logging
import os
import threading
import time
from pathlib import Path
from typing import Callable

from . import config, db, events
from .errors import Cancelled, UserError
from .pipeline import audio

log = logging.getLogger("desifre.worker")
IDLE_UNLOAD_SECONDS = 600


def make_engine():
    if os.environ.get("DESIFRE_ENGINE") == "fake":
        from .pipeline.fake import FakeEngine
        return FakeEngine()
    from .pipeline.transcribe import RealEngine
    return RealEngine()


class Worker:
    def __init__(self, engine_factory: Callable = make_engine):
        self._factory = engine_factory
        self.engine = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._wake = threading.Event()
        self.current_id: str | None = None
        self._cancel = threading.Event()
        self._user_cancel = False
        self._idle_since = time.monotonic()

    # ---- yaşam döngüsü ----
    def start(self) -> None:
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, name="desifre-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._cancel.set()
        self._wake.set()
        if self._thread:
            self._thread.join(timeout=15)
        if self.engine:
            try:
                self.engine.unload()
            except Exception:
                pass

    def wake(self) -> None:
        self._wake.set()

    def cancel_running(self, job_id: str) -> bool:
        if self.current_id == job_id:
            self._user_cancel = True
            self._cancel.set()
            return True
        return False

    # ---- döngü ----
    def _loop(self) -> None:
        while not self._stop.is_set():
            job = db.next_queued()
            if not job:
                self._wake.wait(timeout=1.0)
                self._wake.clear()
                if self.engine and time.monotonic() - self._idle_since > IDLE_UNLOAD_SECONDS:
                    self._unload_engine()
                continue
            if not db.claim_job(job["id"]):
                continue
            self._process(job)
            self._idle_since = time.monotonic()

    def _unload_engine(self) -> None:
        if self.engine:
            try:
                self.engine.unload()
            except Exception:
                log.exception("Model boşaltılamadı")

    def _process(self, job: dict) -> None:
        job_id, options = job["id"], job["options"]
        self.current_id = job_id
        self._cancel.clear()
        self._user_cancel = False
        events.bump()
        wav = config.work_dir() / f"{job_id}.wav"
        started = time.monotonic()

        def cancelled() -> bool:
            return self._cancel.is_set() or self._stop.is_set()

        def report(stage: str, pct: float) -> None:
            db.update_job(job_id, stage=stage, progress=max(0.0, min(99.0, pct)))
            events.bump(throttle=0.3)

        try:
            report("Ses hazırlanıyor", 1)
            media = config.data_dir() / job["media_path"]
            if not media.exists():
                raise UserError("Kaynak dosya bulunamadı. Dosya silinmiş olabilir.")
            info = audio.probe(media)
            if cancelled():
                raise Cancelled()
            audio.decode_to_wav(media, wav, cancelled)
            ext = media.suffix.lstrip(".").lower()
            preview = audio.make_preview(media, ext, info["has_video"], config.uploads_dir() / f"{job_id}.preview", cancelled)
            if preview:
                db.update_job(job_id, preview_path=str(Path(preview).relative_to(config.data_dir())))
            if self.engine is None:
                self.engine = self._factory()
            run_opts = {**config.load(), **options}
            result = self.engine.run(str(wav), info["duration"], run_opts, report, cancelled)
            if cancelled():
                raise Cancelled()
            report("Kaydediliyor", 98)
            db.save_result(job_id, language=result["language"], duration=info["duration"],
                           model=options.get("model", ""), is_video=info["has_video"],
                           segments=result["segments"], speakers=result["speakers"])
            if result.get("notice"):
                db.update_job(job_id, notice=result["notice"])
            db.finish_job(job_id, db.DONE)
        except Cancelled:
            if self._stop.is_set() and not self._user_cancel:
                db.update_job(job_id, status=db.QUEUED, progress=0, stage="", started_at=None)  # kapanırken işi kuyruğa geri koy
            else:
                db.finish_job(job_id, db.CANCELLED)
        except UserError as e:
            db.finish_job(job_id, db.FAILED, str(e))
        except Exception as e:  # noqa: BLE001
            log.exception("İş başarısız: %s", job_id)
            db.finish_job(job_id, db.FAILED, f"Beklenmeyen bir hata oluştu ({type(e).__name__}). Ayrıntılar günlükte.")
        finally:
            try:
                wav.unlink(missing_ok=True)
            except OSError:
                pass
            if self.engine:
                try:
                    self.engine.after_job(options)
                except Exception:
                    log.exception("Model temizliği başarısız")
            self.current_id = None
            events.bump()
            log.info("İş bitti: %s (%.1f sn)", job_id, time.monotonic() - started)
