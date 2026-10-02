import math
import os
import struct
import sys
import wave
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT_DIR))


def make_wav(path: Path, seconds: float = 3.0, freq: float = 440.0) -> Path:
    rate = 16000
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        frames = b"".join(struct.pack("<h", int(8000 * math.sin(2 * math.pi * freq * i / rate))) for i in range(int(rate * seconds)))
        w.writeframes(frames)
    return path


@pytest.fixture()
def wav_file(tmp_path):
    return make_wav(tmp_path / "ornek.wav")


@pytest.fixture()
def data_dir(tmp_path, monkeypatch):
    d = tmp_path / "data"
    monkeypatch.setenv("DESIFRE_DATA", str(d))
    monkeypatch.setenv("DESIFRE_ENGINE", "fake")
    return d


@pytest.fixture()
def client(data_dir):
    from fastapi.testclient import TestClient
    from app.main import create_app
    with TestClient(create_app()) as c:
        yield c


def sample_segments():
    def words(items):
        return [{"word": w, "start": s, "end": e} for w, s, e in items]
    return [
        {"id": "s0", "start": 0.0, "end": 2.0, "speaker": "SPEAKER_00", "text": "Merhaba nasılsınız bugün.",
         "words": words([("Merhaba", 0.0, 0.6), ("nasılsınız", 0.7, 1.4), ("bugün.", 1.5, 2.0)])},
        {"id": "s1", "start": 2.2, "end": 4.0, "speaker": "SPEAKER_01", "text": "İyiyim, teşekkür ederim.",
         "words": words([("İyiyim,", 2.2, 2.9), ("teşekkür", 3.0, 3.5), ("ederim.", 3.5, 4.0)])},
    ]
