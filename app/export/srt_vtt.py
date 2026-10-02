"""SRT ve VTT dışa aktarma."""
from __future__ import annotations

from ..util import fmt_clock, speaker_label
from .segmenter import Rules, build_cues


def srt_time(sec: float) -> str:
    return fmt_clock(sec, ms=True, sep=",")


def vtt_time(sec: float) -> str:
    return fmt_clock(sec, ms=True, sep=".")


def _cue_lines(cues: list[dict], speakers: dict | None, prefix: bool) -> list[tuple[dict, list[str]]]:
    out, prev = [], object()
    for c in cues:
        lines = list(c["lines"])
        spk = c.get("speaker")
        if prefix and spk and spk != prev and lines:
            lines[0] = f"{speaker_label(spk, speakers)}: {lines[0]}"
        prev = spk
        out.append((c, lines))
    return out


def to_srt(segments: list[dict], speakers: dict | None = None, rules: Rules | dict | None = None,
           speaker_prefix: bool = False) -> str:
    cues = build_cues(segments, rules)
    parts = []
    for n, (c, lines) in enumerate(_cue_lines(cues, speakers, speaker_prefix), 1):
        parts.append(f"{n}\n{srt_time(c['start'])} --> {srt_time(c['end'])}\n" + "\n".join(lines) + "\n")
    return "\n".join(parts)


def _vtt_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def to_vtt(segments: list[dict], speakers: dict | None = None, rules: Rules | dict | None = None,
           speaker_prefix: bool = False) -> str:
    cues = build_cues(segments, rules)
    parts = ["WEBVTT\n"]
    for c, lines in _cue_lines(cues, speakers, speaker_prefix):
        parts.append(f"{vtt_time(c['start'])} --> {vtt_time(c['end'])}\n" + "\n".join(_vtt_escape(x) for x in lines) + "\n")
    return "\n".join(parts)
