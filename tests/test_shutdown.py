"""Açık bir SSE bağlantısı varken sunucu zamanında kapanabilmeli."""
import signal
import subprocess
import sys
import threading
import time
import urllib.request

import pytest

from tests.e2e_helpers import Server


@pytest.mark.skipif(sys.platform != "win32", reason="CTRL_BREAK yalnızca Windows'ta")
def test_server_stops_quickly_with_open_event_stream(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    srv = Server(data, engine="fake", new_group=True)
    try:
        srv.wait_ready()
        opened = threading.Event()

        def hold():
            try:
                with urllib.request.urlopen(srv.url + "/api/events", timeout=30) as r:
                    r.readline()
                    opened.set()
                    while r.readline():
                        pass
            except Exception:
                opened.set()

        threading.Thread(target=hold, daemon=True).start()
        assert opened.wait(10)
        t0 = time.time()
        srv.proc.send_signal(signal.CTRL_BREAK_EVENT)  # uvicorn zarif kapanışını tetikler
        srv.proc.wait(timeout=20)
        assert time.time() - t0 < 10
        assert "Traceback" not in (data.parent / "server.log").read_text(errors="replace")
    finally:
        srv.stop()
