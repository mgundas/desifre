import json
import shutil
import time

import pytest

from app import db

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None and not __import__("app.pipeline.audio", fromlist=["x"]).ffmpeg_path(),
                                reason="ffmpeg gerekli")


def upload(client, wav_file, name="Görüşme Çağrı.wav", **opts):
    r = client.post("/api/jobs", params={"filename": name, "options": json.dumps(opts)}, content=wav_file.read_bytes())
    assert r.status_code == 200, r.text
    return r.json()["id"]


def wait_status(client, job_id, wanted, timeout=20):
    end = time.time() + timeout
    status = None
    while time.time() < end:
        status = client.get(f"/api/jobs/{job_id}").json()["status"]
        if status in wanted:
            return status
        time.sleep(0.05)
    raise AssertionError(f"beklenen durum {wanted}, son durum {status}")


def test_full_flow_upload_edit_export(client, wav_file):
    jid = upload(client, wav_file, diarize=True)
    assert wait_status(client, jid, {"tamamlandı"}) == "tamamlandı"
    tr = client.get(f"/api/transcripts/{jid}").json()
    assert tr["title"] == "Görüşme Çağrı"
    assert tr["segments"] and tr["segments"][0]["words"]
    assert set(tr["speakers"]) == {"SPEAKER_00", "SPEAKER_01"}
    assert tr["duration"] == pytest.approx(3.0, abs=0.2)

    segs = tr["segments"]
    segs[0]["text"] = "Düzenlenmiş çağrı metni"
    segs[0]["words"] = [{"word": w, "start": 0.1 * i, "end": 0.1 * i + 0.09} for i, w in enumerate(segs[0]["text"].split())]
    speakers = {**tr["speakers"], "SPEAKER_00": {"name": "Ayşe", "color": "#3b82f6"}}
    r = client.put(f"/api/transcripts/{jid}", json={"title": "Şubat Toplantısı", "segments": segs, "speakers": speakers})
    assert r.status_code == 200

    srt = client.get(f"/api/transcripts/{jid}/export/srt", params={"speaker_prefix": "1"})
    assert srt.status_code == 200
    assert srt.content.startswith(b"\xef\xbb\xbf")  # BOM varsayılan açık
    text = srt.content.decode("utf-8-sig")
    assert "Ayşe: Düzenlenmiş çağrı metni" in text
    assert "filename*=UTF-8''%C5%9Eubat%20Toplant%C4%B1s%C4%B1.srt" in srt.headers["content-disposition"]

    assert not client.get(f"/api/transcripts/{jid}/export/vtt").content.startswith(b"\xef\xbb\xbf")
    assert client.get(f"/api/transcripts/{jid}/export/srt", params={"bom": "0"}).content[:3] != b"\xef\xbb\xbf"
    for fmt in ("txt", "csv", "json", "docx"):
        assert client.get(f"/api/transcripts/{jid}/export/{fmt}").status_code == 200
    assert client.get(f"/api/transcripts/{jid}/export/xyz").status_code == 404
    assert b"D\xc3\xbczenlenmi\xc5\x9f" in client.get(f"/api/transcripts/{jid}/export/json").content


def test_media_endpoint_and_cues(client, wav_file):
    jid = upload(client, wav_file)
    wait_status(client, jid, {"tamamlandı"})
    r = client.get(f"/api/transcripts/{jid}/media")
    assert r.status_code == 200 and r.content == wav_file.read_bytes()
    segs = client.get(f"/api/transcripts/{jid}").json()["segments"]
    cues = client.post("/api/cues", json={"segments": segs, "rules": {"max_chars": 20}}).json()["cues"]
    assert cues and all(len(line) <= 20 for c in cues for line in c["lines"])


def test_cancel_queued_and_running(client, wav_file, monkeypatch):
    monkeypatch.setenv("DESIFRE_FAKE_DELAY", "0.3")
    first = upload(client, wav_file, name="bir.wav")
    second = upload(client, wav_file, name="iki.wav")
    wait_status(client, first, {"işleniyor"})
    assert client.post(f"/api/jobs/{second}/cancel").status_code == 200
    assert client.get(f"/api/jobs/{second}").json()["status"] == "iptal"
    assert client.post(f"/api/jobs/{first}/cancel").status_code == 200
    assert wait_status(client, first, {"iptal"}) == "iptal"
    assert client.post(f"/api/jobs/{first}/cancel").status_code == 409
    # iptal edilen iş yeniden denenebilir
    monkeypatch.setenv("DESIFRE_FAKE_DELAY", "0")
    assert client.post(f"/api/jobs/{first}/retry").status_code == 200
    assert wait_status(client, first, {"tamamlandı"}) == "tamamlandı"


def test_failed_job_and_retry(client, wav_file, monkeypatch):
    monkeypatch.setenv("DESIFRE_FAKE_FAIL", "1")
    jid = upload(client, wav_file)
    assert wait_status(client, jid, {"hata"}) == "hata"
    assert client.get(f"/api/jobs/{jid}").json()["error"] == "GPU belleği yetersiz. Daha küçük bir model deneyin."
    monkeypatch.delenv("DESIFRE_FAKE_FAIL")
    assert client.post(f"/api/jobs/{jid}/retry").status_code == 200
    assert wait_status(client, jid, {"tamamlandı"}) == "tamamlandı"
    assert client.post(f"/api/jobs/{jid}/retry").status_code == 409


def test_restart_recovery(data_dir, wav_file, monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import create_app
    monkeypatch.setenv("DESIFRE_FAKE_DELAY", "0.2")
    with TestClient(create_app()) as c:
        jid = upload(c, wav_file)
        wait_status(c, jid, {"işleniyor"})
    # kapanış, çalışan işi kuyruğa geri koyar. Çökmeyi taklit etmek için yeniden "işleniyor" yapalım.
    db.update_job(jid, status="işleniyor", progress=40)
    monkeypatch.setenv("DESIFRE_FAKE_DELAY", "0")
    with TestClient(create_app()) as c2:
        assert wait_status(c2, jid, {"beklemede", "işleniyor", "tamamlandı"}) in {"beklemede", "işleniyor", "tamamlandı"}
        assert wait_status(c2, jid, {"tamamlandı"}) == "tamamlandı"


def test_recover_function_resets_running(data_dir):
    db.init()
    jid = db.create_job("a.wav", "uploads/a.wav", 1, {}, "a")
    db.claim_job(jid)
    assert db.get_job(jid)["status"] == "işleniyor"
    assert db.recover_after_restart() == 1
    assert db.get_job(jid)["status"] == "beklemede"


def test_reorder_queue(client, wav_file, monkeypatch):
    monkeypatch.setenv("DESIFRE_FAKE_DELAY", "0.5")
    a = upload(client, wav_file, name="a.wav")
    wait_status(client, a, {"işleniyor"})
    b = upload(client, wav_file, name="b.wav")
    c = upload(client, wav_file, name="c.wav")
    assert [j["id"] for j in client.get("/api/jobs").json()["jobs"]] == [a, b, c]
    client.post("/api/jobs/reorder", json={"ids": [c, b]})
    assert [j["id"] for j in client.get("/api/jobs").json()["jobs"]] == [a, c, b]
    for j in (a, b, c):
        client.post(f"/api/jobs/{j}/cancel")


def test_upload_validation(client, wav_file, monkeypatch):
    r = client.post("/api/jobs", params={"filename": "virus.exe"}, content=b"abc")
    assert r.status_code == 415 and "desteklenmiyor" in r.json()["detail"]
    assert client.post("/api/jobs", params={"filename": "a.wav"}, content=b"").status_code == 400
    assert client.post("/api/jobs", params={"filename": "a.wav", "options": '{"model":"x"}'}, content=b"abc").status_code == 400
    assert client.post("/api/jobs", params={"filename": "a.wav", "options": "{bozuk"}, content=b"abc").status_code == 400
    client.put("/api/settings", json={"max_upload_mb": 1})
    big = client.post("/api/jobs", params={"filename": "a.wav"}, content=b"0" * (1024 * 1024 + 10))
    assert big.status_code == 413 and "çok büyük" in big.json()["detail"]
    # başarısız yüklemeler diskte kalıntı bırakmamalı
    from app import config
    assert list(config.uploads_dir().iterdir()) == []


def test_undecodable_file_fails_with_turkish_message(client):
    r = client.post("/api/jobs", params={"filename": "bozuk.mp3"}, content="bu bir ses dosyası değil".encode() * 50)
    jid = r.json()["id"]
    assert wait_status(client, jid, {"hata"}) == "hata"
    assert "desteklenmiyor" in client.get(f"/api/jobs/{jid}").json()["error"]


def test_library_search_sort_delete(client, wav_file):
    a = upload(client, wav_file, name="Işıklı İstanbul.wav")
    b = upload(client, wav_file, name="Ankara toplantısı.wav")
    wait_status(client, a, {"tamamlandı"})
    wait_status(client, b, {"tamamlandı"})
    titles = lambda **p: [i["title"] for i in client.get("/api/transcripts", params=p).json()["items"]]
    assert titles(q="ışıklı") == ["Işıklı İstanbul"]
    assert titles(q="IŞIKLI") == ["Işıklı İstanbul"]
    assert titles(q="IŞIKLI İSTANBUL") == ["Işıklı İstanbul"]
    both = {"Işıklı İstanbul", "Ankara toplantısı"}
    assert set(titles(q="IĞDIR")) == both  # metin içinde Türkçe büyük/küçük harfe duyarsız arama
    assert set(titles(q="şimdi ığdır")) == both
    assert titles(q="igdir") == []
    assert titles(q="100%") == []
    assert titles(sort="title", order="asc") == ["Ankara toplantısı", "Işıklı İstanbul"]
    assert client.get("/api/transcripts", params={"sort": "duration"}).status_code == 200

    from app import config
    assert client.delete(f"/api/transcripts/{a}", params={"delete_media": "false"}).status_code == 200
    kept = list((config.data_dir() / "kept_media").iterdir())
    assert [k.name for k in kept] == ["Işıklı İstanbul.wav"]
    assert client.delete(f"/api/transcripts/{b}", params={"delete_media": "true"}).status_code == 200
    assert not list(config.uploads_dir().glob("*.wav"))
    assert client.get(f"/api/transcripts/{b}").status_code == 404
    assert client.get("/api/transcripts").json()["items"] == []


def test_settings_roundtrip_masks_token(client):
    r = client.put("/api/settings", json={"hf_token": "hf_abcdefghijklmnop", "model": "small", "subtitle": {"max_chars": 30}})
    body = r.json()
    assert "hf_token" not in body and body["hf_token_set"] is True
    assert "abcdefghij" not in json.dumps(body)
    assert body["model"] == "small" and body["subtitle"]["max_chars"] == 30 and body["subtitle"]["max_lines"] == 2
    # belirteç alanı gönderilmezse silinmez
    client.put("/api/settings", json={"model": "tiny"})
    assert client.get("/api/settings").json()["hf_token_set"] is True
    assert client.put("/api/settings", json={"model": "yok"}).status_code == 400
    assert client.put("/api/settings", json={"subtitle": {"min_dur": 5, "max_dur": 2}}).status_code == 400


def test_system_info(client):
    d = client.get("/api/system").json()
    assert set(d) >= {"gpu", "cuda_available", "ffmpeg", "models", "storage"}
    assert {m["name"] for m in d["models"]} >= {"large-v3", "tiny"}


def test_host_and_origin_guard(client):
    assert client.get("/api/settings", headers={"host": "evil.example.com"}).status_code == 403
    assert client.put("/api/settings", json={}, headers={"origin": "http://evil.example.com"}).status_code == 403
    assert client.get("/api/settings", headers={"host": "127.0.0.1:7860"}).status_code == 200


def test_languages_endpoint(client):
    langs = client.get("/api/languages").json()["languages"]
    assert langs[0] == {"code": "tr", "name": "Türkçe"} and len(langs) >= 99


def make_media(tmp_path, name, args):
    import subprocess
    from app.pipeline import audio
    out = tmp_path / name
    subprocess.run([audio.ffmpeg_path(), "-y", "-loglevel", "error", *args, str(out)], check=True)
    return out


def test_video_mkv_and_wma_get_playable_previews(client, tmp_path):
    from app import config
    mkv = make_media(tmp_path, "klip.mkv", ["-f", "lavfi", "-i", "color=c=blue:s=160x120:d=2", "-f", "lavfi", "-i", "sine=f=440:d=2", "-shortest", "-c:v", "libx264", "-c:a", "aac"])
    wma = make_media(tmp_path, "ses.wma", ["-f", "lavfi", "-i", "sine=f=330:d=2", "-c:a", "wmav2"])
    mp4 = make_media(tmp_path, "klip.mp4", ["-f", "lavfi", "-i", "color=c=red:s=160x120:d=2", "-f", "lavfi", "-i", "sine=f=440:d=2", "-shortest", "-c:v", "libx264", "-c:a", "aac"])
    ids = {}
    for p in (mkv, wma, mp4):
        r = client.post("/api/jobs", params={"filename": p.name, "options": "{}"}, content=p.read_bytes())
        assert r.status_code == 200, r.text
        ids[p.suffix] = r.json()["id"]
    for jid in ids.values():
        assert wait_status(client, jid, {"tamamlandı", "hata"}, timeout=60) == "tamamlandı"
    tr = {ext: client.get(f"/api/transcripts/{jid}").json() for ext, jid in ids.items()}
    assert tr[".mkv"]["is_video"] and tr[".mp4"]["is_video"] and not tr[".wma"]["is_video"]
    mkv_media = client.get(f"/api/transcripts/{ids['.mkv']}/media")
    assert mkv_media.headers["content-type"] == "video/mp4"
    assert client.get(f"/api/transcripts/{ids['.wma']}/media").headers["content-type"] == "audio/mp4"
    assert client.get(f"/api/transcripts/{ids['.mp4']}/media").content == mp4.read_bytes()  # tarayıcı çalabilir, kopya yok
    assert len(list(config.uploads_dir().glob("*.preview.*"))) == 2
    # silinince önizleme dosyaları da gider
    client.delete(f"/api/transcripts/{ids['.mkv']}", params={"delete_media": "true"})
    client.delete(f"/api/transcripts/{ids['.wma']}", params={"delete_media": "true"})
    assert not list(config.uploads_dir().glob("*.preview.*"))


def test_media_supports_range_requests_for_seeking(client, wav_file):
    jid = upload(client, wav_file)
    wait_status(client, jid, {"tamamlandı"})
    r = client.get(f"/api/transcripts/{jid}/media", headers={"Range": "bytes=100-199"})
    assert r.status_code == 206 and len(r.content) == 100
    assert r.content == wav_file.read_bytes()[100:200]
    assert r.headers["content-range"].startswith("bytes 100-199/")
