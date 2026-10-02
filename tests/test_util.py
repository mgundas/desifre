from app.util import fmt_clock, sanitize_filename, speaker_label, tr_lower, tr_upper, tr_contains
from app.export.srt_vtt import srt_time, vtt_time


def test_turkish_case():
    assert tr_lower("IŞIK İSTANBUL") == "ışık istanbul"
    assert tr_upper("ışık istanbul") == "IŞIK İSTANBUL"
    assert tr_upper("iyi") == "İYİ"
    assert tr_lower("İ") == "i" and tr_lower("I") == "ı"


def test_turkish_search_is_case_insensitive():
    assert tr_contains("Işıklı İstanbul sokakları", "ışıklı")
    assert tr_contains("Işıklı İstanbul sokakları", "İSTANBUL")
    assert tr_contains("ığdır", "IĞDIR")
    assert not tr_contains("ığdır", "igdir")


def test_time_formats():
    assert srt_time(62.345) == "00:01:02,345"
    assert vtt_time(62.345) == "00:01:02.345"
    assert srt_time(3661.0) == "01:01:01,000"
    assert srt_time(0.9996) == "00:00:01,000"
    assert fmt_clock(75) == "00:01:15"


def test_sanitize_filename_keeps_turkish_letters():
    assert sanitize_filename("Toplantı: Çağrı/Şubat?.mp3") == "Toplantı_ Çağrı_Şubat_.mp3"
    assert sanitize_filename("  ..  ") == "dosya"
    assert sanitize_filename("CON") == "_CON"
    assert sanitize_filename("a" * 300).__len__() == 120
    assert sanitize_filename("ğüşiöçİ") == "ğüşiöçİ"


def test_speaker_label():
    assert speaker_label("SPEAKER_00", {}) == "Konuşmacı 1"
    assert speaker_label("SPEAKER_01", {"SPEAKER_01": {"name": "Ayşe"}}) == "Ayşe"
    assert speaker_label(None, {}) == ""
