"""JSON ve CSV dışa aktarma."""
from __future__ import annotations

import csv
import io
import json

from ..util import fmt_clock, speaker_label


def to_json(tr: dict) -> str:
    data = {
        "title": tr["title"], "language": tr["language"], "duration": tr["duration"], "model": tr["model"],
        "speakers": tr["speakers"], "segments": tr["segments"],
    }
    return json.dumps(data, ensure_ascii=False, indent=2)


def to_csv(segments: list[dict], speakers: dict | None = None, delimiter: str = ";") -> str:
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=delimiter, lineterminator="\r\n")
    w.writerow(["başlangıç", "bitiş", "konuşmacı", "metin"])
    for s in segments:
        w.writerow([fmt_clock(s["start"], ms=True), fmt_clock(s["end"], ms=True),
                    speaker_label(s.get("speaker"), speakers), (s.get("text") or "").strip()])
    return buf.getvalue()
