from datetime import date

import pytest

from app import fields as F
from app import verhoeff
from app.dialogue import ASK, CONFIRM, DONE, REVIEW, Session
from app.parsers import extract_name, parse_choice, yes_no

TODAY = date(2026, 11, 6)
GOOD_AADHAAR = verhoeff.make_valid_aadhaar("23456789012")


def new(lang="hi") -> Session:
    s = Session(F.load_form("scholarship"), lang, today=TODAY)
    s.start()
    return s


def run(s, *utterances):
    out = None
    for u in utterances:
        out = s.handle(u)
    return out


def fill_until(s, field_id):
    """Answer every field before `field_id` correctly."""
    answers = {
        "name": ("mera naam Krishna Kumar hai", "haan"),
        "dob": ("15 August 2005", "haan"),
        "phone": ("9876543210", "haan"),
        "aadhaar": (GOOD_AADHAAR, "haan"),
        "pincode": ("226010", "haan"),
        "category": ("obc", "haan"),
        "income": ("do lakh pachas hazaar", "haan"),
        "course": ("b tech", "haan"),
    }
    for f in s.fields:
        if f["id"] == field_id:
            return
        run(s, *answers[f["id"]])


# ----------------------------------------------------------------------------- happy path
@pytest.mark.parametrize("lang", ["hi", "en"])
def test_full_form(lang):
    s = new(lang)
    fill_until(s, "__end__")
    assert s.state == REVIEW
    run(s, "all correct")
    assert s.state == DONE
    assert s.values == {
        "name": "Krishna Kumar", "dob": "2005-08-15", "phone": "9876543210", "aadhaar": GOOD_AADHAAR,
        "pincode": "226010", "category": "obc", "income": 250000, "course": "btech",
    }


# ----------------------------------------------------------------------------- validation + re-ask
def test_phone_wrong_length_reasks_without_advancing():
    s = new()
    fill_until(s, "phone")
    out = run(s, "98765 4321")
    assert s.state == ASK and s.field["id"] == "phone"
    assert out[0].kind == "error"


def test_phone_must_start_6_to_9():
    s = new()
    fill_until(s, "phone")
    run(s, "1234567890")
    assert s.state == ASK


def test_aadhaar_checksum_rejected_then_accepted():
    s = new()
    fill_until(s, "aadhaar")
    bad = GOOD_AADHAAR[:-1] + str((int(GOOD_AADHAAR[-1]) + 1) % 10)
    run(s, bad)
    assert s.state == ASK and s.field["id"] == "aadhaar"
    run(s, GOOD_AADHAAR)
    assert s.state == CONFIRM and s.pending == GOOD_AADHAAR


def test_underage_dob_rejected():
    s = new()
    fill_until(s, "dob")
    run(s, "1 january 2020")
    assert s.state == ASK


def test_error_hint_to_type_appears_on_second_failure():
    s = new("en")
    fill_until(s, "phone")
    run(s, "123")
    out = run(s, "456")
    assert "type" in out[0].text.lower()


# ----------------------------------------------------------------------------- read-back / correction
def test_no_at_confirm_goes_back_to_ask():
    s = new()
    fill_until(s, "phone")
    run(s, "9876543210", "nahi")
    assert s.state == ASK and "phone" not in s.values


def test_spoken_digit_correction_at_confirm():
    s = new()
    fill_until(s, "phone")
    run(s, "9876543210")
    run(s, "5 nahi 6")
    assert s.state == CONFIRM and s.pending == "9876643210"
    run(s, "haan")
    assert s.values["phone"] == "9876643210"


def test_positional_correction_last_digit():
    s = new()
    fill_until(s, "phone")
    run(s, "9876543210", "last digit 7")
    assert s.pending == "9876543217"


def test_new_full_answer_instead_of_no():
    s = new()
    fill_until(s, "phone")
    run(s, "9876543210", "nahi 9123456789")
    assert s.state == CONFIRM and s.pending == "9123456789"


def test_unclear_confirm_asks_again():
    s = new("en")
    fill_until(s, "phone")
    out = run(s, "9876543210", "hmm banana")
    assert s.state == CONFIRM and out[0].kind == "error"


def test_readback_is_spoken_in_words_and_slow():
    s = new("en")
    fill_until(s, "phone")
    out = run(s, "9876543210")
    m = out[0]
    assert not any(ch.isdigit() for ch in m.speech)      # Timbre needs numbers as words
    assert m.speed == 0.9 and not m.cacheable            # personal data is never cached on disk


# ----------------------------------------------------------------------------- navigation
def test_repeat_back_restart():
    s = new()
    fill_until(s, "phone")
    first = run(s, "repeat")
    assert first[0].text == "अपना दस अंकों का मोबाइल नंबर बोलिए।"     # the phone question, repeated verbatim
    assert s.state == ASK and s.field["id"] == "phone"
    run(s, "go back")
    assert s.field["id"] == "dob" and "dob" not in s.values
    run(s, "start over")
    assert s.idx == 0 and not s.values


def test_empty_transcript_asks_again():
    s = new()
    out = s.handle("")
    assert out[0].kind == "error" and s.state == ASK


# ----------------------------------------------------------------------------- review step
def test_change_one_field_from_review():
    s = new()
    fill_until(s, "__end__")
    run(s, "change my phone number")
    assert s.state == ASK and s.field["id"] == "phone"
    run(s, "9123456789", "haan")
    assert s.state == REVIEW and s.values["phone"] == "9123456789"


def test_review_no_asks_which():
    s = new("en")
    fill_until(s, "__end__")
    out = run(s, "no")
    assert s.state == REVIEW and "Which" in out[0].text


def test_done_state_is_sticky():
    s = new()
    fill_until(s, "__end__")
    run(s, "submit")
    assert s.state == DONE
    run(s, "haan")
    assert s.state == DONE


# ----------------------------------------------------------------------------- snapshot (what the UI draws)
def test_snapshot_masks_aadhaar_and_counts():
    s = new()
    fill_until(s, "pincode")
    snap = s.snapshot()
    rows = {r["id"]: r for r in snap["fields"]}
    assert rows["aadhaar"]["display"].startswith("XXXX XXXX")
    assert GOOD_AADHAAR not in str(snap)
    assert snap["done"] == 4 and snap["total"] == 8
    assert rows["pincode"]["status"] == "active"


# ----------------------------------------------------------------------------- small parsers
@pytest.mark.parametrize("said,expected", [
    ("mera naam Krishna Kumar hai", "Krishna Kumar"),
    ("my name is priya sharma", "Priya Sharma"),
    ("main Rahul Verma hoon aur Lucknow se hoon", "Rahul Verma"),
    ("मेरा नाम अमित कुमार है", "अमित कुमार"),
    ("Krishna", "Krishna"),
])
def test_names(said, expected):
    assert extract_name(said) == expected


@pytest.mark.parametrize("said", ["nahi", "haan ji", "", "12345"])
def test_names_rejected(said):
    assert extract_name(said) is None


@pytest.mark.parametrize("said,expected", [
    ("haan", "yes"), ("हाँ", "yes"), ("bilkul sahi hai", "yes"), ("yes that's correct", "yes"),
    ("nahi", "no"), ("नहीं", "no"), ("galat hai", "no"), ("haan nahi", "no"),
    ("banana", None),
])
def test_yes_no(said, expected):
    assert yes_no(said) == expected


def test_choices():
    form = F.load_form("scholarship")
    cat = next(f for f in form["fields"] if f["id"] == "category")["options"]
    course = next(f for f in form["fields"] if f["id"] == "course")["options"]
    assert parse_choice("OBC", cat) == "obc"
    assert parse_choice("o b c", cat) == "obc"
    assert parse_choice("मैं जनरल हूँ", cat) == "general"
    assert parse_choice("scheduled caste", cat) == "sc"
    assert parse_choice("something else", cat) is None
    assert parse_choice("b tech", course) == "btech"
    assert parse_choice("बी टेक", course) == "btech"
    assert parse_choice("bachelor of commerce", course) == "bcom"
