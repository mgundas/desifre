"""Whisper'ın desteklediği diller ve Türkçe adları."""
from __future__ import annotations

from .util import tr_lower

LANGUAGES: dict[str, str] = {
    "tr": "Türkçe", "en": "İngilizce", "de": "Almanca", "fr": "Fransızca", "es": "İspanyolca", "it": "İtalyanca",
    "pt": "Portekizce", "ru": "Rusça", "ar": "Arapça", "fa": "Farsça", "zh": "Çince", "yue": "Kantonca",
    "ja": "Japonca", "ko": "Korece", "nl": "Felemenkçe", "pl": "Lehçe", "uk": "Ukraynaca", "el": "Yunanca",
    "bg": "Bulgarca", "ro": "Romence", "hu": "Macarca", "cs": "Çekçe", "sk": "Slovakça", "sv": "İsveççe",
    "no": "Norveççe", "nn": "Norveççe (Nynorsk)", "da": "Danca", "fi": "Fince", "he": "İbranice", "hi": "Hintçe",
    "ur": "Urduca", "bn": "Bengalce", "ta": "Tamilce", "te": "Teluguca", "kn": "Kannadaca", "ml": "Malayalamca",
    "mr": "Marathi", "gu": "Güceratça", "pa": "Pencapça", "ne": "Nepalce", "si": "Seylanca", "id": "Endonezce",
    "ms": "Malayca", "vi": "Vietnamca", "th": "Tayca", "tl": "Tagalogca", "km": "Kmerce", "lo": "Laoca",
    "my": "Burmaca", "mn": "Moğolca", "kk": "Kazakça", "uz": "Özbekçe", "tk": "Türkmence", "tg": "Tacikçe",
    "az": "Azerice", "ka": "Gürcüce", "hy": "Ermenice", "be": "Belarusça", "sr": "Sırpça", "hr": "Hırvatça",
    "bs": "Boşnakça", "sl": "Slovence", "mk": "Makedonca", "sq": "Arnavutça", "lt": "Litvanca", "lv": "Letonca",
    "et": "Estonca", "is": "İzlandaca", "cy": "Galce", "br": "Bretonca", "eu": "Baskça",
    "ca": "Katalanca", "gl": "Galiçyaca", "oc": "Oksitanca", "lb": "Lüksemburgca", "mt": "Maltaca",
    "la": "Latince", "sa": "Sanskritçe", "af": "Afrikaanca", "sw": "Svahili", "am": "Amharca", "so": "Somalice",
    "ha": "Hausaca", "yo": "Yorubaca", "sn": "Shona", "ln": "Lingala", "mg": "Malagasice", "ps": "Peştuca",
    "sd": "Sindhice", "as": "Assamca", "yi": "Yidiş", "bo": "Tibetçe", "tt": "Tatarca", "ba": "Başkurtça",
    "fo": "Faroece", "ht": "Haiti Kreolü", "mi": "Maorice", "haw": "Hawaii dili", "jw": "Cava dili",
    "su": "Sunda dili",
}


def language_name(code: str) -> str:
    return LANGUAGES.get(code, code or "")


def language_list() -> list[dict]:
    """Türkçe ada göre sıralı liste, Türkçe en başta."""
    items = [{"code": c, "name": n} for c, n in LANGUAGES.items()]
    items.sort(key=lambda x: (x["code"] != "tr", tr_lower(x["name"])))
    return items
