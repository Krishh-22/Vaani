"""Rule-based parsers for everything except raw digits/amounts (see numbers.py).

Each parser takes the transcript text and returns a value, or None when it
can't make sense of it. Validation (is this a legal Aadhaar?) lives in
fields.py - parsing here only answers "what did the person say?".
"""
import re
from datetime import date
from difflib import get_close_matches
from typing import List, Optional, Tuple

from . import lexicon as L
from .numbers import Group, Tok, classify, items_from_text, tokenize, digit_segments


# ----------------------------------------------------------------------------- yes / no
def yes_no(text: str) -> Optional[str]:
    """'yes' | 'no' | None. When both appear ('haan nahi'), the last one wins."""
    last, weak = None, False
    for raw in tokenize(text):
        c = L.canon(raw)
        if c in L.NO:
            last = "no"
        elif c in L.YES:
            last = "yes"
        elif c in L.WEAK_YES and last is None:
            weak = True
    return last or ("yes" if weak else None)


def _contains_phrase(text: str, phrases: List[str]) -> bool:
    t = " " + " ".join(tokenize(text)) + " "
    return any(" " + " ".join(tokenize(p)) + " " in t for p in phrases)


def command(text: str) -> Optional[str]:
    """Short navigation commands: 'repeat' | 'back' | 'restart'. Only for short utterances without numbers."""
    toks = tokenize(text)
    if not toks or len(toks) > 5:
        return None
    if any(classify(t).kind in ("num", "mult", "month") for t in toks):
        return None
    if _contains_phrase(text, L.RESTART_CMDS):
        return "restart"
    if _contains_phrase(text, L.BACK_CMDS):
        return "back"
    if _contains_phrase(text, L.REPEAT_CMDS):
        return "repeat"
    return None


def wants_submit(text: str) -> bool:
    return yes_no(text) == "yes" or _contains_phrase(text, L.SUBMIT_WORDS)


# ----------------------------------------------------------------------------- name
_LEAD = re.compile(
    r"^\s*(?:"
    r"(?:mera|meraa)\s+(?:poora\s+|pura\s+)?(?:naam|nam|name)\s*(?:hai\s*)?|"
    r"my\s+(?:full\s+)?name\s+is\s+|(?:the\s+)?name\s+is\s+|full\s+name\s+is\s+|"
    r"i\s+am\s+|i'm\s+|this\s+is\s+|main\s+|mai\s+|"
    r"मेरा\s+(?:पूरा\s+)?नाम\s*(?:है\s*)?|मैं\s+|मै\s+|नाम\s+|"
    r"(?:haan|han|ji|umm?|uh|ok|okay|जी|हाँ|हां)[\s,]+"
    r")", re.I)
_CUT = re.compile(
    r"(?:[,.;!?।]|\s+(?:aur|and|main|mai|from|i\s+live|i\s+am|living|और|मैं|मै)\s).*$", re.I)
_TRAIL = re.compile(r"(?:\s+(?:hai|hain|hoon|hun|hu|ji|please|plz|है|हैं|हूँ|हूं|जी))+\s*$", re.I)


def extract_name(text: str) -> Optional[str]:
    t = (text or "").strip()
    for _ in range(4):                       # peel off several lead-ins
        new = _LEAD.sub("", t, count=1)
        if new == t:
            break
        t = new
    t = _CUT.sub("", t)
    t = _TRAIL.sub("", t).strip()
    parts = [p for p in re.split(r"\s+", t) if p]
    parts = [p.strip("-'\".") for p in parts]
    parts = [p for p in parts if p and not any(ch.isdigit() for ch in p)]
    if not parts or len(parts) > 5:
        return None
    junk = L.YES | L.NO | L.CORR | L.WEAK_YES | L.FILLERS | {L.canon(w) for w in (
        "umm um uh hmm hm acha accha achha aaa aah ah oh well so okay".split())}
    if all(L.canon(p) in junk for p in parts):          # "nahi", "haan ji" are not names
        return None
    if sum(ch.isalpha() or "ऀ" <= ch <= "ॿ" for ch in "".join(parts)) < 2:
        return None
    if all(p.isascii() for p in parts):
        parts = [p[:1].upper() + p[1:].lower() if p.islower() or p.isupper() else p for p in parts]
    return " ".join(parts)


# ----------------------------------------------------------------------------- date
def _two_digit_year(yy: int, today: date) -> int:
    return 2000 + yy if yy <= today.year % 100 else 1900 + yy


def parse_date(text: str, today: Optional[date] = None) -> Tuple[Optional[date], Optional[str]]:
    """Returns (date, None) or (None, 'unclear' | 'invalid')."""
    today = today or date.today()
    items = items_from_text(text)
    last = max((i for i, it in enumerate(items) if getattr(it, "kind", "") == "corr"), default=-1)
    items = items[last + 1:]
    groups: List[Group] = [it for it in items if isinstance(it, Group)]
    months = [it.value for it in items if isinstance(it, Tok) and it.kind == "month"]

    # one literal blob: 15082005 or 150805
    if len(groups) == 1 and groups[0].text and groups[0].text.isdigit() and not months:
        s = groups[0].text
        if len(s) == 8:
            groups = [Group(value=int(s[:2]), text=s[:2]), Group(value=int(s[2:4]), text=s[2:4]),
                      Group(value=int(s[4:]), text=s[4:])]
        elif len(s) == 6:
            groups = [Group(value=int(s[:2]), text=s[:2]), Group(value=int(s[2:4]), text=s[2:4]),
                      Group(value=int(s[4:]), text=s[4:])]

    vals = [int(round(g.value)) for g in groups]
    # "nineteen ninety nine" -> 19, 99 -> 1999 (only when the pair ends the sentence)
    if len(vals) >= 2 and vals[-2] in (19, 20) and 0 <= vals[-1] <= 99 and (months and len(vals) >= 3 or len(vals) >= 4):
        vals = vals[:-2] + [vals[-2] * 100 + vals[-1]]

    day = month = year = None
    if months:
        month = int(months[0])
        rest = list(vals)
        years = [v for v in rest if v >= 100]
        if years:
            year = years[-1]
            rest.remove(year)
        days = [v for v in rest if 1 <= v <= 31]
        if days:
            day = days[0]
            rest.remove(day)
        if year is None and rest:
            year = _two_digit_year(rest[0], today)
    elif len(vals) >= 3:
        day, month, year = vals[-3], vals[-2], vals[-1]
        if year < 100:
            year = _two_digit_year(year, today)
    if None in (day, month, year):
        return None, "unclear"
    try:
        d = date(year, month, day)
    except ValueError:
        return None, "invalid"
    if d > today or year < 1900:
        return None, "invalid"
    return d, None


def age_on(d: date, today: Optional[date] = None) -> int:
    today = today or date.today()
    return today.year - d.year - ((today.month, today.day) < (d.month, d.day))


# ----------------------------------------------------------------------------- choices
def _compact(s: str) -> str:
    return "".join(ch for ch in s.lower() if ch.isalpha() or "ऀ" <= ch <= "ॿ")


def _merged_tokens(tokens: List[str]) -> List[str]:
    """Join spoken letters: 'b tech' -> 'btech', 'o b c' -> 'obc'."""
    out, run = [], ""
    for t in tokens:
        short = len(t) == 1 or (t.isascii() is False and len(t) <= 2)
        if short:
            run += t
        else:
            if run:
                out.append(run + t if run else t)
                run = ""
            else:
                out.append(t)
    if run:
        out.append(run)
    return out


def parse_choice(text: str, options: List[dict]) -> Optional[str]:
    """options: [{'value': 'obc', 'synonyms': ['obc','other backward', ...]}]. Longest match wins."""
    tokens = [t for t in tokenize(text) if t]
    if not tokens:
        return None
    merged = _merged_tokens(tokens)
    compact = _compact("".join(tokens))
    joined = " " + " ".join(tokens) + " "
    best, best_len, tie = None, 0, False
    for opt in options:
        for syn in opt["synonyms"]:
            sc = _compact(syn)
            if not sc:
                continue
            hit = False
            if " " + " ".join(tokenize(syn)) + " " in joined:        # whole-phrase match
                hit = True
            elif merged and sc in [_compact(m) for m in merged]:    # spoken letters merged
                hit = True
            elif len(sc) >= 4 and sc in compact:                     # long synonyms: substring of run-together text
                hit = True
            if hit:
                if len(sc) > best_len:
                    best, best_len, tie = opt["value"], len(sc), False
                elif len(sc) == best_len and best != opt["value"]:
                    tie = True
    if best and not tie:
        return best
    if best is None:                                   # typo-tolerant fallback
        pool = {}
        for opt in options:
            for syn in opt["synonyms"]:
                pool[_compact(syn)] = opt["value"]
        latin_pool = [k for k in pool if k.isascii()]
        for m in merged + [compact]:
            mc = _compact(m)
            if len(mc) >= 5 and mc.isascii():            # Latin only: Devanagari fuzzy gave false hits
                close = get_close_matches(mc, latin_pool, n=1, cutoff=0.84)
                if close:
                    return pool[close[0]]
    return None


# ----------------------------------------------------------------------------- digit corrections
def correct_digits(pending: str, text: str) -> Tuple[Optional[str], Optional[str]]:
    """Fix a read-back number from a spoken correction.

    Returns (new_value, problem). problem is 'ambiguous' when the wrong digit appears
    more than once; (None, None) means 'this wasn't a correction'.
    Supported:  "5 nahi 6"  |  "nahi, 5 nahi 6"  |  "teesra digit 7"  |  "last digit 4"
    """
    toks = [classify(r) for r in tokenize(text)]
    # positional: ordinal word + a digit
    ords = [t for t in toks if t.kind == "ord"]
    if ords:
        digs = [d for d in digit_segments(text) if d]
        if digs and len(digs[-1]) == 1:
            pos = int(ords[0].value)
            idx = len(pending) - 1 if pos == -1 else pos - 1
            if 0 <= idx < len(pending):
                return pending[:idx] + digs[-1] + pending[idx + 1:], None
    segs = digit_segments(text)
    has_marker = any(t.kind == "corr" for t in toks)
    if has_marker and len(segs) == 2 and len(segs[0]) == len(segs[1]):
        wrong, right = segs
        n = pending.count(wrong)
        if n == 1:
            return pending.replace(wrong, right), None
        if n > 1:
            return None, "ambiguous"
    return None, None
