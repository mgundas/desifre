"""Metin dışa aktarma ve paragraf gruplama."""
from __future__ import annotations

from ..util import fmt_clock, speaker_label

PARAGRAPH_GAP = 2.0
PARAGRAPH_MAX_CHARS = 700


def group_paragraphs(segments: list[dict]) -> list[dict]:
    """Aynı konuşmacının ardışık bölümlerini paragrafta toplar.

    Konuşmacı değişince, bölümler arası boşluk 2 sn'yi aşınca ya da paragraf çok uzayınca yeni paragraf başlar.
    """
    paras: list[dict] = []
    for seg in segments:
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        last = paras[-1] if paras else None
        if (last and last["speaker"] == seg.get("speaker")
                and seg["start"] - last["end"] <= PARAGRAPH_GAP and len(last["text"]) < PARAGRAPH_MAX_CHARS):
            last["text"] += " " + text
            last["end"] = seg["end"]
        else:
            paras.append({"speaker": seg.get("speaker"), "start": seg["start"], "end": seg["end"], "text": text})
    return paras


def to_txt(segments: list[dict], speakers: dict | None = None, timestamps: bool = True,
           show_speakers: bool = True) -> str:
    out = []
    for p in group_paragraphs(segments):
        head = []
        if timestamps:
            head.append(f"[{fmt_clock(p['start'])}]")
        label = speaker_label(p["speaker"], speakers) if show_speakers else ""
        if label:
            head.append(f"{label}:")
        out.append((" ".join(head) + " " if head else "") + p["text"])
    return "\n\n".join(out) + ("\n" if out else "")
