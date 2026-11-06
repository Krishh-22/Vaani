"""HTTP API + static frontend (Starlette; FastAPI is built on top of this).

Run:  uvicorn app.main:app --reload --port 8000     (from the backend/ folder)
"""
import logging
from pathlib import Path

from starlette.applications import Starlette
from starlette.concurrency import run_in_threadpool
from starlette.middleware import Middleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from .config import PROJECT, settings
from .service import Service, ServiceError

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
service = Service()

FRONTEND = PROJECT / "frontend"


def _err(e: ServiceError) -> JSONResponse:
    return JSONResponse({"error": e.code, "message": e.message}, status_code=e.status)


async def health(request: Request):
    return JSONResponse({
        "ok": True, "gnani_configured": bool(service.gnani.configured),
        "tts_model": settings.tts_model, "tts_voice": settings.tts_voice, "stt_model": settings.stt_model,
    })


async def create_session(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    lang = body.get("lang", "hi") if isinstance(body, dict) else "hi"
    try:
        return JSONResponse(await run_in_threadpool(service.create_session, lang))
    except ServiceError as e:
        return _err(e)


async def post_text(request: Request):
    sid = request.path_params["sid"]
    try:
        body = await request.json()
        text = str(body.get("text", ""))
        return JSONResponse(await run_in_threadpool(service.turn_text, sid, text))
    except ServiceError as e:
        return _err(e)
    except (ValueError, AttributeError):
        return JSONResponse({"error": "bad_request", "message": "Send JSON like {\"text\": \"...\"}"}, status_code=400)


async def post_audio(request: Request):
    sid = request.path_params["sid"]
    try:
        form = await request.form()
        up = form.get("audio")
        if up is None or not hasattr(up, "read"):
            raise ServiceError("bad_audio", "Send the recording in a form field named 'audio'.", 400)
        data = await up.read()
        return JSONResponse(await run_in_threadpool(
            service.turn_audio, sid, data, up.filename or "audio.wav", up.content_type or "audio/wav"))
    except ServiceError as e:
        return _err(e)


async def message_audio(request: Request):
    p = request.path_params
    try:
        audio = await run_in_threadpool(service.message_audio, p["sid"], p["mid"])
        return Response(audio, media_type="audio/wav", headers={"Cache-Control": "no-store"})
    except ServiceError as e:
        return _err(e)


async def get_pdf(request: Request):
    try:
        data = await run_in_threadpool(service.pdf, request.path_params["sid"])
        return Response(data, media_type="application/pdf", headers={
            "Content-Disposition": 'attachment; filename="scholarship-application.pdf"', "Cache-Control": "no-store"})
    except ServiceError as e:
        return _err(e)


async def delete_session(request: Request):
    service.delete(request.path_params["sid"])
    return Response(status_code=204)


routes = [
    Route("/api/health", health),
    Route("/api/sessions", create_session, methods=["POST"]),
    Route("/api/sessions/{sid}/text", post_text, methods=["POST"]),
    Route("/api/sessions/{sid}/audio", post_audio, methods=["POST"]),
    Route("/api/sessions/{sid}/messages/{mid}/audio", message_audio, methods=["GET"]),
    Route("/api/sessions/{sid}/pdf", get_pdf, methods=["GET"]),
    # POST alias so the browser can use navigator.sendBeacon when the tab closes
    Route("/api/sessions/{sid}", delete_session, methods=["DELETE", "POST"]),
    Mount("/", StaticFiles(directory=str(FRONTEND), html=True), name="frontend"),
]

app = Starlette(routes=routes)
