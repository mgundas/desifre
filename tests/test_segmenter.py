from app.export.segmenter import Rules, build_cues, layout_lines, seg_words, text_len


def make_seg(text, start=0.0, per_word=0.4, speaker=None, gap=0.05):
    words, t = [], start
    for w in text.split():
        words.append({"word": w, "start": round(t, 3), "end": round(t + per_word, 3)})
        t += per_word + gap
    return {"id": "x", "start": words[0]["start"], "end": words[-1]["end"], "speaker": speaker, "text": text, "words": words}


def flat(cues):
    return " ".join(c["text"].replace(chr(10), " ") for c in cues)


def test_line_length_and_count_respected():
    text = "Bu uzun bir cümle olup altyazı satırlarına doğal biçimde bölünmesi gerekiyor ve her satır sınırı aşmamalı elbette"
    cues = build_cues([make_seg(text)], Rules(max_chars=30, max_lines=2, max_dur=20, min_dur=0.5))
    assert len(cues) > 1
    for c in cues:
        assert len(c["lines"]) <= 2
        assert all(text_len(line) <= 30 for line in c["lines"])
    assert flat(cues) == text


def test_two_lines_are_balanced():
    lines = layout_lines("Bugün hava çok güzel olduğu için dışarıya çıkıp yürüyüş yaptık".split(), 42, 2)
    assert len(lines) == 2
    assert abs(text_len(lines[0]) - text_len(lines[1])) <= 12


def test_short_text_stays_on_one_line():
    assert layout_lines(["Merhaba", "dünya"], 42, 2) == ["Merhaba dünya"]


def test_max_duration_splits_cues():
    seg = make_seg("bir iki üç dört beş altı yedi sekiz dokuz on", per_word=1.0, gap=0.0)
    cues = build_cues([seg], Rules(max_chars=100, max_lines=2, max_dur=4.0, min_dur=1.0))
    assert len(cues) >= 3
    assert all(c["end"] - c["start"] <= 4.0 + 1e-6 for c in cues)


def test_min_duration_extends_short_cue():
    seg = make_seg("Evet.", per_word=0.3)
    cues = build_cues([seg], Rules(min_dur=1.0))
    assert len(cues) == 1
    assert cues[0]["end"] - cues[0]["start"] >= 1.0 - 1e-9


def test_min_duration_does_not_overlap_next_cue():
    segs = [make_seg("Evet.", start=0.0, per_word=0.2), make_seg("Hayır.", start=0.5, per_word=0.2)]
    cues = build_cues(segs, Rules(min_dur=1.0))
    assert cues[0]["end"] <= cues[1]["start"] + 1e-9


def test_breaks_at_sentence_punctuation():
    text = "Merhaba arkadaşlar bugün çok güzel gün. Şimdi başlayalım ve işe koyulalım hemen"
    cues = build_cues([make_seg(text)], Rules(max_chars=42, max_lines=1, max_dur=20, min_dur=0.2))
    assert cues[0]["text"].endswith("gün.")
    assert cues[1]["text"].startswith("Şimdi")


def test_prefers_clause_break_when_overflowing():
    text = "Eğer yarın yağmur yağarsa, evde kalıp kitap okuruz ve dinleniriz"
    lines = layout_lines(text.split(), 40, 2)
    assert lines[0].endswith("yağarsa,")


def test_turkish_characters_count_once():
    assert text_len("çğıİöşü") == 7
    # 'İ' birleşik karakter olarak gelse bile tek sayılır
    assert text_len("İ") == 1
    word = "çğıİöşü" * 3  # 21 karakter
    lines = layout_lines([word, word], 43, 2)
    assert lines == [word + " " + word]  # 43 karakter tek satıra sığar
    assert len(layout_lines([word, word], 42, 2)) == 2


def test_cues_do_not_cross_segments_and_keep_speaker():
    segs = [make_seg("Selam nasılsın", speaker="SPEAKER_00"), make_seg("İyiyim sağ ol", start=3.0, speaker="SPEAKER_01")]
    cues = build_cues(segs)
    assert [c["speaker"] for c in cues] == ["SPEAKER_00", "SPEAKER_01"]
    assert [c["seg"] for c in cues] == [0, 1]


def test_words_without_timing_are_interpolated():
    seg = {"id": "a", "start": 0.0, "end": 3.0, "text": "bir iki üç",
           "words": [{"word": "bir", "start": 0.0, "end": 1.0}, {"word": "iki"}, {"word": "üç", "start": 2.0, "end": 3.0}]}
    words = seg_words(seg)
    assert 1.0 <= words[1]["start"] < words[1]["end"] <= 2.0


def test_segment_without_words_is_synthesised():
    seg = {"id": "a", "start": 10.0, "end": 14.0, "text": "merhaba güzel dünya"}
    cues = build_cues([seg])
    assert cues and cues[0]["start"] == 10.0 and abs(cues[-1]["end"] - 14.0) < 1e-6


def test_single_very_long_word_does_not_hang():
    seg = make_seg("a" * 80 + " kısa")
    cues = build_cues([seg], Rules(max_chars=20, max_lines=2))
    assert cues


def test_no_single_word_orphan_after_duration_split():
    text = "bir iki üç dört beş altı yedi sekiz dokuz on"
    seg = make_seg(text, per_word=0.78, gap=0.0)
    cues = build_cues([seg], Rules(max_chars=100, max_lines=2, max_dur=7.0, min_dur=1.0))
    assert all(len(c["text"].split()) >= 2 for c in cues)
    assert flat(cues) == text


def test_cue_word_ranges_cover_every_word_once():
    seg = make_seg("bir iki üç dört beş altı yedi sekiz dokuz on on bir on iki", per_word=0.9, gap=0.0)
    cues = build_cues([seg], Rules(max_chars=20, max_lines=1, max_dur=4.0, min_dur=0.5))
    spans = [(c["w0"], c["w1"]) for c in cues]
    assert spans[0][0] == 0 and spans[-1][1] == len(seg["words"])
    assert all(spans[i][1] == spans[i + 1][0] for i in range(len(spans) - 1))
