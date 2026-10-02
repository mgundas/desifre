"""RealEngine: bellek yetersizliğinde yeniden deneme ve model tutma kuralları (model gerektirmez)."""
import pytest

from app.errors import Cancelled, UserError
from app.pipeline import gpu, transcribe
from app.pipeline.transcribe import RealEngine


def options(**kw):
    return {"device": "cuda", "compute_type": "auto", "batch_size": 8, **kw}


@pytest.fixture(autouse=True)
def fake_cuda(monkeypatch):
    monkeypatch.setattr(gpu, "resolve_device", lambda pref="auto": "cuda")
    monkeypatch.setattr(gpu, "free_gpu", lambda: None)


def test_oom_retries_once_with_half_batch(monkeypatch):
    calls = []
    eng = RealEngine()

    def run_once(self, wav, dur, opts, report, cancelled, device, compute, batch):
        calls.append(batch)
        if len(calls) == 1:
            raise RuntimeError("CUDA failed with error out of memory")
        return {"language": "tr", "segments": [], "speakers": {}, "notice": ""}

    monkeypatch.setattr(RealEngine, "_run_once", run_once)
    unloaded = []
    monkeypatch.setattr(RealEngine, "unload", lambda self: unloaded.append(1))
    res = eng.run("x.wav", 10, options(), lambda *a: None, lambda: False)
    assert calls == [8, 4] and res["language"] == "tr" and unloaded


def test_second_oom_becomes_turkish_user_error(monkeypatch):
    def run_once(self, *a, **k):
        raise RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB")

    monkeypatch.setattr(RealEngine, "_run_once", run_once)
    monkeypatch.setattr(RealEngine, "unload", lambda self: None)
    with pytest.raises(UserError) as e:
        RealEngine().run("x.wav", 10, options(), lambda *a: None, lambda: False)
    assert str(e.value) == "GPU belleği yetersiz. Daha küçük bir model deneyin."


def test_non_oom_errors_are_not_retried(monkeypatch):
    calls = []

    def run_once(self, *a, **k):
        calls.append(1)
        raise ValueError("başka bir sorun")

    monkeypatch.setattr(RealEngine, "_run_once", run_once)
    with pytest.raises(ValueError):
        RealEngine().run("x.wav", 10, options(), lambda *a: None, lambda: False)
    assert calls == [1]


def test_cancel_is_not_retried(monkeypatch):
    def run_once(self, *a, **k):
        raise Cancelled()

    monkeypatch.setattr(RealEngine, "_run_once", run_once)
    with pytest.raises(Cancelled):
        RealEngine().run("x.wav", 10, options(), lambda *a: None, lambda: False)


def test_cublas_error_gets_friendly_message(monkeypatch):
    def run_once(self, *a, **k):
        raise RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")

    monkeypatch.setattr(RealEngine, "_run_once", run_once)
    with pytest.raises(UserError) as e:
        RealEngine().run("x.wav", 10, options(), lambda *a: None, lambda: False)
    assert "cuBLAS" in str(e.value)


def test_diarization_jobs_unload_asr_after_job(monkeypatch):
    eng = RealEngine()
    unloaded = []
    monkeypatch.setattr(RealEngine, "unload", lambda self: unloaded.append(1))
    eng.after_job({"diarize": False})
    assert not unloaded
    eng.after_job({"diarize": True})
    assert unloaded


def test_same_model_is_kept_and_different_model_reloads(monkeypatch):
    import sys, types
    loads = []

    class FakeModel:
        def __init__(self, name, device, compute_type):
            loads.append(name)

    fake = types.SimpleNamespace(WhisperModel=FakeModel, BatchedInferencePipeline=lambda m: object())
    monkeypatch.setitem(sys.modules, "faster_whisper", fake)
    eng = RealEngine()
    report = lambda *a: None
    eng._load_asr("tiny", "cuda", "int8_float16", report)
    eng._load_asr("tiny", "cuda", "int8_float16", report)
    assert loads == ["tiny"]
    eng._load_asr("small", "cuda", "int8_float16", report)
    assert loads == ["tiny", "small"]
