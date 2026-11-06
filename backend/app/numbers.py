"""Spoken numbers -> digits / amounts.

Pipeline:  text -> tokens -> classified tokens -> number groups -> digit string or value.

The hard parts this handles:
  * digits said one by one         "nau aath saat ..."        -> 987...
  * pairs                          "ninety eight seventy six"  -> 9876
  * repeats                        "double nine"               -> 99
  * Indian amounts                 "do lakh pachas hazaar"     -> 250000
  * fractions                      "dhai lakh", "saadhe teen lakh", "sava lakh"
  * self-correction                "9876 nahi 9877 ..." / "... 5 nahi 6"
"""
import re
from dataclasses import dataclass
from typing import List, Optional

from . import lexicon as L

_DEV_DIGITS = str.maketrans("०१२३४५६७८९", "0123456789")
_TOKEN_RE = re.compile(r"\d+(?:\.\d+)?|[^\d\s,.;:!?()\[\]\"'।/\\|_+=*<>{}\-–—]+")

_PHRASE_MARKERS = [  # multi-word corrections collapsed into one marker word
    (re.compile(r"\b(?:ki|ke)\s+jagah\b|(?:की|के)\s+जगह|\bi\s+mean\b|\bi\s+meant\b|\bnot\s+that\b|\bnahi\s+nahi\b"), " nahi "),
]


@dataclass
class Tok:
    kind: str            # num | mult | repeat | mod | month | ord | corr | skip | word
    raw: str
    value: float = 0
    literal: bool = False
    en_tens: bool = False


@dataclass
class Group:
    kind: str = "group"
    value: float = 0
    text: Optional[str] = None   # literal digits exactly as written (keeps leading zeros)
    repeat: int = 1

    def digits(self) -> str:
        if self.text is not None and "." not in self.text:
            s = self.text
        else:
            v = self.value
            s = str(int(round(v))) if float(v).is_integer() or v > 100 else str(v)
        return s * self.repeat


def normalize(text: str) -> str:
    t = (text or "").lower().translate(_DEV_DIGITS)
    t = re.sub(r"(?<=\d),(?=\d)", "", t)         # 2,50,000 -> 250000
    t = t.replace("₹", " rs ")
    for rx, rep in _PHRASE_MARKERS:
        t = rx.sub(rep, t)
    return t


def tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(normalize(text))


def classify(raw: str) -> Tok:
    if re.fullmatch(r"\d+(?:\.\d+)?", raw):
        return Tok("num", raw, float(raw) if "." in raw else int(raw), literal=True)
    c = L.canon(raw)
    if c in L.NUMS:
        v, tens = L.NUMS[c]
        return Tok("num", raw, v, en_tens=tens)
    if c in L.MULTS:
        return Tok("mult", raw, L.MULTS[c])
    if c in L.REPEATS:
        return Tok("repeat", raw, L.REPEATS[c])
    if c in L.MODS:
        return Tok("mod", raw, L.MODS[c])
    if c in L.MONTHS:
        return Tok("month", raw, L.MONTHS[c])
    if c in L.ORDINALS:
        return Tok("ord", raw, L.ORDINALS[c])
    if c in L.CORR:
        return Tok("corr", raw)
    if c in L.FILLERS:
        return Tok("skip", raw)
    return Tok("word", raw)


def build_items(toks: List[Tok]) -> list:
    """Group consecutive number words into numbers; pass other tokens through unchanged."""
    items: list = []
    g = None
    mod = None
    rep = 1

    def close():
        nonlocal g
        if g is not None:
            literal = g["lit"] if (g["n"] == 1 and g["mults"] == 0) else None
            items.append(Group(value=g["total"] + g["cur"], text=literal, repeat=g["rep"]))
            g = None

    for t in toks:
        if t.kind == "skip":
            continue
        if t.kind == "repeat":
            close()
            rep = int(t.value)
        elif t.kind == "mod":
            close()
            mod = t.value
        elif t.kind == "num":
            v = t.value
            if mod is not None:
                v += mod
                mod = None
            if g is None:
                g = dict(total=0, cur=v, last="num", tens=t.en_tens, lit=t.raw if t.literal else None,
                         n=1, mults=0, rep=rep)
                rep = 1
            elif g["last"] == "mult":
                g["cur"] += v
                g["last"], g["tens"] = "num", t.en_tens
                g["n"] += 1
            elif g["last"] == "num" and g["tens"] and not t.literal and not t.en_tens and 0 < v < 10:
                g["cur"] += v                       # English "twenty" + "five"
                g["tens"] = False
                g["n"] += 1
            else:
                close()
                g = dict(total=0, cur=v, last="num", tens=t.en_tens, lit=t.raw if t.literal else None,
                         n=1, mults=0, rep=rep)
                rep = 1
        elif t.kind == "mult":
            m = t.value
            if g is None:
                base = 1 + (mod or 0)
                mod = None
                g = dict(total=0, cur=base, last="num", tens=False, lit=None, n=1, mults=0, rep=1)
            if m == 100:
                g["cur"] = (g["cur"] or 1) * 100
            else:
                g["total"] += (g["cur"] or 1) * m
                g["cur"] = 0
            g["last"] = "mult"
            g["mults"] += 1
        else:
            close()
            items.append(t)
    close()
    return items


def items_from_text(text: str) -> list:
    return build_items([classify(r) for r in tokenize(text)])


# ----------------------------------------------------------------------------- digits
def _segments(items: list) -> List[str]:
    """Digit strings between self-correction markers, e.g. '98765 nahi 98766' -> ['98765','98766']."""
    segs, cur = [], []
    for it in items:
        if getattr(it, "kind", "") == "corr":
            segs.append("".join(cur))
            cur = []
        elif isinstance(it, Group):
            cur.append(it.digits())
    segs.append("".join(cur))
    return [s for s in segs if s]


def compose_segments(segs: List[str]) -> str:
    """Apply 'A nahi B' corrections: B replaces the tail of A (or restarts if B is as long as A)."""
    acc = ""
    for s in segs:
        if not acc:
            acc = s
        elif len(s) >= len(acc):
            acc = s
        else:
            acc = acc[:-len(s)] + s
    return acc


def digits_from_text(text: str) -> str:
    """All digits the person said, with in-sentence self-corrections applied."""
    return compose_segments(_segments(items_from_text(text)))


def digit_segments(text: str) -> List[str]:
    return _segments(items_from_text(text))


# ----------------------------------------------------------------------------- amounts
def amount_from_text(text: str) -> Optional[int]:
    items = items_from_text(text)
    # keep only what follows the last correction marker ("do lakh nahi teen lakh")
    last = max((i for i, it in enumerate(items) if getattr(it, "kind", "") == "corr"), default=-1)
    groups = [it for it in items[last + 1:] if isinstance(it, Group)]
    if not groups:
        return None
    if len(groups) == 1:
        return int(round(groups[0].value))
    # several groups: accept only a clean "big then smaller" spoken form, e.g. "2 lakh" + "50 hazaar"
    total, prev_unit = 0, None
    for g in groups:
        v = int(round(g.value))
        unit = _lowest_unit(v)
        if prev_unit is not None and unit >= prev_unit:
            return None
        total += v
        prev_unit = unit
    return total


def _lowest_unit(v: int) -> int:
    if v <= 0:
        return 1
    u = 1
    while v % 10 == 0:
        v //= 10
        u *= 10
    return u
