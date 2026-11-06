"""One-minute check that your key, Prisma and Timbre work the way this app expects.

    cd backend && python -m tools.check_gnani

What it does (about 10 short API calls; measure your credit balance on the dashboard before and after):
  1. Timbre speaks a Hindi phone number and a Hinglish sentence -> saved as .wav files in tools/out/
  2. Prisma listens to those files back, once per output format (verbatim / transcribe / codemix / transliterate)
  3. Prints what came back, so you can see how numbers and names arrive

Listen to the .wav files yourself too: that is the real test of whether Timbre reads digits clearly.
"""
import sys
import time
from pathlib import Path

from app import speak
from app.config import settings
from app.gnani import GnaniClient, GnaniError

OUT = Path(__file__).parent / "out"

PHONE = "9876543210"
CASES = [
    ("phone_hi", "hi-IN", "आपका मोबाइल नंबर " + speak.speak_digits(PHONE, "hi", [5, 5]) + " है।", PHONE),
    ("hinglish", "hi-en", "मेरा नाम Krishna Kumar है और मैं Lucknow से हूँ।", "Krishna Kumar"),
    ("income_hi", "hi-IN", "सालाना आमदनी " + speak.speak_amount(250000, "hi"), "250000"),
]
FORMATS = ["verbatim", "transcribe", "codemix", "transliterate"]


def main() -> int:
    g = GnaniClient()
    if not g.configured:
        print("GNANI_API_KEY is not set. Copy .env.example to .env and paste your key from app.gnani.ai.")
        return 2
    OUT.mkdir(exist_ok=True)
    print(f"TTS model={settings.tts_model} voice={settings.tts_voice} | STT model={settings.stt_model}\n")
    failures = 0
    for name, lang, text, expect in CASES:
        print(f"=== {name}: Timbre says  {text!r}")
        try:
            wav = g.synthesize(text, lang)
        except GnaniError as e:
            print(f"  TTS FAILED [{e.code}] {e.message}\n")
            failures += 1
            continue
        path = OUT / f"{name}.wav"
        path.write_bytes(wav)
        print(f"  saved {path} ({len(wav) // 1024} KB) - play it and check the digits sound clear")
        for fmt in FORMATS:
            try:
                res = g.transcribe(wav, "hi-IN,en-IN", fmt)
                print(f"  Prisma[{fmt:13}] -> {res.get('transcript')!r}   (expecting something like {expect!r})")
            except GnaniError as e:
                print(f"  Prisma[{fmt:13}] FAILED [{e.code}] {e.message}")
                failures += 1
            time.sleep(0.3)
        print()
    print("Done. Failures:", failures)
    print("Check your credit balance on the dashboard now; (balance before - after) / number of calls = cost per call.")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
