"""Kelime zamanlarından altyazı kesitleri (cue) üretir.

Kurallar: satır başına en çok karakter, kesit başına en çok satır, en uzun ve en kısa süre.
Satır sonları önce noktalama yerlerinde, sonra en dengeli bölünmede yapılır.
Karakterler NFC biçiminde sayılır, yani ç ğ ı İ ö ş ü her biri tek karakterdir.
"""
from __future__ import annotations

import unicodedata
from dataclasses import dataclass
from functools import lru_cache

SENT_END = (".", "?", "!", "…")
CLAUSE_END = (",", ";", ":")
SENT_BONUS = 220.0
CLAUSE_BONUS = 120.0


@dataclass(frozen=True)
class Rules:
    max_chars: int = 42
    max_lines: int = 2
    max_dur: float = 7.0
    min_dur: float = 1.0

    @classmethod
    def from_dict(cls, d: dict | None) -> "Rules":
        d = d or {}
        base = cls()
        return cls(
            max_chars=max(10, int(d.get("max_chars", base.max_chars))),
            max_lines=max(1, int(d.get("max_lines", base.max_lines))),
            max_dur=max(1.0, float(d.get("max_dur", base.max_dur))),
            min_dur=max(0.0, float(d.get("min_dur", base.min_dur))),
        )


def _n(s: str) -> str:
    return unicodedata.normalize("NFC", s)


def text_len(s: str) -> int:
    return len(_n(s))


def seg_words(seg: dict) -> list[dict]:
    """Bölümün kelimelerini {'word','start','end'} olarak döndürür. Zaman eksikse doldurur."""
    start, end = float(seg.get("start", 0)), float(seg.get("end", 0))
    raw = [w for w in (seg.get("words") or []) if str(w.get("word", "")).strip()]
    if not raw:
        toks = _n(seg.get("text", "")).split()
        if not toks:
            return []
        weights = [max(1, len(t)) for t in toks]
        total = sum(weights)
        t, out = start, []
        for tok, wt in zip(toks, weights):
            d = (end - start) * wt / total
            out.append({"word": tok, "start": t, "end": t + d})
            t += d
        return out
    out = [{"word": _n(str(w["word"]).strip()), "start": w.get("start"), "end": w.get("end")} for w in raw]
    # eksik zamanları komşulardan doldur
    n = len(out)
    i = 0
    while i < n:
        if out[i]["start"] is None or out[i]["end"] is None:
            j = i
            while j < n and (out[j]["start"] is None or out[j]["end"] is None):
                j += 1
            left = out[i - 1]["end"] if i > 0 else start
            right = out[j]["start"] if j < n else end
            right = max(right, left)
            span = (right - left) / (j - i)
            for k in range(i, j):
                out[k]["start"] = left + span * (k - i)
                out[k]["end"] = left + span * (k - i + 1)
            i = j
        else:
            i += 1
    for w in out:
        w["start"], w["end"] = float(w["start"]), float(max(w["end"], w["start"]))
    return out


def _lines_needed(tokens: list[str], max_chars: int) -> int:
    """Açgözlü doldurma ile gereken en az satır sayısı."""
    lines, cur = 1, 0
    for t in tokens:
        ln = text_len(t)
        if cur == 0:
            cur = ln
        elif cur + 1 + ln <= max_chars:
            cur += 1 + ln
        else:
            lines += 1
            cur = ln
    return lines


def _fits(tokens: list[str], rules: Rules) -> bool:
    return _lines_needed(tokens, rules.max_chars) <= rules.max_lines


def _ends(tok: str, marks: tuple) -> bool:
    return tok.rstrip("\"'”’)»]").endswith(marks)


def _balanced_lines(tokens: tuple, k: int, max_chars: int):
    n = len(tokens)
    lens = [text_len(t) for t in tokens]
    total = sum(lens) + n - 1
    target = total / k

    def span(i, j):
        return sum(lens[i:j]) + (j - i - 1)

    @lru_cache(maxsize=None)
    def best(i, left):
        if left == 1:
            ln = span(i, n)
            return (((ln - target) ** 2), (n,)) if ln <= max_chars else None
        res = None
        for j in range(i + 1, n - left + 2):
            ln = span(i, j)
            if ln > max_chars:
                break
            sub = best(j, left - 1)
            if sub is None:
                continue
            bonus = SENT_BONUS if _ends(tokens[j - 1], SENT_END) else CLAUSE_BONUS if _ends(tokens[j - 1], CLAUSE_END) else 0.0
            cost = (ln - target) ** 2 + sub[0] - bonus
            if res is None or cost < res[0]:
                res = (cost, (j,) + sub[1])
        return res

    r = best(0, k)
    if r is None:
        return None
    out, prev = [], 0
    for cut in r[1]:
        out.append(" ".join(tokens[prev:cut]))
        prev = cut
    return out


def layout_lines(tokens: list[str], max_chars: int, max_lines: int) -> list[str]:
    """Kelimeleri doğal ve dengeli satırlara böler."""
    if not tokens:
        return []
    one = " ".join(tokens)
    if text_len(one) <= max_chars:
        return [one]
    need = _lines_needed(tokens, max_chars)
    for k in range(max(2, need), max_lines + 1):
        r = _balanced_lines(tuple(tokens), k, max_chars)
        if r:
            return r
    # tek bir kelime satıra sığmıyorsa açgözlü doldur
    lines, cur = [], ""
    for t in tokens:
        if not cur:
            cur = t
        elif text_len(cur) + 1 + text_len(t) <= max_chars:
            cur += " " + t
        else:
            lines.append(cur)
            cur = t
    lines.append(cur)
    return lines


def _best_break(cur: list[dict]) -> int:
    """Taşma olduğunda kesitin hangi kelimeden sonra bitirileceği (noktalamaya öncelik)."""
    n = len(cur)
    for j in range(n - 1, max(0, (n - 1) // 2), -1):
        if _ends(cur[j - 1]["word"], SENT_END + CLAUSE_END):
            return j
    return n


def _group_words(words: list[dict], rules: Rules) -> list[list[dict]]:
    groups: list[list[dict]] = []
    cur: list[dict] = []
    i = 0
    while i < len(words):
        w = words[i]
        if cur:
            toks = [x["word"] for x in cur] + [w["word"]]
            if not _fits(toks, rules) or (w["end"] - cur[0]["start"]) > rules.max_dur:
                k = _best_break(cur)
                groups.append(cur[:k])
                cur = cur[k:]
                continue
        cur.append(w)
        i += 1
        if _ends(w["word"], SENT_END):
            filled = text_len(" ".join(x["word"] for x in cur))
            if filled >= 0.4 * rules.max_chars * rules.max_lines or (cur[-1]["end"] - cur[0]["start"]) >= rules.min_dur * 2:
                groups.append(cur)
                cur = []
    if cur:
        groups.append(cur)
    return groups


def _fix_orphans(groups: list[list[dict]], rules: Rules) -> list[list[dict]]:
    """Cümle sonu olmayan tek kelimelik kuyrukları, önceki kesitten bir kelime alarak dengeler."""
    for i in range(1, len(groups)):
        prev, cur = groups[i - 1], groups[i]
        if len(cur) == 1 and len(prev) >= 3 and not _ends(cur[0]["word"], SENT_END) and not _ends(prev[-1]["word"], SENT_END + CLAUSE_END):
            moved = [prev[-1]] + cur
            if _fits([w["word"] for w in moved], rules) and moved[-1]["end"] - moved[0]["start"] <= rules.max_dur:
                groups[i - 1], groups[i] = prev[:-1], moved
    return groups


def _merge_short(groups: list[list[dict]], rules: Rules) -> list[list[dict]]:
    out: list[list[dict]] = []
    i = 0
    while i < len(groups):
        g = groups[i]
        dur = g[-1]["end"] - g[0]["start"]
        if dur < rules.min_dur:
            if i + 1 < len(groups):
                m = g + groups[i + 1]
                if _fits([x["word"] for x in m], rules) and m[-1]["end"] - m[0]["start"] <= rules.max_dur:
                    groups[i + 1] = m
                    i += 1
                    continue
            if out:
                m = out[-1] + g
                if _fits([x["word"] for x in m], rules) and m[-1]["end"] - m[0]["start"] <= rules.max_dur:
                    out[-1] = m
                    i += 1
                    continue
        out.append(g)
        i += 1
    return out


def build_cues(segments: list[dict], rules: Rules | dict | None = None) -> list[dict]:
    """Bölümlerden altyazı kesitleri üretir. Kesitler bölüm sınırını geçmez."""
    if not isinstance(rules, Rules):
        rules = Rules.from_dict(rules)
    cues: list[dict] = []
    for si, seg in enumerate(segments):
        words = seg_words(seg)
        if not words:
            continue
        # kelime indeksleri için sıra numarası ekle
        for wi, w in enumerate(words):
            w["_i"] = wi
        groups = _merge_short(_fix_orphans(_group_words(words, rules), rules), rules)
        for g in groups:
            toks = [x["word"] for x in g]
            lines = layout_lines(toks, rules.max_chars, rules.max_lines)
            cues.append({
                "start": g[0]["start"], "end": g[-1]["end"], "lines": lines, "text": "\n".join(lines),
                "seg": si, "seg_id": seg.get("id"), "w0": g[0]["_i"], "w1": g[-1]["_i"] + 1,
                "speaker": seg.get("speaker"),
            })
    cues.sort(key=lambda c: (c["start"], c["end"]))
    # çakışmaları gider, en kısa süreyi sağla
    for i, c in enumerate(cues):
        nxt = cues[i + 1]["start"] if i + 1 < len(cues) else None
        if nxt is not None and c["end"] > nxt and nxt > c["start"]:
            c["end"] = nxt
        if c["end"] - c["start"] < rules.min_dur:
            want = c["start"] + rules.min_dur
            c["end"] = min(want, nxt) if nxt is not None and nxt > c["start"] else want
    return cues
