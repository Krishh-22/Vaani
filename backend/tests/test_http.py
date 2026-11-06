"""End-to-end over real HTTP: the actual Starlette app on a local port, with FakeGnani instead of Gnani."""
import io
import socket
import threading
import time

import pytest
import requests
import uvicorn

from app import main, verhoeff
from app.config import settings
from app.gnani import GnaniError
from tests.fake_gnani import FakeGnani, tone_wav

GOOD_AADHAAR = verhoeff.make_valid_aadhaar("23456789012")


@pytest.fixture()
def server(tmp_path, monkeypatch):
    fake = FakeGnani()
    monkeypatch.setattr(main.service, "gnani", fake)
    monkeypatch.setattr(main.service, "sessions", {})
    monkeypatch.setattr(main.service, "stt_total", 0)
    monkeypatch.setattr(main.service, "tts_total", 0)
    monkeypatch.setattr(settings, "tts_cache_dir", tmp_path)
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, log_level="error"))
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    for _ in range(100):
        if srv.started:
            break
        time.sleep(0.05)
    base = f"http://127.0.0.1:{port}"
    yield base, fake
    srv.should_exit = True
    th.join(timeout=5)


def new_session(base, lang="hi"):
    r = requests.post(f"{base}/api/sessions", json={"lang": lang})
    assert r.status_code == 200, r.text
    return r.json()


def text(base, sid, t):
    r = requests.post(f"{base}/api/sessions/{sid}/text", json={"text": t})
    assert r.status_code == 200, r.text
    return r.json()


def audio(base, sid, data=None):
    return requests.post(f"{base}/api/sessions/{sid}/audio", files={"audio": ("a.wav", tone_wav() if data is None else data, "audio/wav")})


def test_frontend_and_health(server):
    base, _ = server
    assert requests.get(base + "/").status_code == 200
    assert "BoloBharo" in requests.get(base + "/").text
    assert requests.get(base + "/app.js").status_code == 200
    assert requests.get(base + "/style.css").status_code == 200
    h = requests.get(base + "/api/health").json()
    assert h["ok"] is True and h["stt_model"] and h["tts_model"]


def test_health_never_leaks_the_key(server, monkeypatch):
    base, _ = server
    monkeypatch.setattr(settings, "api_key", "SECRET-KEY-123")
    assert "SECRET-KEY-123" not in requests.get(base + "/api/health").text
    assert "SECRET-KEY-123" not in requests.get(base + "/app.js").text


def test_session_start(server):
    base, _ = server
    d = new_session(base)
    assert d["state"] == "ask" and not d["done"]
    assert d["messages"][0]["text"] and d["messages"][0]["tts_lang"] in ("hi-IN", "hi-en")
    assert d["form"]["total"] == 8 and d["form"]["fields"][0]["status"] == "active"


def test_full_form_by_audio_and_pdf(server):
    base, fake = server
    sid = new_session(base)["session_id"]
    fake.say(
        "mera naam Krishna Kumar hai", "haan",
        "15 August 2005", "haan",
        "nau aath saat chhah paanch char teen do ek shunya", "5 nahi 6", "haan",
        GOOD_AADHAAR, "haan",
        "do do chhah shunya ek shunya", "haan",
        "obc", "haan",
        "do lakh pachas hazaar", "haan",
        "b tech", "haan",
        "sab sahi hai",
    )
    last = None
    for _ in range(18):
        r = audio(base, sid)
        assert r.status_code == 200, r.text
        last = r.json()
    assert last["done"] and last["form"]["complete"] and last["form"]["done"] == 8
    assert GOOD_AADHAAR not in str(last["form"])         # the browser only ever sees a masked Aadhaar

    # Prisma got the right hints for the phone field
    phone_call = fake.stt_calls[4]
    assert phone_call["lang"] == settings.stt_langs_hi and phone_call["format"] == "transcribe"
    # the name field asks for Roman letters, the category field for code-mixed output
    assert fake.stt_calls[0]["format"] == "transliterate"

    pdf = requests.get(f"{base}/api/sessions/{sid}/pdf")
    assert pdf.status_code == 200 and pdf.headers["content-type"] == "application/pdf"
    from pypdf import PdfReader
    body = "\n".join(p.extract_text() for p in PdfReader(io.BytesIO(pdf.content)).pages)
    assert "Krishna Kumar" in body and "98766 43210" in body and "2,50,000" in body
    assert GOOD_AADHAAR[:4] + " " + GOOD_AADHAAR[4:8] + " " + GOOD_AADHAAR[8:] in body
    assert "OBC" in body and "B.Tech" in body


def test_pdf_refused_until_form_done(server):
    base, _ = server
    sid = new_session(base)["session_id"]
    r = requests.get(f"{base}/api/sessions/{sid}/pdf")
    assert r.status_code == 409 and r.json()["error"] == "not_done"


def test_text_fallback(server):
    base, _ = server
    sid = new_session(base)["session_id"]
    d = text(base, sid, "Krishna Kumar")
    assert d["state"] == "confirm" and d["heard"] == "Krishna Kumar"


def test_tts_is_cached_for_static_prompts_but_not_for_readbacks(server):
    base, fake = server
    d = new_session(base)
    mid = d["messages"][0]["id"]
    a = requests.get(f"{base}/api/sessions/{d['session_id']}/messages/{mid}/audio")
    b = requests.get(f"{base}/api/sessions/{d['session_id']}/messages/{mid}/audio")
    assert a.status_code == 200 and a.headers["content-type"] == "audio/wav" and a.content[:4] == b"RIFF"
    assert b.content == a.content and len(fake.tts_calls) == 1          # second request came from disk

    conf = text(base, d["session_id"], "Krishna Kumar")["messages"][0]
    for _ in range(2):
        assert requests.get(f"{base}/api/sessions/{d['session_id']}/messages/{conf['id']}/audio").status_code == 200
    assert len(fake.tts_calls) == 3                                      # read-back synthesised each time


def test_stt_failure_is_reported_and_session_survives(server):
    base, fake = server
    sid = new_session(base)["session_id"]
    fake.fail_stt = GnaniError("credits", "out of credits", 402)
    r = audio(base, sid)
    assert r.status_code == 502 and r.json()["error"] == "stt_credits"
    assert "type" in r.json()["message"].lower()
    fake.fail_stt = None
    assert text(base, sid, "Krishna Kumar")["state"] == "confirm"


def test_tts_failure_returns_503(server):
    base, fake = server
    d = new_session(base)
    fake.fail_tts = GnaniError("upstream", "boom")
    r = requests.get(f"{base}/api/sessions/{d['session_id']}/messages/{d['messages'][0]['id']}/audio")
    assert r.status_code == 503


def test_silence_does_not_advance(server):
    base, fake = server
    sid = new_session(base)["session_id"]
    fake.say("")
    d = audio(base, sid).json()
    assert d["state"] == "ask" and d["messages"][0]["kind"] == "error"


def test_bad_inputs(server):
    base, _ = server
    sid = new_session(base)["session_id"]
    assert requests.post(f"{base}/api/sessions/{sid}/audio", data=b"x").status_code == 400
    assert audio(base, sid, b"").status_code == 400
    assert audio(base, sid, b"0" * (3 * 1024 * 1024 + 1)).status_code == 400
    assert requests.post(f"{base}/api/sessions/{sid}/text", data="not json").status_code == 400
    assert requests.post(f"{base}/api/sessions/nope/text", json={"text": "hi"}).status_code == 404


def test_voice_quota_per_session(server, monkeypatch):
    base, fake = server
    monkeypatch.setattr(settings, "max_stt_per_session", 2)
    sid = new_session(base)["session_id"]
    fake.say("Krishna", "haan", "x")
    assert audio(base, sid).status_code == 200
    assert audio(base, sid).status_code == 200
    r = audio(base, sid)
    assert r.status_code == 429 and r.json()["error"] == "quota"
    assert text(base, sid, "15 August 2005")["state"] == "confirm"        # typing still works


def test_global_voice_quota(server, monkeypatch):
    base, fake = server
    monkeypatch.setattr(settings, "max_stt_calls", 1)
    a, b = new_session(base)["session_id"], new_session(base)["session_id"]
    fake.say("Krishna", "Priya")
    assert audio(base, a).status_code == 200
    assert audio(base, b).status_code == 429


def test_delete_session_and_beacon_alias(server):
    base, _ = server
    sid = new_session(base)["session_id"]
    assert requests.delete(f"{base}/api/sessions/{sid}").status_code == 204
    assert requests.post(f"{base}/api/sessions/{sid}/text", json={"text": "x"}).status_code == 404
    sid2 = new_session(base)["session_id"]
    assert requests.post(f"{base}/api/sessions/{sid2}").status_code == 204       # sendBeacon is always POST
    assert requests.post(f"{base}/api/sessions/{sid2}/text", json={"text": "x"}).status_code == 404


def test_session_cap(server, monkeypatch):
    base, _ = server
    monkeypatch.setattr(settings, "max_sessions", 2)
    new_session(base), new_session(base)
    r = requests.post(f"{base}/api/sessions", json={"lang": "hi"})
    assert r.status_code == 503 and r.json()["error"] == "busy"


def test_expired_sessions_are_purged(server, monkeypatch):
    base, _ = server
    sid = new_session(base)["session_id"]
    main.service.sessions[sid].last_active -= settings.session_ttl_seconds + 5
    assert requests.post(f"{base}/api/sessions/{sid}/text", json={"text": "x"}).status_code == 404


def test_unconfigured_key_message(server, monkeypatch):
    """With the real client and no key, a voice turn explains itself instead of crashing."""
    base, _ = server
    from app.gnani import GnaniClient
    monkeypatch.setattr(settings, "api_key", "")
    monkeypatch.setattr(main.service, "gnani", GnaniClient())
    sid = new_session(base)["session_id"]
    r = audio(base, sid)
    assert r.status_code == 503 and r.json()["error"] == "stt_not_configured"
