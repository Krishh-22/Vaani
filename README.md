# BoloBharo (बोलो भरो) — fill a form by talking

A voice-first scholarship application for people who find reading and typing hard. The app asks one
question at a time in Hindi, English or Hinglish, **reads every answer back**, and waits for a yes or no.
Built for the Great Indian AI Internship Challenge on Gnani's **Prisma** (speech to text) and **Timbre** (text to speech).

## Run it (5 minutes)

```bash
cd bolobharo
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                     # then paste your key into GNANI_API_KEY
cd backend
python -m tools.check_gnani                              # 1-minute check of your key, Prisma and Timbre
uvicorn app.main:app --port 8000                         # open http://127.0.0.1:8000 in Chrome
```

Use headphones when you test, or the microphone will hear the app's own voice.
Everything is served by one process: the API and the web page.

### No key or no credits yet?
```bash
cd backend && python -m tests.run_fake_server            # http://127.0.0.1:8010
```
This runs the full app with a **fake** recogniser that ignores your voice and replays a scripted application.
It is for checking the interface, not the speech recognition.

### Tests
```bash
cd backend && python -m pytest -q                        # 98 tests, about 6 seconds, no network or key needed
```

## What happens in one turn

```
 mic ──▶ browser records 16 kHz WAV ──▶ POST /audio ──▶ Prisma (STT) ──▶ dialogue manager ──▶ JSON
                                                                                                │
 speaker ◀── browser plays WAV ◀── GET /messages/{id}/audio ◀── Timbre (TTS) ◀── text to say ◀──┘
```

The dialogue manager (`backend/app/dialogue.py`) is a small state machine with no network code, so it is fully unit tested:

```
ASK ──(understood + valid)──▶ CONFIRM ──(yes)──▶ next field
 ▲                               │
 └──────(no / invalid)───────────┘          after the last field: REVIEW ──("all correct")──▶ DONE
                                            REVIEW: say a field name ("change my phone number") to redo just that one
```

### The hard parts it solves
| Problem | How |
|---|---|
| Digits said many ways: "nau aath saat…", "९८७…", "ninety eight seventy six", "double nine" | `numbers.py`: tokenizer + Hindi/English number lexicon with spelling normalisation |
| Indian amounts: "do lakh pachas hazaar", "dhai lakh", "saadhe teen lakh", "2,50,000" | same module, lakh/crore aware |
| Self-correction: "98765 nahi 98766…", and at read-back "5 nahi 6", "last digit 4", "teesra digit 7" | `numbers.compose_segments`, `parsers.correct_digits` (asks again if the digit appears twice) |
| Wrong numbers on official forms | Read-back after **every** answer, spoken slowly, digit by digit in groups |
| Fake Aadhaar numbers | 12 digits + Verhoeff checksum (`verhoeff.py`); phone must start with 6-9; PIN not 0; age 15-35 |
| Hinglish | Prisma v3 with `hi-IN,en-IN`; per-field output format (`transliterate` for names, `codemix` for choices) |
| Timbre mispronouncing digits | Every number is converted to spoken words before TTS (`speak.py`), as Gnani's docs advise |
| Silence / background noise | Browser-side voice detection; nothing is sent to Prisma if nobody spoke (saves credits) |

Adding another form means adding a JSON file in `backend/app/forms/` (fields, prompts in both languages, validators).

## Protecting your 5,000 credits
- The API key lives only on the server. The browser never sees it (there is a test for this).
- Fixed questions are synthesised once and cached on disk. Read-backs of personal data are **never** cached.
- Hard limits (see `.env.example`): total and per-session voice calls, session count. When a limit is hit, typing still works.
- If Timbre fails, the browser's own voice speaks so a live demo never goes silent.

## Privacy
Answers live in server memory only. They are deleted after 30 minutes, on "Delete my data", or when the tab closes.
The Aadhaar number is masked on screen (`XXXX XXXX 0124`); the full number appears only in the PDF you download.
Transcripts are not logged unless `LOG_TRANSCRIPTS=1`. **Don't use real IDs in your demo video.**

## Putting it online (optional)
`Dockerfile` is included (untested here, so build it once before relying on it). Sessions are held in memory,
so run **one worker**. Set `GNANI_API_KEY` as an environment variable on the host, never in the repo.
The microphone only works on `https://` or `localhost`; most hosts give you https automatically.

## Known limits (honest list)
- **Not yet tested against the live Gnani API** — no key was available while this was built. The code follows the
  published docs and is tested against a mock of them. Run `python -m tools.check_gnani` first; if Prisma or Timbre
  behave differently from the docs, the fixes will be small and in `backend/app/gnani.py`.
- Hindi/Hinglish and English only (Prisma and Timbre support 10 languages; the form text is the part that is Hindi/English).
- One form. Push-to-talk with automatic stop on silence, not streaming. Streaming would cut latency by roughly a second.
- Names arrive in Roman letters (the PDF's built-in font has no Devanagari).
- Heavy accents, a noisy room, or a bad phone mic will cause mistakes. That is exactly why the read-back exists.

## Layout
```
backend/app/   main.py (HTTP)  service.py (glue + limits)  dialogue.py (state machine)  fields.py  parsers.py
               numbers.py  lexicon.py  speak.py  verhoeff.py  gnani.py (API client)  pdf.py  i18n.py  forms/scholarship.json
backend/tests/ unit, HTTP, and Gnani-client tests + fake_gnani.py + run_fake_server.py
backend/tools/ check_gnani.py
frontend/      index.html  style.css  app.js   (no build step)
docs/          demo-script-60s.md   linkedin-post.md
```
