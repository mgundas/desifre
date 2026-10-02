"""ffmpeg ile ses çözme, süre ve önizleme dosyası."""
from __future__ import annotations

import glob
import json
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Callable

from ..errors import Cancelled, UserError

NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
MSG_NO_FFMPEG = "ffmpeg bulunamadı. Kurulum adımları için Ayarlar sayfasına bakın."
BROWSER_OK = {"mp3", "wav", "m4a", "aac", "ogg", "opus", "flac", "mp4", "webm", "mov"}


def _find(name: str) -> str | None:
    exe = shutil.which(name)
    if exe:
        return exe
    local = os.environ.get("LOCALAPPDATA", "")
    candidates = [Path(local) / "Microsoft" / "WinGet" / "Links" / f"{name}.exe"] if local else []
    if local:
        candidates += [Path(p) for p in glob.glob(str(Path(local) / "Microsoft" / "WinGet" / "Packages" / "Gyan.FFmpeg*" / "**" / f"{name}.exe"), recursive=True)]
    candidates.append(Path(__file__).resolve().parents[2] / "ffmpeg" / "bin" / f"{name}.exe")
    for c in candidates:
        if c.exists():
            return str(c)
    return None


def ffmpeg_path() -> str | None:
    return _find("ffmpeg")


def ffprobe_path() -> str | None:
    return _find("ffprobe")


def require_ffmpeg() -> tuple[str, str]:
    ff, fp = ffmpeg_path(), ffprobe_path()
    if not ff or not fp:
        raise UserError(MSG_NO_FFMPEG)
    return ff, fp


def probe(path: str | Path) -> dict:
    """Süreyi ve görüntü akışı olup olmadığını döndürür."""
    _, fp = require_ffmpeg()
    r = subprocess.run(
        [fp, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True, creationflags=NO_WINDOW, encoding="utf-8", errors="replace",
    )
    try:
        data = json.loads(r.stdout or "{}")
    except ValueError:
        data = {}
    streams = data.get("streams") or []
    has_audio = any(s.get("codec_type") == "audio" for s in streams)
    if r.returncode != 0 or not has_audio:
        raise UserError("Dosya biçimi desteklenmiyor ya da dosyada ses bulunamadı.")
    has_video = any(s.get("codec_type") == "video" and s.get("disposition", {}).get("attached_pic") != 1 for s in streams)
    try:
        duration = float((data.get("format") or {}).get("duration") or 0)
    except ValueError:
        duration = 0.0
    if duration <= 0:
        for s in streams:
            try:
                duration = max(duration, float(s.get("duration") or 0))
            except ValueError:
                pass
    return {"duration": duration, "has_video": has_video}


def _run(cmd: list[str], cancel: Callable[[], bool] | None) -> int:
    p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NO_WINDOW)
    while p.poll() is None:
        if cancel and cancel():
            p.kill()
            p.wait()
            raise Cancelled()
        time.sleep(0.2)
    return p.returncode


def decode_to_wav(src: str | Path, dst: str | Path, cancel: Callable[[], bool] | None = None) -> None:
    ff, _ = require_ffmpeg()
    rc = _run([ff, "-nostdin", "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(dst)], cancel)
    if rc != 0 or not Path(dst).exists():
        raise UserError("Dosya biçimi desteklenmiyor ya da dosya bozuk. Ses çözülemedi.")


def make_preview(src: str | Path, ext: str, has_video: bool, dst_base: str | Path,
                 cancel: Callable[[], bool] | None = None) -> str | None:
    """Tarayıcının çalamayacağı biçimler için çalınabilir bir kopya üretir. Gerek yoksa None."""
    if ext in BROWSER_OK:
        return None
    ff, _ = require_ffmpeg()
    if has_video:
        dst = str(dst_base) + ".mp4"
        cmd = [ff, "-nostdin", "-y", "-i", str(src), "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", dst]
    else:
        dst = str(dst_base) + ".m4a"
        cmd = [ff, "-nostdin", "-y", "-i", str(src), "-vn", "-c:a", "aac", "-b:a", "128k", dst]
    try:
        rc = _run(cmd, cancel)
    except Cancelled:
        raise
    if rc != 0 and has_video:
        dst = str(dst_base) + ".m4a"
        rc = _run([ff, "-nostdin", "-y", "-i", str(src), "-vn", "-c:a", "aac", "-b:a", "128k", dst], cancel)
    return dst if rc == 0 and Path(dst).exists() else None
