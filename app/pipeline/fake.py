"""Test için sahte yazıya dökücü. Model gerektirmez."""
from __future__ import annotations

import os
import time

from ..errors import Cancelled, UserError

TEXT = ("Merhaba, bu bir deneme kaydıdır. İstanbul'da hava çok güzel. "
        "Şimdi ığdır ve çorbadan bahsedelim. Öğrenciler üniversiteye gidiyor.")


class FakeEngine:
    def __init__(self):
        self.unloaded = 0
        self.loaded_key = None

    def unload(self):
        self.unloaded += 1
        self.loaded_key = None

    def after_job(self, options: dict) -> None:
        if options.get("diarize"):
            self.unload()

    def run(self, wav_path, duration, options, report, cancelled):
        delay = float(os.environ.get("DESIFRE_FAKE_DELAY", "0"))
        if os.environ.get("DESIFRE_FAKE_FAIL"):
            raise UserError("GPU belleği yetersiz. Daha küçük bir model deneyin.")
        self.loaded_key = options.get("model")
        words = TEXT.split()
        span = min(max(duration, 4.0), 40.0)
        step = span / len(words)
        steps = 10
        for i in range(steps):
            if cancelled():
                raise Cancelled()
            report("Yazıya dökülüyor", 70.0 * (i + 1) / steps)
            if delay:
                time.sleep(delay)
        segments, speakers = [], {}
        per = 6
        for si in range(0, len(words), per):
            chunk = words[si:si + per]
            ws = [{"word": w, "start": round((si + k) * step, 3), "end": round((si + k + 1) * step, 3), "score": 0.9}
                  for k, w in enumerate(chunk)]
            spk = None
            if options.get("diarize"):
                spk = f"SPEAKER_{(si // per) % 2:02d}"
                speakers.setdefault(spk, {"name": "", "color": "#3b82f6" if spk.endswith("0") else "#f97316"})
            segments.append({"id": f"s{si // per}", "start": ws[0]["start"], "end": ws[-1]["end"], "speaker": spk,
                             "text": " ".join(chunk), "words": ws})
        report("Hizalanıyor", 85.0)
        return {"language": options.get("language") or "tr", "segments": segments, "speakers": speakers,
                "notice": ""}
