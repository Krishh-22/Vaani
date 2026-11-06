"""A stand-in for GnaniClient so the app can be tested without an API key or credits.

transcribe() returns whatever you queue with say(); synthesize() returns a short valid WAV tone.
"""
import io
import math
import struct
import wave
from typing import List, Optional

from app.gnani import GnaniError


def tone_wav(seconds: float = 0.25, freq: int = 440, rate: int = 16000) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        n = int(seconds * rate)
        w.writeframes(b"".join(struct.pack("<h", int(9000 * math.sin(2 * math.pi * freq * i / rate))) for i in range(n)))
    return buf.getvalue()


class FakeGnani:
    configured = True

    def __init__(self):
        self.queue: List[str] = []
        self.stt_calls: List[dict] = []
        self.tts_calls: List[dict] = []
        self.fail_stt: Optional[GnaniError] = None
        self.fail_tts: Optional[GnaniError] = None

    def say(self, *transcripts: str) -> "FakeGnani":
        self.queue.extend(transcripts)
        return self

    def transcribe(self, audio, language_code, fmt=None, keyterms=None, topic=None, filename="a.wav", mime="audio/wav"):
        self.stt_calls.append({"bytes": len(audio), "lang": language_code, "format": fmt, "keyterms": keyterms})
        if self.fail_stt:
            raise self.fail_stt
        text = self.queue.pop(0) if self.queue else ""
        return {"success": True, "transcript": text, "model": "prisma-v3.0", "detected_language_code": "hi-IN"}

    def synthesize(self, text, language, speed=None):
        self.tts_calls.append({"text": text, "lang": language, "speed": speed})
        if self.fail_tts:
            raise self.fail_tts
        return tone_wav()
