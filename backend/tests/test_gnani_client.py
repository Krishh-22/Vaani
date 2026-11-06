"""The real GnaniClient talking to a local mock that follows Gnani's documented API
(https://docs.gnani.ai/api/STT/speech-to-text and /api/TTS/tts-inference).

This proves our request shape and error handling. It cannot prove Gnani's live behaviour:
for that, run `python -m tools.check_gnani` with your key.
"""
import json
import socket
import threading
import time

import pytest
import uvicorn
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route

from app.config import settings
from app.gnani import GnaniClient, GnaniError
from tests.fake_gnani import tone_wav

seen = []          # every request the mock received
plan = {}          # per-test behaviour: {"stt": [status, ...], "tts": [status, ...]}


def _next(kind):
    q = plan.get(kind, [])
    return q.pop(0) if q else 200


async def stt(request):
    form = await request.form()
    seen.append({"path": "stt", "key": request.headers.get("x-api-key-id"),
                 "fields": {k: v for k, v in form.items() if k != "audio_file"},
                 "has_audio": hasattr(form.get("audio_file"), "read")})
    status = _next("stt")
    if status == 200:
        return JSONResponse({"success": True, "request_id": "r1", "transcript": "नौ आठ सात", "model": "prisma-v3.0"})
    if status == "reject_hints":
        if "keyterms" in form or "topic" in form or "format" in form:
            return JSONResponse({"success": False, "error": {"type": "invalid_request", "message": "bad param"}}, status_code=422)
        return JSONResponse({"success": True, "transcript": "ok minimal", "model": "prisma-v3.0"})
    return JSONResponse({"success": False, "error": {"type": "x", "message": f"status {status}"}}, status_code=status)


async def tts(request):
    body = await request.json()
    seen.append({"path": "tts", "key": request.headers.get("x-api-key-id"), "body": body})
    status = _next("tts")
    if status == 200:
        return Response(tone_wav(), media_type="audio/wav")
    return JSONResponse({"success": False, "error": {"type": "x", "message": f"status {status}"}}, status_code=status)


@pytest.fixture()
def client(monkeypatch):
    seen.clear()
    plan.clear()
    app = Starlette(routes=[Route("/stt/v3", stt, methods=["POST"]), Route("/api/v1/tts/inference", tts, methods=["POST"])])
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    srv = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error"))
    th = threading.Thread(target=srv.run, daemon=True)
    th.start()
    while not srv.started:
        time.sleep(0.05)
    monkeypatch.setattr(settings, "base_url", f"http://127.0.0.1:{port}")
    monkeypatch.setattr(settings, "api_key", "test-key-123")
    monkeypatch.setattr(settings, "stt_format_override", "")
    monkeypatch.setattr("app.gnani.time.sleep", lambda s: None)       # don't wait between retries
    yield GnaniClient()
    srv.should_exit = True
    th.join(timeout=5)


def test_stt_request_matches_the_docs(client):
    res = client.transcribe(tone_wav(), "hi-IN,en-IN", "transcribe", ["OBC", "SC"], "scholarship form")
    assert res["transcript"] == "नौ आठ सात"
    r = seen[0]
    assert r["key"] == "test-key-123" and r["has_audio"]
    assert r["fields"]["model"] == "prisma-v3.0"
    assert r["fields"]["language_code"] == "hi-IN,en-IN"
    assert r["fields"]["format"] == "transcribe"
    assert json.loads(r["fields"]["keyterms"]) == ["OBC", "SC"]
    assert r["fields"]["topic"] == "scholarship form"


def test_stt_retries_without_hints_when_they_are_rejected(client):
    plan["stt"] = ["reject_hints", "reject_hints"]       # first call (with hints) rejected, second (minimal) accepted
    res = client.transcribe(tone_wav(), "hi-IN", "codemix", ["x"], "topic")
    assert res["transcript"] == "ok minimal"
    assert len(seen) == 2
    assert set(seen[1]["fields"]) == {"language_code", "model"}


def test_stt_retries_once_on_429_then_succeeds(client):
    plan["stt"] = [429, 200]
    assert client.transcribe(tone_wav(), "hi-IN")["transcript"]
    assert len(seen) == 2


def test_stt_gives_up_after_one_retry(client):
    plan["stt"] = [503, 503, 503]
    with pytest.raises(GnaniError) as e:
        client.transcribe(tone_wav(), "hi-IN")
    assert e.value.code == "upstream" and len(seen) == 2


@pytest.mark.parametrize("status,code", [(401, "auth"), (403, "auth"), (402, "credits")])
def test_stt_auth_and_credit_errors_are_not_retried(client, status, code):
    plan["stt"] = [status, status]
    with pytest.raises(GnaniError) as e:
        client.transcribe(tone_wav(), "hi-IN")
    assert e.value.code == code and len(seen) == 1


def test_format_override_wins(client, monkeypatch):
    monkeypatch.setattr(settings, "stt_format_override", "codemix")
    client.transcribe(tone_wav(), "hi-IN", "transcribe")
    assert seen[0]["fields"]["format"] == "codemix"


def test_tts_request_matches_the_docs(client):
    wav = client.synthesize("नमस्ते", "hi-IN", 0.9)
    assert wav[:4] == b"RIFF"
    b = seen[0]["body"]
    assert seen[0]["key"] == "test-key-123"
    assert (b["text"], b["model"], b["voice"], b["language"], b["speed"]) == ("नमस्ते", "timbre-v2.5", "Nalini", "hi-IN", 0.9)
    assert b["audio_config"] == {"sample_rate": 24000, "num_channels": 1, "sample_width": 2,
                                 "encoding": "linear_pcm", "container": "wav"}


def test_tts_errors(client):
    plan["tts"] = [403]
    with pytest.raises(GnaniError) as e:
        client.synthesize("x", "hi-IN")
    assert e.value.code == "auth"
    plan["tts"] = [500, 200]
    assert client.synthesize("x", "hi-IN")[:4] == b"RIFF"       # one retry on 5xx


def test_no_key_never_calls_out(client, monkeypatch):
    monkeypatch.setattr(settings, "api_key", "")
    seen.clear()
    with pytest.raises(GnaniError) as e:
        client.transcribe(tone_wav(), "hi-IN")
    assert e.value.code == "not_configured" and not seen
