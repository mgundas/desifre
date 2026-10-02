"""Arayüze canlı güncelleme için basit sürüm sayacı (SSE bunu izler)."""
from __future__ import annotations

import threading
import time

_lock = threading.Lock()
_version = 0
_last_bump = 0.0


def version() -> int:
    return _version


def bump(throttle: float = 0.0) -> None:
    """Durum değişti. throttle > 0 ise çok sık çağrılar birleştirilir."""
    global _version, _last_bump
    now = time.monotonic()
    with _lock:
        if throttle and now - _last_bump < throttle:
            return
        _last_bump = now
        _version += 1
