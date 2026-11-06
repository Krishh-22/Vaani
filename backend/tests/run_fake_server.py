"""Run the whole app with a FAKE Gnani: no API key, no credits.

    cd backend && python -m tests.run_fake_server            # http://127.0.0.1:8010

Every time you speak, the fake "recogniser" ignores your audio and returns the next line of a
scripted scholarship application. Good for checking the UI, hands-free flow, and your demo timing.
It proves nothing about real speech recognition - for that, use the real server with your key.
"""
import os
import sys
import tempfile
from pathlib import Path

import uvicorn

from app import main
from app.config import settings
from app import verhoeff
from tests.fake_gnani import FakeGnani

AADHAAR = verhoeff.make_valid_aadhaar("23456789012")
SCRIPT = [
    "mera naam Krishna Kumar hai", "haan",
    "pandrah august do hazaar paanch", "haan",
    "nau aath saat chhah paanch char teen do ek shunya", "5 nahi 6", "haan",
    " ".join(AADHAAR[i:i + 4] for i in (0, 4, 8)), "haan",
    "do do chhah shunya ek shunya", "haan",
    "obc", "haan",
    "do lakh pachas hazaar", "haan",
    "b tech", "haan",
    "sab sahi hai",
]


class Looping(FakeGnani):
    def transcribe(self, *a, **k):
        if not self.queue:
            self.say(*SCRIPT)
        return super().transcribe(*a, **k)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", sys.argv[1] if len(sys.argv) > 1 else 8010))
    # The fake voice is a beep. Keep it OUT of the real TTS cache, or the real server would replay beeps.
    settings.tts_cache_dir = Path(tempfile.mkdtemp(prefix="vaani-fake-tts-"))
    main.service.gnani = Looping()
    print(f"Fake-Gnani demo on http://127.0.0.1:{port}  (scripted answers, no credits used)")
    uvicorn.run(main.app, host="127.0.0.1", port=port, log_level="warning")
