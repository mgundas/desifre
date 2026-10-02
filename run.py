"""Deşifre sunucusunu başlatır: python run.py"""
import os

import uvicorn

from app import config


def main() -> None:
    lan = bool(config.load()["allow_lan"])
    host = "0.0.0.0" if lan else "127.0.0.1"
    if lan:
        print("UYARI: Yerel ağ erişimi açık. Aynı ağdaki herkes kayıtlarınıza erişebilir.")
    print(f"Deşifre çalışıyor: http://127.0.0.1:{config.PORT}")
    uvicorn.run("app.main:app", host=host, port=config.PORT, log_level="warning", workers=1,
                timeout_keep_alive=30, timeout_graceful_shutdown=3, reload=bool(os.environ.get("DESIFRE_RELOAD")))


if __name__ == "__main__":
    main()
