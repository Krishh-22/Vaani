"""Thin client for Gnani's Prisma (speech-to-text) and Timbre (text-to-speech) REST APIs.

Docs: https://docs.gnani.ai/api/STT/speech-to-text  and  https://docs.gnani.ai/api/TTS/tts-inference
The API key lives only here, on the server. It is never sent to the browser.
"""
import json
import logging
import time
from typing import List, Optional

import requests

from .config import settings

log = logging.getLogger("vaani.gnani")


class GnaniError(Exception):
    """code: not_configured | auth | credits | rate | timeout | upstream | bad_request | empty"""

    def __init__(self, code: str, message: str, status: Optional[int] = None):
        super().__init__(message)
        self.code, self.message, self.status = code, message, status


def _error_from_response(r: requests.Response) -> GnaniError:
    try:
        body = r.json()
    except ValueError:
        body = {}
    detail = ""
    if isinstance(body, dict):
        err = body.get("error") or body.get("detail") or {}
        detail = err.get("message", "") if isinstance(err, dict) else str(err)
    code = {401: "auth", 403: "auth", 402: "credits", 429: "rate"}.get(r.status_code)
    if code is None:
        code = "bad_request" if r.status_code in (400, 413, 415, 422) else "upstream"
    return GnaniError(code, detail or f"Gnani API returned HTTP {r.status_code}", r.status_code)


class GnaniClient:
    def __init__(self):
        self.s = settings
        self.http = requests.Session()

    @property
    def configured(self) -> bool:
        return self.s.configured

    def _headers(self) -> dict:
        if not self.s.configured:
            raise GnaniError("not_configured", "GNANI_API_KEY is not set")
        return {"X-API-Key-ID": self.s.api_key}

    # ------------------------------------------------------------------ STT
    def transcribe(self, audio: bytes, language_code: str, fmt: Optional[str] = None,
                   keyterms: Optional[List[str]] = None, topic: Optional[str] = None,
                   filename: str = "audio.wav", mime: str = "audio/wav") -> dict:
        """Returns the Prisma JSON ({'transcript': ..., 'detected_language_code': ...}).

        First try with the optional accuracy hints (format, keyterms, topic). If the API
        rejects them (400/422) we retry once with the bare minimum, so a hint can never
        break the app.
        """
        fmt = self.s.stt_format_override or fmt
        base = {"language_code": language_code, "model": self.s.stt_model}
        rich = dict(base)
        if fmt:
            rich["format"] = fmt
        if keyterms and self.s.stt_use_keyterms:
            rich["keyterms"] = json.dumps(keyterms)
        if topic and self.s.stt_use_keyterms:
            rich["topic"] = topic
        try:
            return self._stt_call(audio, rich, filename, mime)
        except GnaniError as e:
            if e.code == "bad_request" and rich != base:
                log.warning("STT rejected optional params (%s); retrying with the minimum", e.message)
                return self._stt_call(audio, base, filename, mime)
            raise

    def _stt_call(self, audio: bytes, data: dict, filename: str, mime: str) -> dict:
        url = f"{self.s.base_url}/stt/v3"
        last: Optional[GnaniError] = None
        for attempt in range(2):
            try:
                r = self.http.post(url, headers=self._headers(), data=data,
                                   files={"audio_file": (filename, audio, mime)}, timeout=self.s.http_timeout)
            except requests.Timeout:
                last = GnaniError("timeout", "Speech recognition timed out")
            except requests.RequestException as e:
                last = GnaniError("upstream", f"Could not reach Gnani: {e.__class__.__name__}")
            else:
                if r.status_code == 200:
                    body = r.json()
                    if body.get("success") is False:
                        raise GnaniError("upstream", str(body.get("error")))
                    return body
                last = _error_from_response(r)
                if last.code not in ("rate", "upstream"):
                    raise last
            time.sleep(1.2)             # one polite retry for 429 / 5xx / timeouts
        raise last

    # ------------------------------------------------------------------ TTS
    def synthesize(self, text: str, language: str, speed: Optional[float] = None) -> bytes:
        """Returns WAV bytes."""
        payload = {
            "text": text,
            "model": self.s.tts_model,
            "voice": self.s.tts_voice,
            "language": language,
            "speed": speed or self.s.tts_speed,
            "audio_config": {
                "sample_rate": self.s.tts_sample_rate, "num_channels": 1, "sample_width": 2,
                "encoding": "linear_pcm", "container": "wav",
            },
        }
        last: Optional[GnaniError] = None
        for attempt in range(2):
            try:
                r = self.http.post(f"{self.s.base_url}/api/v1/tts/inference",
                                   headers={**self._headers(), "Content-Type": "application/json"},
                                   json=payload, timeout=self.s.http_timeout)
            except requests.Timeout:
                last = GnaniError("timeout", "Speech synthesis timed out")
            except requests.RequestException as e:
                last = GnaniError("upstream", f"Could not reach Gnani: {e.__class__.__name__}")
            else:
                ctype = r.headers.get("content-type", "")
                if r.status_code == 200 and not ctype.startswith("application/json") and r.content:
                    return r.content
                last = _error_from_response(r) if r.status_code != 200 else GnaniError("empty", "Empty audio from TTS")
                if last.code not in ("rate", "upstream"):
                    raise last
            time.sleep(1.2)
        raise last
