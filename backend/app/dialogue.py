"""The dialogue manager: a small state machine that walks through the form one field at a time.

    ASK  ──(parsed + valid)──▶  CONFIRM  ──(yes)──▶  next field's ASK
     ▲                              │
     └────────(no / unclear)────────┘                 after the last field
                                                            │
                                                          REVIEW ──(all correct)──▶ DONE
                                                            │
                                                     "change phone number"
                                                            └──▶ ASK that field, then back to REVIEW

Navigation works in every state: "repeat", "go back", "start over".
Everything here is plain Python with no network calls, so it is fully unit-testable.
"""
import re
import time
import uuid
from dataclasses import dataclass
from datetime import date
from typing import List, Optional

from . import fields as F
from . import parsers
from .i18n import FIELD_KEYWORDS, t
from .lexicon import canon
from .numbers import tokenize

ASK, CONFIRM, REVIEW, DONE = "ask", "confirm", "review", "done"


@dataclass
class BotMessage:
    id: str
    text: str            # shown on screen
    speech: str          # sent to TTS (numbers as words)
    tts_lang: str        # hi-IN | en-IN | hi-en
    speed: Optional[float] = None
    cacheable: bool = False   # static prompts can be cached on disk; read-backs of personal data never are
    kind: str = "prompt"      # prompt | confirm | error | info


class Session:
    def __init__(self, form: dict, lang: str = "hi", today: Optional[date] = None):
        self.id = uuid.uuid4().hex
        self.form = form
        self.lang = lang if lang in ("hi", "en") else "hi"
        self.today = today
        self.idx = 0
        self.values: dict = {}
        self.pending = None
        self.state = ASK
        self.retries = 0
        self.edit_return = False
        self.messages: dict = {}            # id -> BotMessage (so audio can be fetched later)
        self.created = self.last_active = time.time()
        self.stt_calls = 0

    # ------------------------------------------------------------------ helpers
    @property
    def fields(self) -> list:
        return self.form["fields"]

    @property
    def field(self) -> dict:
        return self.fields[min(self.idx, len(self.fields) - 1)]

    def touch(self) -> None:
        self.last_active = time.time()

    def _msg(self, kind: str, text: str, speech: Optional[str] = None, cacheable=False, speed=None) -> BotMessage:
        speech = F.speechify(speech if speech is not None else text, self.lang)
        if self.lang == "en":
            tts_lang = "en-IN"
        else:
            tts_lang = "hi-en" if re.search(r"[A-Za-z]", speech) else "hi-IN"
        m = BotMessage(uuid.uuid4().hex[:8], text, speech, tts_lang, speed, cacheable, kind)
        self.messages[m.id] = m
        return m

    def _prompt_texts(self, f: dict):
        raw = f["prompt"][self.lang]
        if "{options}" in raw:
            shown = ", ".join(o["label"][self.lang] for o in f["options"])
            spoken = ", ".join(o["speech"][self.lang] for o in f["options"])
            return raw.format(options=shown), raw.format(options=spoken)
        return raw, raw

    def _prompt_msg(self, prefix: str = "", kind: str = "prompt") -> BotMessage:
        shown, spoken = self._prompt_texts(self.field)
        sep = " " if prefix else ""
        return self._msg(kind, prefix + sep + shown, prefix + sep + spoken, cacheable=True)

    def _confirm_msg(self) -> BotMessage:
        f = self.field
        shown, spoken = F.fmt(f, self.pending, self.lang)
        tpl = f["confirm"][self.lang]
        slow = 0.9 if f["type"] in ("digits", "date", "amount") else None
        return self._msg("confirm", tpl.format(v=shown), tpl.format(v=spoken), speed=slow)

    def _error_msg(self, res: F.Parsed) -> BotMessage:
        self.retries += 1
        text = t(res.error, self.lang, **res.params)
        if self.retries >= 2:
            text += " " + t("type_hint", self.lang)
        return self._msg("error", text)

    def _review_msg(self) -> BotMessage:
        return self._msg("info", t("review", self.lang), cacheable=True)

    # ------------------------------------------------------------------ public API
    def start(self) -> List[BotMessage]:
        shown, spoken = self._prompt_texts(self.field)
        g = t("greeting", self.lang)
        return [self._msg("prompt", f"{g} {shown}", f"{g} {spoken}", cacheable=True)]

    def stt_hint(self) -> dict:
        """What the speech recogniser should expect right now."""
        f = self.field
        if self.state == REVIEW:
            return {"format": "transcribe", "keyterms": []}
        return {"format": f.get("stt_format", "transcribe"), "keyterms": f.get("keyterms", [])}

    def handle(self, text: str) -> List[BotMessage]:
        self.touch()
        text = (text or "").strip()
        if self.state == DONE:
            return [self._msg("info", t("already_done", self.lang), cacheable=True)]
        if not text:
            return [self._msg("error", t("no_speech", self.lang), cacheable=True)]
        cmd = parsers.command(text)
        if cmd:
            return self._command(cmd)
        if self.state == ASK:
            return self._on_answer(text)
        if self.state == CONFIRM:
            return self._on_confirm(text)
        return self._on_review(text)

    # ------------------------------------------------------------------ navigation commands
    def _command(self, cmd: str) -> List[BotMessage]:
        if cmd == "restart":
            self.values.clear()
            self.idx, self.pending, self.state, self.retries, self.edit_return = 0, None, ASK, 0, False
            return [self._prompt_msg(t("restart", self.lang))]
        if cmd == "repeat":
            if self.state == CONFIRM:
                return [self._confirm_msg()]
            if self.state == REVIEW:
                return [self._review_msg()]
            return [self._prompt_msg()]
        # back
        self.edit_return = False
        if self.state == REVIEW:
            self.idx = len(self.fields) - 1
        elif self.idx == 0:
            self.pending, self.state = None, ASK
            return [self._prompt_msg(t("first_question", self.lang))]
        else:
            self.idx -= 1
        self.values.pop(self.field["id"], None)
        self.pending, self.state, self.retries = None, ASK, 0
        return [self._prompt_msg()]

    # ------------------------------------------------------------------ ASK
    def _on_answer(self, text: str) -> List[BotMessage]:
        res = F.parse_field(self.field, text, self.lang, self.today)
        if not res.ok:
            return [self._error_msg(res)]
        self.pending, self.state, self.retries = res.value, CONFIRM, 0
        return [self._confirm_msg()]

    # ------------------------------------------------------------------ CONFIRM
    def _on_confirm(self, text: str) -> List[BotMessage]:
        f = self.field
        polarity = parsers.yes_no(text)

        # 1. spoken correction of a digit string: "5 nahi 6", "last digit 4", "teesra digit 7"
        if f["type"] == "digits" and polarity != "yes":
            fixed, problem = parsers.correct_digits(self.pending, text)
            if problem == "ambiguous":
                return [self._msg("error", t("ambiguous_digit", self.lang))]
            if fixed and fixed != self.pending:
                res = F.validate_digits(f, fixed, self.lang)
                if res.ok:
                    self.pending = res.value
                    return [self._confirm_msg()]
                self.pending, self.state = None, ASK
                return [self._error_msg(res)]

        # 2. a whole new answer instead of yes/no ("nahi, 9876543211")
        if polarity != "yes":
            res = F.parse_field(f, text, self.lang, self.today)
            if res.ok and res.value != self.pending:
                self.pending = res.value
                return [self._confirm_msg()]

        if polarity == "yes":
            return self._commit()
        if polarity == "no":
            self.pending, self.state = None, ASK
            return [self._prompt_msg(t("retry", self.lang))]
        return [self._msg("error", t("yes_no", self.lang), cacheable=True)]

    def _commit(self) -> List[BotMessage]:
        self.values[self.field["id"]] = self.pending
        self.pending, self.retries = None, 0
        if self.edit_return:
            self.edit_return, self.state = False, REVIEW
            return [self._msg("info", t("review_more", self.lang), cacheable=True)]
        self.idx += 1
        if self.idx >= len(self.fields):
            self.idx = len(self.fields) - 1
            self.state = REVIEW
            return [self._review_msg()]
        self.state = ASK
        return [self._prompt_msg(t("ack", self.lang))]

    # ------------------------------------------------------------------ REVIEW
    def _find_field(self, text: str) -> Optional[int]:
        toks = {canon(x) for x in tokenize(text)}
        for i, f in enumerate(self.fields):
            if any(canon(k) in toks for k in FIELD_KEYWORDS.get(f["id"], [])):
                return i
        return None

    def _on_review(self, text: str) -> List[BotMessage]:
        i = self._find_field(text)
        if i is not None:
            self.idx, self.state, self.edit_return, self.retries = i, ASK, True, 0
            self.pending = None
            return [self._prompt_msg()]
        if parsers.wants_submit(text):
            self.state = DONE
            return [self._msg("info", t("done", self.lang), cacheable=True)]
        if parsers.yes_no(text) == "no":
            return [self._msg("info", t("review_which", self.lang), cacheable=True)]
        return [self._msg("error", t("review_unclear", self.lang), cacheable=True)]

    # ------------------------------------------------------------------ what the UI shows
    def snapshot(self) -> dict:
        rows = []
        for i, f in enumerate(self.fields):
            fid = f["id"]
            row = {"id": fid, "label": f["label"][self.lang], "status": "todo", "display": "", "pending": ""}
            if fid in self.values:
                row["status"] = "done"
                row["display"] = F.fmt(f, self.values[fid], self.lang, masked=True)[0]
            if self.state in (ASK, CONFIRM) and i == self.idx:
                row["status"] = "confirm" if self.state == CONFIRM else "active"
                if self.state == CONFIRM and self.pending is not None:
                    row["pending"] = F.fmt(f, self.pending, self.lang)[0]
            rows.append(row)
        done = len(self.values)
        return {
            "title": self.form["title"][self.lang],
            "state": self.state,
            "current": self.field["id"] if self.state in (ASK, CONFIRM) else None,
            "fields": rows,
            "done": done,
            "total": len(self.fields),
            "complete": self.state == DONE,
        }
