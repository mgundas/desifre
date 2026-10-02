"""Tarayıcı testleri (Playwright). Varsayılan olarak sahte yazıya dökücüyle çalışır.

Gerçek modelle (tiny, CPU) çalıştırmak için: DESIFRE_E2E_ENGINE=real pytest tests/test_e2e_ui.py
"""
import json
import os
import shutil
import urllib.request
from pathlib import Path

import pytest

pytest.importorskip("playwright")
from playwright.sync_api import expect, sync_playwright  # noqa: E402

from tests.e2e_helpers import ROOT, Server  # noqa: E402

SAMPLE = ROOT / "tests" / "data" / "ornek_tr.wav"
SHOTS = ROOT / "tests" / "_artifacts" / "screenshots"
ENGINE = os.environ.get("DESIFRE_E2E_ENGINE", "fake")
pytestmark = pytest.mark.e2e
UPLOAD_OPTS = {"model": "tiny", "language": "tr", "diarize": False} if ENGINE == "real" else {"diarize": True}


def api(srv, method, path, body=None):
    req = urllib.request.Request(srv.url + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"} if body is not None else {})
    return json.loads(urllib.request.urlopen(req, timeout=30).read() or b"{}")


@pytest.fixture(scope="module")
def srv(tmp_path_factory):
    data = tmp_path_factory.mktemp("e2e") / "data"
    data.mkdir()
    server = Server(data, engine=ENGINE)
    server.wait_ready()
    if ENGINE == "real":
        api(server, "PUT", "/api/settings", {"device": "cpu", "model": "tiny"})
    yield server
    server.stop()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


@pytest.fixture()
def page(browser, srv):
    SHOTS.mkdir(parents=True, exist_ok=True)
    ctx = browser.new_context(viewport={"width": 1280, "height": 800}, locale="tr-TR", accept_downloads=True)
    pg = ctx.new_page()
    pg.errors = []
    pg.on("console", lambda m: pg.errors.append(m.text) if m.type == "error" else None)
    pg.on("pageerror", lambda e: pg.errors.append(str(e)))
    pg.on("dialog", lambda d: d.accept())
    yield pg
    assert not pg.errors, f"Tarayıcı hataları: {pg.errors}"
    ctx.close()


def shot(page, name):
    page.screenshot(path=str(SHOTS / f"{name}.png"))


def wait_done(srv, job_id, timeout=300):
    import time
    end = time.time() + timeout
    while time.time() < end:
        job = api(srv, "GET", f"/api/jobs/{job_id}")
        if job["status"] in ("tamamlandı", "hata", "iptal"):
            assert job["status"] == "tamamlandı", job.get("error")
            return
        time.sleep(0.5)
    raise AssertionError("iş zamanında bitmedi")


def new_job(srv, name="Röportaj Çağrı.wav"):
    q = urllib.parse.quote(name)
    o = urllib.parse.quote(json.dumps(UPLOAD_OPTS))
    req = urllib.request.Request(f"{srv.url}/api/jobs?filename={q}&options={o}", method="POST", data=SAMPLE.read_bytes())
    jid = json.loads(urllib.request.urlopen(req, timeout=60).read())["id"]
    wait_done(srv, jid)
    return jid


import urllib.parse  # noqa: E402


def open_editor(page, srv, jid):
    page.goto(f"{srv.url}/#/t/{jid}")
    page.wait_for_selector(".seg")
    page.wait_for_function("document.querySelector('audio, video') && document.querySelector('audio, video').readyState >= 1")


def saved(page):
    expect(page.locator(".save-status")).to_have_text("Kaydedildi", timeout=10000)


def edit_first(page, text):
    page.locator(".seg").first.locator(".seg-text").dblclick()
    ta = page.locator(".seg-edit")
    ta.fill(text)
    ta.press("Control+Enter")
    expect(page.locator(".seg-edit")).to_have_count(0)


def test_upload_through_ui_then_queue_and_library(page, srv):
    page.goto(srv.url)
    page.wait_for_selector(".dropzone")
    assert page.locator("html").get_attribute("lang") == "tr"
    shot(page, "01-yukleme")
    page.set_input_files("input[type=file]", str(SAMPLE))
    expect(page.locator(".file-name")).to_have_text("ornek_tr.wav")
    page.set_input_files("input[type=file]", {"name": "virus.exe", "mimeType": "application/octet-stream", "buffer": b"MZ"})
    expect(page.locator(".file-err")).to_contain_text("Dosya biçimi desteklenmiyor")
    page.locator(".file-row", has_text="virus.exe").get_by_role("button", name="Çıkar").click()
    if ENGINE == "real":
        page.get_by_label("Model").select_option("tiny")
    else:
        page.get_by_label("Konuşmacıları ayır").check()
    page.get_by_role("button", name="Kuyruğa ekle").click()
    page.wait_for_url("**#/queue")
    shot(page, "02-kuyruk")
    expect(page.locator(".chip-done").first).to_be_visible(timeout=300000)
    shot(page, "03-kuyruk-bitti")
    page.get_by_role("link", name="Kütüphane").click()
    page.wait_for_selector("table")
    # Türkçe büyük/küçük harfe duyarsız arama
    page.get_by_placeholder("Başlıkta ve metinde ara…").fill("ORNEK_TR")
    expect(page.locator("tbody tr")).to_have_count(1)
    page.get_by_placeholder("Başlıkta ve metinde ara…").fill("yokböylebirşey")
    expect(page.locator(".empty")).to_contain_text("Aramanızla eşleşen kayıt bulunamadı")
    page.get_by_placeholder("Başlıkta ve metinde ara…").fill("")
    shot(page, "04-kutuphane")


def test_edit_text_rename_speaker_and_export_srt(page, srv):
    jid = new_job(srv)
    open_editor(page, srv, jid)
    shot(page, "05-duzenleyici")
    edit_first(page, "Düzenlenmiş çığ şöyle İŞTE ığdır")
    expect(page.locator(".seg").first).to_contain_text("Düzenlenmiş çığ şöyle İŞTE ığdır")
    saved(page)
    if ENGINE == "fake":
        page.get_by_role("button", name="Konuşmacılar").click()
        name = page.locator(".spk-row input[type=text]").first
        name.fill("Ayşe")
        expect(page.locator(".spk-chip").first).to_contain_text("Ayşe")
        shot(page, "06-konusmacilar")
        saved(page)
    # sunucudaki kayıt
    tr = api(srv, "GET", f"/api/transcripts/{jid}")
    assert tr["segments"][0]["text"] == "Düzenlenmiş çığ şöyle İŞTE ığdır"
    assert [w["word"] for w in tr["segments"][0]["words"]] == tr["segments"][0]["text"].split()
    # SRT dışa aktarma
    page.get_by_role("button", name="Dışa aktar").click()
    dlg = page.locator("dialog")
    if ENGINE == "fake":
        dlg.get_by_label("Altyazıda konuşmacı adını yaz").check()
    shot(page, "07-disa-aktar")
    with page.expect_download() as dl:
        dlg.get_by_role("button", name="İndir").click()
    download = dl.value
    assert download.suggested_filename == "Röportaj Çağrı.srt"
    raw = Path(download.path()).read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig")
    assert "Düzenlenmiş çığ" in text and "İŞTE ığdır" in text.replace("\n", " ")
    if ENGINE == "fake":
        assert "Ayşe:" in text
    assert "-->" in text


def test_split_merge_undo_redo_and_timing(page, srv):
    jid = new_job(srv)
    open_editor(page, srv, jid)
    count = page.locator(".seg").count()
    first = page.locator(".seg").first
    first.locator(".seg-text").click()
    expect(first.locator(".seg-tools")).to_be_visible()
    # zaman ince ayarı
    start_before = first.locator(".seg-t-end").inner_text()
    first.get_by_role("button", name="+100 ms").nth(1).click()
    assert first.locator(".seg-t-end").inner_text() != start_before
    # böl: düzenleme modunda imleç konumundan
    first.locator(".seg-text").dblclick()
    ta = page.locator(".seg-edit")
    ta.evaluate("(el) => { el.setSelectionRange(8, 8); }")
    ta.press("Shift+Enter")
    expect(page.locator(".seg")).to_have_count(count + 1)
    # birleştir
    page.locator(".seg").first.locator(".seg-text").click()
    page.locator(".seg").first.get_by_role("button", name="Sonrakiyle birleştir").click()
    expect(page.locator(".seg")).to_have_count(count)
    # geri al / yinele
    page.locator("body").click(position={"x": 700, "y": 700})
    page.keyboard.press("Control+z")
    expect(page.locator(".seg")).to_have_count(count + 1)
    page.keyboard.press("Control+y")
    expect(page.locator(".seg")).to_have_count(count)
    page.keyboard.press("Control+z")
    page.keyboard.press("Control+z")
    page.keyboard.press("Control+z")
    saved(page)
    shot(page, "08-bol-birlestir")


def test_find_and_replace_with_turkish_letters(page, srv):
    jid = new_job(srv)
    open_editor(page, srv, jid)
    edit_first(page, "Işık İstanbul ışık ığdır")
    page.keyboard.press("Control+f")
    find = page.get_by_placeholder("Bul")
    find.fill("IŞIK")
    expect(page.locator(".find-count")).to_contain_text("2 eşleşme")
    assert page.locator(".w.match").count() >= 2
    shot(page, "09-bul")
    page.get_by_placeholder("Yerine").fill("lamba")
    page.get_by_role("button", name="Tümünü değiştir").click()
    expect(page.locator(".seg").first).to_contain_text("lamba İstanbul lamba ığdır")
    find.fill("İSTANBUL")
    expect(page.locator(".find-count")).to_contain_text("1 / ")
    page.get_by_role("button", name="Kapat").first.click()
    saved(page)


def test_keyboard_shortcuts_and_player(page, srv):
    jid = new_job(srv)
    open_editor(page, srv, jid)
    paused = lambda: page.evaluate("document.querySelector('audio, video').paused")
    page.locator("body").click(position={"x": 700, "y": 700})
    assert paused()
    page.keyboard.press("Space")
    assert not paused()
    page.keyboard.press("Space")
    assert paused()
    t0 = page.evaluate("document.querySelector('audio, video').currentTime")
    page.keyboard.press("Alt+ArrowRight")
    t1 = page.evaluate("document.querySelector('audio, video').currentTime")
    assert 4.5 < t1 - t0 < 5.5
    page.keyboard.press("Alt+ArrowLeft")
    assert abs(page.evaluate("document.querySelector('audio, video').currentTime") - t0) < 0.2
    # metin alanında Ctrl+Space oynatır
    page.locator(".seg").first.locator(".seg-text").dblclick()
    page.keyboard.press("Control+Space")
    assert not paused()
    page.keyboard.press("Control+Space")
    assert paused()
    page.keyboard.press("Escape")
    # hız
    page.get_by_label("Hız").select_option("1.5")
    assert page.evaluate("document.querySelector('audio, video').playbackRate") == 1.5
    # senkron: oynarken bir bölüm vurgulanır ve kelime işaretlenir
    page.evaluate("document.querySelector('audio, video').currentTime = 1.0")
    page.keyboard.press("Space")
    page.wait_for_selector(".seg.playing")
    page.wait_for_selector(".w.cur-word")
    page.keyboard.press("Space")
    # kısayol paneli
    page.keyboard.press("F1")
    expect(page.locator("dialog")).to_contain_text("Klavye kısayolları")
    shot(page, "10-kisayollar")
    page.keyboard.press("Escape")
    # bir kelimeye tıklayınca oraya gider
    page.locator(".seg").nth(2).locator(".w").nth(1).click()
    assert page.evaluate("document.querySelector('audio, video').currentTime") > 5


def test_subtitle_view_edit(page, srv):
    jid = new_job(srv)
    open_editor(page, srv, jid)
    page.get_by_role("button", name="Altyazı", exact=True).click()
    page.wait_for_selector(".cue")
    n = page.locator(".cue").count()
    assert n >= 3
    ta = page.locator(".cue-edit").first
    ta.fill("Altyazı düzenlendi şöyle")
    ta.press("Control+Enter")
    page.wait_for_function("document.querySelector('.cue-edit').value.includes('Altyazı düzenlendi')")
    saved(page)
    shot(page, "11-altyazi")
    tr = api(srv, "GET", f"/api/transcripts/{jid}")
    assert tr["segments"][0]["text"].startswith("Altyazı düzenlendi şöyle")
    page.get_by_role("button", name="Metin", exact=True).click()
    expect(page.locator(".seg").first).to_contain_text("Altyazı düzenlendi şöyle")


def test_edits_survive_immediate_reload(page, srv):
    jid = new_job(srv)
    open_editor(page, srv, jid)
    edit_first(page, "Yenilemeden önce yazılan metin")
    page.reload()  # otomatik kaydetme gecikmesi dolmadan
    page.wait_for_selector(".seg")
    expect(page.locator(".seg").first).to_contain_text("Yenilemeden önce yazılan metin")
    saved(page)
    assert api(srv, "GET", f"/api/transcripts/{jid}")["segments"][0]["text"] == "Yenilemeden önce yazılan metin"


def test_screens_in_dark_theme_and_narrow_editor(page, srv):
    jid = new_job(srv)
    page.goto(srv.url)
    page.get_by_role("button", name="Tema: Sistem").click()  # açık
    page.get_by_role("button", name="Tema: Açık").click()    # koyu
    assert page.locator("html").get_attribute("data-theme") == "dark"
    shot(page, "12-koyu-yukleme")
    page.goto(f"{srv.url}/#/library")
    page.wait_for_selector("table")
    shot(page, "13-koyu-kutuphane")
    page.goto(f"{srv.url}/#/settings")
    page.wait_for_selector(".card")
    page.set_viewport_size({"width": 1280, "height": 2200})
    shot(page, "14-koyu-ayarlar")
    page.set_viewport_size({"width": 1024, "height": 760})
    open_editor(page, srv, jid)
    page.locator(".seg").nth(1).locator(".seg-text").click()
    shot(page, "15-koyu-duzenleyici-1024")
    assert page.evaluate("document.documentElement.scrollWidth <= window.innerWidth + 1")
    page.get_by_role("button", name="Tema: Koyu").click()
    assert page.locator("html").get_attribute("data-theme") is None


def test_no_english_ui_strings_in_main_screens(page, srv):
    new_job(srv)
    banned = ["Upload", "Library", "Queue", "Settings", "Save", "Cancel", "Delete", "Search", "Loading"]
    for route in ("#/upload", "#/library", "#/queue", "#/settings"):
        page.goto(f"{srv.url}/{route}")
        page.wait_for_selector(".page")
        body = page.locator("main").inner_text()
        for word in banned:
            assert word not in body, f"{route} ekranında İngilizce metin: {word}"


def test_settings_save_and_token_masking(page, srv):
    page.goto(f"{srv.url}/#/settings")
    page.wait_for_selector(".card")
    page.locator("input[type=password]").fill("hf_abcdefghijklmnop1234")
    page.get_by_role("button", name="Ayarları kaydet").click()
    page.wait_for_selector(".card")  # sayfa yenilenir
    page.wait_for_function("document.body.innerText.includes('Kayıtlı belirteç')")
    body = page.locator("main").inner_text()
    assert "abcdefghijklmnop" not in body
    assert page.locator("input[type=password]").input_value() == ""
    api(srv, "PUT", "/api/settings", {"hf_token": ""})


@pytest.mark.skipif(ENGINE != "fake", reason="yavaş sahte motor gerekir")
def test_live_queue_progress_reorder_cancel_retry(page, tmp_path_factory):
    data = tmp_path_factory.mktemp("slow") / "data"
    data.mkdir()
    slow = Server(data, engine="fake", extra_env={"DESIFRE_FAKE_DELAY": "0.6"})
    slow.wait_ready()
    try:
        for name in ("birinci.wav", "ikinci.wav", "ucuncu.wav"):
            req = urllib.request.Request(f"{slow.url}/api/jobs?filename={name}&options={{}}", method="POST", data=SAMPLE.read_bytes())
            urllib.request.urlopen(req, timeout=30).read()
        page.goto(f"{slow.url}/#/queue")
        # çalışan işte gerçek ilerleme, aşama adı ve süre görünür
        expect(page.locator(".job-running progress")).to_be_visible(timeout=15000)
        expect(page.locator(".job-running .job-stage")).to_contain_text("Yazıya dökülüyor", timeout=15000)
        page.wait_for_function("document.querySelector('.job-running progress').value > 0")
        expect(page.locator(".job-running .job-times")).to_contain_text("Geçen süre")
        assert page.locator(".nav-link .badge").inner_text() in ("3", "2")
        shot(page, "16-kuyruk-calisiyor")
        # sıra değiştir: üçüncü işi bir yukarı taşı
        waiting = page.locator("section", has=page.get_by_role("heading", name="Bekleyenler")).locator("article")
        expect(waiting).to_have_count(2)
        assert "ikinci" in waiting.nth(0).inner_text()
        waiting.nth(1).get_by_role("button", name="Yukarı taşı").click()
        expect(waiting.nth(0)).to_contain_text("ucuncu")
        # bekleyeni iptal et, çalışanı iptal et
        waiting.nth(0).get_by_role("button", name="İptal et").click()
        page.locator(".job-running").get_by_role("button", name="İptal et").click()
        expect(page.locator(".chip-cancel")).to_have_count(2, timeout=20000)
        # iptal edilen yeniden denenir ve tamamlanır
        page.locator("article", has_text="birinci").get_by_role("button", name="Yeniden dene").click()
        expect(page.locator("article", has_text="birinci").locator(".chip-done")).to_be_visible(timeout=60000)
        shot(page, "17-kuyruk-tamam")
    finally:
        slow.stop()
