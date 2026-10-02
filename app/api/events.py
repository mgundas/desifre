"""Server-Sent Events: iş ilerlemesini tarayıcıya iter."""
from __future__ import annotations

import asyncio
import json
import time

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from .. import db, events

router = APIRouter(prefix="/api")

FIELDS = ("id", "status", "progress", "stage", "elapsed", "eta", "error", "notice", "title", "position",
          "orig_name", "duration", "created_at", "finished_at")


def _payload() -> str:
    jobs = [{k: j.get(k) for k in FIELDS} for j in db.list_active(time.time() - 60)]
    return json.dumps({"jobs": jobs}, ensure_ascii=False)


@router.get("/events")
async def stream(request: Request):
    async def gen():
        seen = -1
        last_send = 0.0
        while True:
            if await request.is_disconnected():
                return
            v = events.version()
            now = time.monotonic()
            # değişiklik olduysa hemen, yoksa ilerleme/süre güncellemesi için 2 sn'de bir gönder
            if v != seen or now - last_send > 2:
                data = await asyncio.to_thread(_payload)
                yield f"event: jobs\ndata: {data}\n\n"
                seen, last_send = v, now
            await asyncio.sleep(0.4)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
