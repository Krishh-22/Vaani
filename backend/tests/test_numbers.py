from datetime import date

import pytest

from app import verhoeff
from app.numbers import amount_from_text, digits_from_text
from app.parsers import correct_digits, parse_date


@pytest.mark.parametrize("said,expected", [
    ("nau aath saat chhah paanch char teen do ek shunya", "9876543210"),
    ("नौ आठ सात छह पाँच चार तीन दो एक शून्य", "9876543210"),
    ("nine eight seven six five four three two one zero", "9876543210"),
    ("9876543210", "9876543210"),
    ("98765 43210", "9876543210"),
    ("double nine eight seven six five four three two one", "9987654321"),
    ("triple five", "555"),
    ("ninety eight seventy six", "9876"),
    ("98765 nahi 98766 43210", "9876643210"),      # whole-number restart after a correction
    ("0 1 2", "012"),                              # leading zeros survive
])
def test_digits(said, expected):
    assert digits_from_text(said) == expected


@pytest.mark.parametrize("said,expected", [
    ("do lakh pachas hazaar", 250000),
    ("2 lakh 50 hazaar", 250000),
    ("dhai lakh", 250000),
    ("saadhe teen lakh", 350000),
    ("sava lakh", 125000),
    ("2,50,000", 250000),
    ("₹ 1,20,000", 120000),
    ("one lakh twenty thousand", 120000),
    ("पचास हज़ार", 50000),
    ("do lakh nahi teen lakh", 300000),            # self-correction keeps the last
])
def test_amounts(said, expected):
    assert amount_from_text(said) == expected


def test_amount_rejects_nonsense():
    assert amount_from_text("hello there") is None


def test_verhoeff_roundtrip():
    for body in ("23456789012", "99999999999", "12345678901"):
        full = verhoeff.make_valid_aadhaar(body)
        assert verhoeff.is_valid(full)
        wrong = full[:-1] + str((int(full[-1]) + 1) % 10)
        assert not verhoeff.is_valid(wrong)


def test_verhoeff_known_vector():
    # Classic published test vector: 236 -> check digit 3
    assert verhoeff.check_digit("236") == 3
    assert verhoeff.is_valid("2363")


TODAY = date(2026, 11, 6)


@pytest.mark.parametrize("said,expected", [
    ("pandrah august do hazaar paanch", date(2005, 8, 15)),
    ("15 August 2005", date(2005, 8, 15)),
    ("fifteen august two thousand five", date(2005, 8, 15)),
    ("15 08 2005", date(2005, 8, 15)),
    ("15082005", date(2005, 8, 15)),
    ("एक जनवरी दो हज़ार तीन", date(2003, 1, 1)),
    ("3 march nineteen ninety nine", date(1999, 3, 3)),
])
def test_dates(said, expected):
    d, err = parse_date(said, TODAY)
    assert err is None and d == expected


def test_date_errors():
    assert parse_date("hello", TODAY)[1] == "unclear"
    assert parse_date("31 february 2005", TODAY)[1] == "invalid"
    assert parse_date("1 january 2030", TODAY)[1] == "invalid"       # in the future


def test_digit_corrections():
    assert correct_digits("9876543210", "5 nahi 6") == ("9876643210", None)
    assert correct_digits("9876543210", "last digit 4") == ("9876543214", None)
    assert correct_digits("9876543210", "teesra digit 1") == ("9816543210", None)
    assert correct_digits("9876543210", "9 nahi 8") == ("8876543210", None)    # 9 appears once, so it's unambiguous
    assert correct_digits("1231231231", "1 nahi 4") == (None, "ambiguous")
    assert correct_digits("9876543210", "hello") == (None, None)
