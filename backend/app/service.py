"""Glue between the HTTP layer, the dialogue manager and Gnani. No web-framework code in here."""
import hashlib
import logging
import threading
import time
from typing import Dict, Optional

from . import fields as F
from .config import settings
from .dialogue import Session, DONE
from .gnani import GnaniClient, GnaniError
from .pdf import build_pdf

log = logging.getLogger("vaani")

MAX_AUDIO_BYTES = 3 * 1024 * 1024


class ServiceError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


class Service:
    def __init__(self, gnani: Optional[GnaniClient] = None):
        self.gnani = gnani or GnaniClient()
        self.sessions: Dict[str, Session] = {}
        self.lock = threading.Lock()
        self.stt_total = 0
        self.tts_total = 0
        settings.tts_cache_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ sessions
    def _purge(self) -> None:
        cutoff = time.time() - settings.session_ttl_seconds
        for sid in [k for k, s in self.sessions.items() if s.last_active < cutoff]:
            del self.sessions[sid]

    def _get(self, sid: str) -> Session:
        with self.lock:
            self._purge()
            s = self.sessions.get(sid)
        if not s:
            raise ServiceError("no_session", "Session expired. Please start again.", 404)
        return s

    def create_session(self, lang: str) -> dict:
        with self.lock:
            self._purge()
            if len(self.sessions) >= settings.max_sessions:
                raise ServiceError("busy", "The demo is busy right now. Please try again in a few minutes.", 503)
            s = Session(F.load_form("scholarship"), lang)
            self.sessions[s.id] = s
        return self._payload(s, s.start())

    def delete(self, sid: str) -> None:
        with self.lock:
            self.sessions.pop(sid, None)

    def _payload(self, s: Session, msgs, heard: Optional[str] = None) -> dict:
        return {
            "session_id": s.id,
            "lang": s.lang,
            "state": s.state,
            "done": s.state == DONE,
            "heard": heard,
            "messages": [{"id": m.id, "text": m.text, "kind": m.kind, "tts_lang": m.tts_lang} for m in msgs],
            "form": s.snapshot(),
        }

    # ------------------------------------------------------------------ turns
    def turn_text(self, sid: str, text: str) -> dict:
        s = self._get(sid)
        text = (text or "").strip()[:500]
        return self._payload(s, s.handle(text), heard=text)

    def turn_audio(self, sid: str, audio: bytes, filename: str = "audio.wav", mime: str = "audio/wav") -> dict:
        s = self._get(sid)
        if not audio or len(audio) > MAX_AUDIO_BYTES:
            raise ServiceError("bad_audio", "Audio missing or too long (max 30 seconds).", 400)
        with self.lock:
            if self.stt_total >= settings.max_stt_calls or s.stt_calls >= settings.max_stt_per_session:
                raise ServiceError("quota", "Voice limit reached for this demo. You can still type your answers.", 429)
            self.stt_total += 1
            s.stt_calls += 1
        hint = s.stt_hint()
        langs = settings.stt_langs_hi if s.lang == "hi" else settings.stt_langs_en
        try:
            res = self.gnani.transcribe(audio, langs, hint["format"], hint["keyterms"],
                                        s.form.get("stt_topic"), filename, mime)
        except GnaniError as e:
            raise ServiceError("stt_" + e.code, self._friendly(e), 502 if e.code != "not_configured" else 503)
        transcript = (res.get("transcript") or "").strip()
        if settings.log_transcripts:
            log.info("STT field=%s fmt=%s heard=%r", s.field["id"], hint["format"], transcript)
        return self._payload(s, s.handle(transcript), heard=transcript)

    @staticmethod
    def _friendly(e: GnaniError) -> str:
        return {
            "not_configured": "The server has no Gnani API key yet. You can type your answers instead.",
            "auth": "The Gnani API key was rejected. Please check GNANI_API_KEY.",
            "credits": "The Gnani credits are used up. You can still type your answers.",
            "rate": "Too many requests right now. Please try again in a moment.",
            "timeout": "Speech recognition took too long. Please try again.",
        }.get(e.code, "Speech recognition is unavailable right now. You can type your answer.")

    # ------------------------------------------------------------------ audio for a bot message
    def message_audio(self, sid: str, mid: str) -> bytes:
        s = self._get(sid)
        m = s.messages.get(mid)
        if not m:
            raise ServiceError("no_message", "Unknown message.", 404)
        key = hashlib.sha1("|".join([settings.tts_model, settings.tts_voice, m.tts_lang, str(m.speed), m.speech]).encode()).hexdigest()
        path = settings.tts_cache_dir / f"{key}.wav"
        if m.cacheable and path.exists():
            return path.read_bytes()
        with self.lock:
            if self.tts_total >= settings.max_tts_calls:
                raise ServiceError("quota", "Voice output limit reached for this demo.", 429)
            self.tts_total += 1
        try:
            audio = self.gnani.synthesize(m.speech, m.tts_lang, m.speed)
        except GnaniError as e:
            raise ServiceError("tts_" + e.code, e.message, 503)
        if m.cacheable:                     # only static prompts, never read-backs of personal data
            path.write_bytes(audio)
        return audio

    # ------------------------------------------------------------------ pdf
    def pdf(self, sid: str) -> bytes:
        s = self._get(sid)
        if s.state != DONE:
            raise ServiceError("not_done", "Finish the form first.", 409)
        return build_pdf(s.form, s.values)
