"""Sunucuyu ayrı bir süreçte başlatan yardımcılar (Playwright testleri ve elle denemeler için)."""
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    def __init__(self, data_dir: Path, engine: str = "fake", extra_env: dict | None = None, new_group: bool = False):
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        env = {**os.environ, "DESIFRE_DATA": str(data_dir), "DESIFRE_PORT": str(self.port), "PYTHONIOENCODING": "utf-8"}
        if engine == "fake":
            env["DESIFRE_ENGINE"] = "fake"
        else:
            env.pop("DESIFRE_ENGINE", None)
        env.update(extra_env or {})
        self.log = open(data_dir.parent / "server.log", "wb")
        flags = subprocess.CREATE_NEW_PROCESS_GROUP if new_group and sys.platform == "win32" else 0
        self.proc = subprocess.Popen([sys.executable, str(ROOT / "run.py")], cwd=ROOT, env=env, stdout=self.log, stderr=subprocess.STDOUT, creationflags=flags)

    def wait_ready(self, timeout=60):
        end = time.time() + timeout
        while time.time() < end:
            try:
                urllib.request.urlopen(self.url + "/api/settings", timeout=2).read()
                return
            except Exception:
                if self.proc.poll() is not None:
                    raise RuntimeError("Sunucu başlamadan kapandı")
                time.sleep(0.3)
        raise RuntimeError("Sunucu zamanında hazır olmadı")

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(10)
        except subprocess.TimeoutExpired:
            self.proc.kill()
        self.log.close()
