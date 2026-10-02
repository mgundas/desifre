from app.pipeline.transcribe import _split_by_speaker, normalize_segment, resegment


def words(text, start=0.0, per=0.4, gap=0.05):
    out, t = [], start
    for w in text.split():
        out.append({"word": w, "start": round(t, 3), "end": round(t + per, 3)})
        t += per + gap
    return out


def seg_of(text, **kw):
    w = words(text, **kw)
    return {"start": w[0]["start"], "end": w[-1]["end"], "text": text, "words": w}


def test_resegment_splits_at_sentence_ends():
    out = resegment([seg_of("Merhaba arkadaşlar. Bugün hava güzel. Yarın yağmur yağacak mı?")])
    assert [s["text"] for s in out] == ["Merhaba arkadaşlar.", "Bugün hava güzel.", "Yarın yağmur yağacak mı?"]
    assert out[1]["start"] == out[1]["words"][0]["start"]


def test_resegment_splits_at_long_pause():
    w = words("bir iki üç") + words("dört beş altı", start=10.0)
    out = resegment([{"start": 0, "end": 11, "text": "x", "words": w}])
    assert len(out) == 2 and out[1]["text"] == "dört beş altı"


def test_resegment_splits_overlong_sentence_at_comma():
    text = " ".join(f"kelime{i}" + ("," if i == 15 else "") for i in range(40))
    out = resegment([seg_of(text, per=0.2, gap=0.0)], max_words=28)
    assert len(out) == 2 and out[0]["text"].endswith("kelime15,")


def test_resegment_keeps_short_answers_as_own_segment():
    out = resegment([seg_of("Evet tabii ki. Hayır")])
    assert [s["text"] for s in out] == ["Evet tabii ki.", "Hayır"]


def test_resegment_attaches_orphan_word_after_clause_split():
    w = words("Ama sonra, bence çok iyi oldu")
    out = resegment([{"start": 0, "end": 3, "text": "x", "words": w}], pause=0.01)
    assert all(len(s["words"]) >= 1 for s in out)
    assert " ".join(s["text"] for s in out) == "Ama sonra, bence çok iyi oldu"


def test_normalize_fills_missing_times_and_rebuilds_text():
    seg = {"start": 0, "end": 3, "text": "eski", "words": [{"word": "bir", "start": 0.0, "end": 1.0},
                                                         {"word": "iki"}, {"word": "üç", "start": 2.0, "end": 3.0}]}
    normalize_segment(seg)
    assert seg["text"] == "bir iki üç"
    assert all(isinstance(w["start"], float) and w["start"] <= w["end"] for w in seg["words"])


def test_split_by_speaker_creates_turns_and_absorbs_single_word_islands():
    w = words("selam nasılsın iyiyim sen nasılsın ben de iyiyim")
    for i, x in enumerate(w):
        x["speaker"] = "SPEAKER_00" if i < 2 else "SPEAKER_01"
    w[4]["speaker"] = "SPEAKER_00"  # tek kelimelik kopma
    out = _split_by_speaker({"start": 0, "end": 4, "speaker": "SPEAKER_00", "text": "", "words": w})
    assert [s["speaker"] for s in out] == ["SPEAKER_00", "SPEAKER_01"]
    assert out[0]["text"] == "selam nasılsın" and out[1]["text"].startswith("iyiyim sen")
    assert all("speaker" not in x for s in out for x in s["words"])
