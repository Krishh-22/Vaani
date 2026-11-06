"""Field types: parse what was said, validate it, and format it for the screen and for the voice."""
import json
import re
from dataclasses import dataclass, field as dc_field
from datetime import date
from pathlib import Path
from typing import Optional, Tuple

from . import parsers, speak, verhoeff
from .numbers import amount_from_text, digits_from_text

FORMS_DIR = Path(__file__).parent / "forms"


def load_form(name: str = "scholarship") -> dict:
    return json.loads((FORMS_DIR / f"{name}.json").read_text(encoding="utf-8"))


@dataclass
class Parsed:
    ok: bool
    value: object = None
    error: Optional[str] = None            # key into i18n.STR
    params: dict = dc_field(default_factory=dict)


def _bad(error: str, **params) -> Parsed:
    return Parsed(False, None, error, params)


# ----------------------------------------------------------------------------- digits
def validate_digits(f: dict, digits: str, lang: str = "en") -> Parsed:
    if f.get("strip_country_code"):
        if len(digits) == 12 and digits.startswith("91"):
            digits = digits[2:]
        elif len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]
    need = f["length"]
    if len(digits) != need:
        return _bad("digits_count", n=len(digits), need=need)
    ok_first = f.get("first_digits")
    if ok_first and digits[0] not in ok_first:
        return _bad("first_digit", ok=", ".join(ok_first[:-1]) + (" या " if lang == "hi" else " or ") + ok_first[-1])
    bad_first = f.get("not_first_digits")
    if bad_first and digits[0] in bad_first:
        return _bad("bad_first_digit", bad=digits[0])
    if f.get("verhoeff") and not verhoeff.is_valid(digits):
        return _bad("checksum")
    return Parsed(True, digits)


# ----------------------------------------------------------------------------- dispatcher
def parse_field(f: dict, text: str, lang: str, today: Optional[date] = None) -> Parsed:
    t = f["type"]
    if t == "digits":
        return validate_digits(f, digits_from_text(text), lang)
    if t == "amount":
        n = amount_from_text(text)
        if n is None:
            return _bad("amount_unclear")
        if not (f.get("min", 0) <= n <= f.get("max", 10 ** 12)):
            return _bad("amount_range")
        return Parsed(True, n)
    if t == "date":
        d, err = parsers.parse_date(text, today)
        if err:
            return _bad("date_unclear" if err == "unclear" else "date_invalid")
        age = parsers.age_on(d, today)
        lo, hi = f.get("min_age", 0), f.get("max_age", 200)
        if not (lo <= age <= hi):
            return _bad("age_range", min=lo, max=hi)
        return Parsed(True, d.isoformat())
    if t == "choice":
        v = parsers.parse_choice(text, f["options"])
        if v is None:
            opts = ", ".join(o["label"][lang] for o in f["options"])
            return _bad("choice_unclear", options=opts)
        return Parsed(True, v)
    if t == "name":
        n = parsers.extract_name(text)
        return Parsed(True, n) if n else _bad("name_unclear")
    raise ValueError(f"unknown field type {t}")


# ----------------------------------------------------------------------------- formatting
def mask(digits: str) -> str:
    return "XXXX XXXX " + digits[-4:]


def fmt(f: dict, value, lang: str, masked: bool = False) -> Tuple[str, str]:
    """-> (text for the screen, text for the voice)"""
    t = f["type"]
    if t == "digits":
        shown = speak.show_digits(value, f.get("group"))
        if masked and f.get("mask"):
            shown = mask(value)
        return shown, speak.speak_digits(value, lang, f.get("group"))
    if t == "amount":
        return speak.show_amount(value), speak.speak_amount(value, lang)
    if t == "date":
        d = date.fromisoformat(value)
        return speak.show_date(d), speak.speak_date(d, lang)
    if t == "choice":
        opt = next(o for o in f["options"] if o["value"] == value)
        return opt["label"][lang], opt["speech"][lang]
    return value, value


def speechify(text: str, lang: str) -> str:
    """Replace any leftover digits in a sentence with spoken words (Timbre reads words best)."""
    def rep(m):
        s = m.group(0)
        return speak.words(int(s), lang) if len(s) <= 9 else s
    return re.sub(r"\d+", rep, text)
