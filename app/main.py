"""FastAPI uygulaması: statik arayüz, API ve başlangıç denetimleri."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from urllib.parse import urlparse

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config, db
from .api import events as events_api
from .api import jobs, settings, system, transcripts
from .pipeline import gpu
from .worker import Worker

STATIC_DIR = config.APP_DIR / "static"
LOCAL_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1", "testserver"}

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")


class NoCacheStatic(StaticFiles):
    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        resp.headers["Cache-Control"] = "no-cache"
        return resp


def create_app() -> FastAPI:
    gpu.setup_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        db.init()
        recovered = db.recover_after_restart()
        if recovered:
            logging.getLogger("desifre").info("%d yarım kalan iş kuyruğa geri alındı", recovered)
        for f in config.work_dir().glob("*.wav"):
            f.unlink(missing_ok=True)
        app.state.worker.start()
        yield
        app.state.worker.stop()

    app = FastAPI(title="Deşifre", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)
    app.state.worker = Worker()

    @app.middleware("http")
    async def guard(request: Request, call_next):
        """Yerel uygulamayı DNS yeniden bağlama ve başka sitelerden gelen isteklere karşı korur."""
        host = (request.headers.get("host") or "").rsplit(":", 1)[0] if not (request.headers.get("host") or "").startswith("[") \
            else (request.headers.get("host") or "").split("]")[0] + "]"
        lan = config.load()["allow_lan"]
        if not lan and host not in LOCAL_HOSTS:
            return JSONResponse({"detail": "Bu adrese erişim izni yok."}, status_code=403)
        origin = request.headers.get("origin")
        if origin and request.method not in ("GET", "HEAD", "OPTIONS"):
            if urlparse(origin).netloc != request.headers.get("host"):
                return JSONResponse({"detail": "İstek başka bir siteden geldiği için reddedildi."}, status_code=403)
        return await call_next(request)

    app.include_router(jobs.router)
    app.include_router(transcripts.router)
    app.include_router(settings.router)
    app.include_router(system.router)
    app.include_router(events_api.router)

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html", headers={"Cache-Control": "no-cache"})

    app.mount("/static", NoCacheStatic(directory=STATIC_DIR), name="static")
    return app


app = create_app()
