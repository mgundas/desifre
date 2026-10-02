"""Modelleri önceden indirir: python -m app.pipeline.download [model] [dil]"""
import sys

from . import gpu


def main() -> int:
    gpu.setup_env()
    gpu.setup_dll_paths()
    model = sys.argv[1] if len(sys.argv) > 1 else "large-v3"
    lang = sys.argv[2] if len(sys.argv) > 2 else "tr"
    print(f"'{model}' modeli indiriliyor. Boyuta göre birkaç dakika sürebilir...")
    try:
        from faster_whisper.utils import download_model
        path = download_model(model)
        print(f"Model hazır: {path}")
    except Exception as e:  # noqa: BLE001
        print(f"Model indirilemedi ({type(e).__name__}). İnternet bağlantınızı kontrol edin.")
        return 1
    print(f"Hizalama modeli ('{lang}') indiriliyor...")
    try:
        import whisperx
        whisperx.load_align_model(language_code=lang, device="cpu")
        print("Hizalama modeli hazır.")
    except Exception as e:  # noqa: BLE001
        print(f"Hizalama modeli indirilemedi ({type(e).__name__}). İlk işte yeniden denenecek.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
