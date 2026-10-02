import csv
import io
import json

from docx import Document

from app.export import docx_export, json_csv, srt_vtt, txt
from tests.conftest import sample_segments

SPK = {"SPEAKER_00": {"name": "Ayşe", "color": "#3b82f6"}, "SPEAKER_01": {"name": "", "color": "#f97316"}}


def test_txt_with_timestamps_and_speakers():
    out = txt.to_txt(sample_segments(), SPK, timestamps=True, show_speakers=True)
    assert out.startswith("[00:00:00] Ayşe: Merhaba nasılsınız bugün.")
    assert "[00:00:02] Konuşmacı 2: İyiyim, teşekkür ederim." in out
    assert out.count("\n\n") == 1


def test_txt_plain():
    out = txt.to_txt(sample_segments(), SPK, timestamps=False, show_speakers=False)
    assert out == "Merhaba nasılsınız bugün.\n\nİyiyim, teşekkür ederim.\n"


def test_txt_groups_same_speaker_into_one_paragraph():
    segs = sample_segments()
    segs[1]["speaker"] = "SPEAKER_00"
    out = txt.to_txt(segs, SPK, timestamps=False, show_speakers=True)
    assert out.strip() == "Ayşe: Merhaba nasılsınız bugün. İyiyim, teşekkür ederim."


def test_txt_splits_paragraph_on_long_gap():
    segs = sample_segments()
    segs[1]["speaker"] = "SPEAKER_00"
    segs[1]["start"] += 10
    segs[1]["end"] += 10
    assert txt.to_txt(segs, SPK, timestamps=False, show_speakers=False).count("\n\n") == 1


def test_srt_format():
    out = srt_vtt.to_srt(sample_segments(), SPK)
    blocks = out.strip().split("\n\n")
    assert blocks[0].splitlines()[0] == "1"
    assert blocks[0].splitlines()[1] == "00:00:00,000 --> 00:00:02,000"
    assert blocks[0].splitlines()[2] == "Merhaba nasılsınız bugün."
    assert "İyiyim, teşekkür ederim." in blocks[1]


def test_vtt_format_uses_dots_and_header():
    out = srt_vtt.to_vtt(sample_segments(), SPK)
    assert out.startswith("WEBVTT\n\n")
    assert "00:00:00.000 --> 00:00:02.000" in out
    assert "," not in out.splitlines()[2]


def test_srt_speaker_prefix_only_on_change():
    segs = sample_segments()
    out = srt_vtt.to_srt(segs, SPK, speaker_prefix=True)
    assert "Ayşe: Merhaba" in out
    assert "Konuşmacı 2: İyiyim," in out


def test_vtt_escapes_markup():
    segs = sample_segments()
    segs[0]["words"][0]["word"] = "<b>&"
    assert "&lt;b&gt;&amp;" in srt_vtt.to_vtt(segs, SPK)


def test_csv_semicolon_and_quoting():
    segs = sample_segments()
    segs[0]["text"] = 'Merhaba; "dünya"'
    out = json_csv.to_csv(segs, SPK, ";")
    rows = list(csv.reader(io.StringIO(out), delimiter=";"))
    assert rows[0] == ["başlangıç", "bitiş", "konuşmacı", "metin"]
    assert rows[1] == ["00:00:00.000", "00:00:02.000", "Ayşe", 'Merhaba; "dünya"']
    assert rows[2][2] == "Konuşmacı 2"


def test_json_roundtrip_keeps_word_timings():
    tr = {"title": "Görüşme", "language": "tr", "duration": 4.0, "model": "tiny", "speakers": SPK, "segments": sample_segments()}
    data = json.loads(json_csv.to_json(tr))
    assert data["title"] == "Görüşme"
    assert data["segments"][1]["words"][0] == {"word": "İyiyim,", "start": 2.2, "end": 2.9}
    assert "İyiyim" in json_csv.to_json(tr)  # ensure_ascii kapalı


def test_docx_contents():
    tr = {"title": "Toplantı Notları", "language": "tr", "duration": 65.0, "model": "tiny", "created_at": 1_700_000_000,
          "speakers": SPK, "segments": sample_segments()}
    doc = Document(io.BytesIO(docx_export.to_docx(tr, timestamps=True, show_speakers=True)))
    texts = [p.text for p in doc.paragraphs]
    assert texts[0] == "Toplantı Notları"
    assert "Süre: 00:01:05" in texts[1] and "Dil: Türkçe" in texts[1] and "Tarih:" in texts[1]
    assert any(t.startswith("[00:00:00] Ayşe: Merhaba") for t in texts)
    assert any("Konuşmacı 2: İyiyim, teşekkür ederim." in t for t in texts)
