"""Küçük yardımcılar: Türkçe büyük/küçük harf, dosya adı temizleme, zaman biçimleri."""
from __future__ import annotations

import re
import unicodedata

_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
_BAD_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def tr_lower(s: str) -> str:
    """Türkçe kurallarına göre küçük harf (İ -> i, I -> ı)."""
    return unicodedata.normalize("NFC", s).replace("İ", "i").replace("I", "ı").lower()


def tr_upper(s: str) -> str:
    """Türkçe kurallarına göre büyük harf (i -> İ, ı -> I)."""
    return unicodedata.normalize("NFC", s).replace("i", "İ").replace("ı", "I").upper()


def tr_contains(haystack: str, needle: str) -> bool:
    return tr_lower(needle) in tr_lower(haystack)


def sanitize_filename(name: str, default: str = "dosya", max_len: int = 120) -> str:
    """Dosya sistemine uygun ad üretir, Türkçe harfleri korur."""
    name = unicodedata.normalize("NFC", name or "")
    name = _BAD_CHARS.sub("_", name)
    name = re.sub(r"\s+", " ", name).strip(" .")
    if not name:
        return default
    if name.split(".")[0].upper() in _RESERVED:
        name = "_" + name
    return name[:max_len].rstrip(" .") or default


def safe_ext(filename: str, allowed: set[str]) -> str | None:
    """Uzantıyı küçük harfle döndürür; izin verilmiyorsa None."""
    m = re.search(r"\.([A-Za-z0-9]{1,5})$", filename or "")
    if not m:
        return None
    ext = m.group(1).lower()
    return ext if ext in allowed else None


def fmt_clock(sec: float, ms: bool = False, sep: str = ".") -> str:
    """Saniyeyi SS:DD:ss (isteğe bağlı .mmm) biçimine çevirir."""
    total_ms = max(0, int(round(sec * 1000)))
    h, rem = divmod(total_ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1000)
    base = f"{h:02d}:{m:02d}:{s:02d}"
    return f"{base}{sep}{milli:03d}" if ms else base


def speaker_label(spk: str | None, speakers: dict | None) -> str:
    """Konuşmacı için gösterilecek ad (verilmiş ad yoksa 'Konuşmacı N')."""
    if not spk:
        return ""
    info = (speakers or {}).get(spk) or {}
    name = (info.get("name") or "").strip()
    if name:
        return name
    m = re.fullmatch(r"SPEAKER_(\d+)", spk)
    if m:
        return f"Konuşmacı {int(m.group(1)) + 1}"
    return spk
