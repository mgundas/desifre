"""Aygıt algılama, CUDA DLL yolları ve VRAM temizliği."""
from __future__ import annotations

import gc
import glob
import os
import shutil
import subprocess
import sys
import threading

_dll_done = False
_lock = threading.Lock()


def setup_env() -> None:
    """Telemetriyi kapatır. Başka hiçbir dış çağrı yapılmaz (model indirme hariç)."""
    for k, v in {
        "HF_HUB_DISABLE_TELEMETRY": "1",
        "DO_NOT_TRACK": "1",
        "ANONYMIZED_TELEMETRY": "False",
        "PYANNOTE_METRICS_ENABLED": "0",
        "HF_HUB_DISABLE_SYMLINKS_WARNING": "1",
        "TOKENIZERS_PARALLELISM": "false",
    }.items():
        os.environ.setdefault(k, v)


def setup_dll_paths() -> list[str]:
    """pip ile kurulan cuBLAS ve cuDNN DLL klasörlerini Windows'ta yola ekler."""
    global _dll_done
    added: list[str] = []
    with _lock:
        if _dll_done:
            return added
        _dll_done = True
        if sys.platform != "win32":
            return added
        roots = [p for p in sys.path if p.lower().endswith("site-packages")]
        for root in roots:
            for pattern in ("nvidia/*/bin", "torch/lib"):
                for d in glob.glob(os.path.join(root, pattern)):
                    if os.path.isdir(d) and d not in added:
                        try:
                            os.add_dll_directory(d)
                        except (OSError, AttributeError):
                            pass
                        os.environ["PATH"] = d + os.pathsep + os.environ.get("PATH", "")
                        added.append(d)
    return added


def cuda_available() -> bool:
    setup_dll_paths()
    try:
        import ctranslate2
        return ctranslate2.get_cuda_device_count() > 0
    except Exception:
        return False


def resolve_device(pref: str = "auto") -> str:
    if pref == "cpu":
        return "cpu"
    if cuda_available():
        return "cuda"
    return "cpu"


def resolve_compute_type(pref: str, device: str) -> str:
    if pref and pref != "auto":
        if device == "cpu" and pref in ("float16", "int8_float16"):
            return "int8"
        return pref
    return "int8_float16" if device == "cuda" else "int8"


def free_gpu() -> None:
    """Python ve CUDA önbelleğini boşaltır."""
    gc.collect()
    try:
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
            torch.cuda.ipc_collect()
    except Exception:
        pass
    gc.collect()


def is_oom(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "out of memory" in msg or "cuda failed with error out of memory" in msg or "cublas_status_alloc_failed" in msg


def gpu_info() -> dict:
    """GPU adı ve VRAM bilgisi (nvidia-smi ile, torch yüklemeden)."""
    info = {"name": None, "vram_mb": None, "driver": None}
    exe = shutil.which("nvidia-smi")
    if not exe:
        return info
    try:
        out = subprocess.run(
            [exe, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        ).stdout.strip().splitlines()
        if out:
            name, mem, drv = [x.strip() for x in out[0].split(",")]
            info.update(name=name, vram_mb=int(float(mem)), driver=drv)
    except Exception:
        pass
    return info
