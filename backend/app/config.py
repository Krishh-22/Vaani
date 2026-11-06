"""Settings, read from environment variables (and an optional .env file)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]          # backend/
PROJECT = ROOT.parent                               # project root


def _load_env_file(path: Path) -> None:
    """Tiny .env loader so we don't need python-dotenv. Real env vars win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_env_file(PROJECT / ".env")
_load_env_file(ROOT / ".env")


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, default))
    except ValueError:
        return default


class Settings:
    # --- Gnani ---
    api_key: str = os.environ.get("GNANI_API_KEY", "").strip()
    base_url: str = os.environ.get("GNANI_BASE_URL", "https://api.vachana.ai").rstrip("/")
    stt_model: str = os.environ.get("STT_MODEL", "prisma-v3.0")
    # Languages sent to Prisma. Hinglish speakers: Hindi first, English second.
    stt_langs_hi: str = os.environ.get("STT_LANGS_HI", "hi-IN,en-IN")
    stt_langs_en: str = os.environ.get("STT_LANGS_EN", "en-IN,hi-IN")
    # Set STT_FORMAT_OVERRIDE=verbatim|transcribe|codemix|transliterate to force one format for all fields.
    stt_format_override: str = os.environ.get("STT_FORMAT_OVERRIDE", "").strip()
    stt_use_keyterms: bool = os.environ.get("STT_USE_KEYTERMS", "1") != "0"
    tts_model: str = os.environ.get("TTS_MODEL", "timbre-v2.5")
    tts_voice: str = os.environ.get("TTS_VOICE", "Nalini")
    tts_speed: float = _float("TTS_SPEED", 1.0)
    tts_sample_rate: int = _int("TTS_SAMPLE_RATE", 24000)
    http_timeout: int = _int("HTTP_TIMEOUT", 40)

    # --- App / safety ---
    session_ttl_seconds: int = _int("SESSION_TTL_SECONDS", 30 * 60)
    max_sessions: int = _int("MAX_SESSIONS", 200)
    # Credit guards: a public demo should not be able to burn all 5,000 credits.
    max_stt_calls: int = _int("MAX_STT_CALLS", 600)
    max_tts_calls: int = _int("MAX_TTS_CALLS", 2000)
    max_stt_per_session: int = _int("MAX_STT_PER_SESSION", 60)
    log_transcripts: bool = os.environ.get("LOG_TRANSCRIPTS", "0") == "1"
    tts_cache_dir: Path = Path(os.environ.get("TTS_CACHE_DIR", str(PROJECT / ".cache" / "tts")))

    @property
    def configured(self) -> bool:
        return bool(self.api_key)


settings = Settings()
