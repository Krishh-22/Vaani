"""Turning values into text that a TTS voice will pronounce correctly.

Gnani's docs say: write numbers, dates and currency as spoken words. So every
value we read back goes through here first.
"""
from datetime import date

HI_0_99 = (
    "शून्य एक दो तीन चार पाँच छह सात आठ नौ "
    "दस ग्यारह बारह तेरह चौदह पंद्रह सोलह सत्रह अठारह उन्नीस "
    "बीस इक्कीस बाईस तेईस चौबीस पच्चीस छब्बीस सत्ताईस अट्ठाईस उनतीस "
    "तीस इकतीस बत्तीस तैंतीस चौंतीस पैंतीस छत्तीस सैंतीस अड़तीस उनतालीस "
    "चालीस इकतालीस बयालीस तैंतालीस चौवालीस पैंतालीस छियालीस सैंतालीस अड़तालीस उनचास "
    "पचास इक्यावन बावन तिरपन चौवन पचपन छप्पन सत्तावन अट्ठावन उनसठ "
    "साठ इकसठ बासठ तिरसठ चौंसठ पैंसठ छियासठ सड़सठ अड़सठ उनहत्तर "
    "सत्तर इकहत्तर बहत्तर तिहत्तर चौहत्तर पचहत्तर छिहत्तर सतहत्तर अठहत्तर उन्यासी "
    "अस्सी इक्यासी बयासी तिरासी चौरासी पचासी छियासी सत्तासी अट्ठासी नवासी "
    "नब्बे इक्यानवे बानवे तिरानवे चौरानवे पंचानवे छियानवे सत्तानवे अट्ठानवे निन्यानवे"
).split()
assert len(HI_0_99) == 100, len(HI_0_99)

EN_0_19 = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
EN_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()

HI_DIGIT = HI_0_99[:10]
EN_DIGIT = EN_0_19[:10]

HI_MONTHS = ["जनवरी", "फ़रवरी", "मार्च", "अप्रैल", "मई", "जून", "जुलाई", "अगस्त", "सितंबर", "अक्टूबर", "नवंबर", "दिसंबर"]
EN_MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]


def hi_words(n: int) -> str:
    """Hindi number words using the lakh/crore system, e.g. 250000 -> 'दो लाख पचास हज़ार'."""
    if n < 100:
        return HI_0_99[n]
    parts = []
    for unit, name in ((10_000_000, "करोड़"), (100_000, "लाख"), (1000, "हज़ार"), (100, "सौ")):
        q, n = divmod(n, unit)
        if q:
            parts.append(f"{hi_words(q)} {name}")
    if n:
        parts.append(HI_0_99[n])
    return " ".join(parts)


def en_words(n: int) -> str:
    """English words in the Indian system, e.g. 250000 -> 'two lakh fifty thousand'."""
    if n < 20:
        return EN_0_19[n]
    if n < 100:
        t, u = divmod(n, 10)
        return EN_TENS[t] + (f" {EN_0_19[u]}" if u else "")
    parts = []
    for unit, name in ((10_000_000, "crore"), (100_000, "lakh"), (1000, "thousand"), (100, "hundred")):
        q, n = divmod(n, unit)
        if q:
            parts.append(f"{en_words(q)} {name}")
    if n:
        parts.append(en_words(n))
    return " ".join(parts)


def words(n: int, lang: str) -> str:
    return hi_words(n) if lang == "hi" else en_words(n)


def group_digits(digits: str, sizes) -> list:
    out, i = [], 0
    for s in sizes:
        out.append(digits[i:i + s])
        i += s
    if i < len(digits):
        out.append(digits[i:])
    return [g for g in out if g]


def speak_digits(digits: str, lang: str, sizes=None) -> str:
    """'9876543210' -> 'नौ आठ सात छह पाँच, चार तीन दो एक शून्य' (commas give the voice a pause)."""
    table = HI_DIGIT if lang == "hi" else EN_DIGIT
    groups = group_digits(digits, sizes) if sizes else [digits]
    return ", ".join(" ".join(table[int(d)] for d in g) for g in groups)


def show_digits(digits: str, sizes=None) -> str:
    return " ".join(group_digits(digits, sizes)) if sizes else digits


def indian_commas(n: int) -> str:
    """250000 -> '2,50,000'"""
    s = str(n)
    if len(s) <= 3:
        return s
    head, tail = s[:-3], s[-3:]
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    if head:
        parts.insert(0, head)
    return ",".join(parts + [tail])


def show_amount(n: int) -> str:
    return f"₹{indian_commas(n)}"


def speak_amount(n: int, lang: str) -> str:
    return f"{words(n, lang)} " + ("रुपये" if lang == "hi" else "rupees")


def show_date(d: date) -> str:
    return f"{d.day} {EN_MONTHS[d.month - 1]} {d.year}"


def speak_date(d: date, lang: str) -> str:
    if lang == "hi":
        return f"{hi_words(d.day)} {HI_MONTHS[d.month - 1]} {hi_words(d.year)}"
    return f"{en_words(d.day)} {EN_MONTHS[d.month - 1]} {en_words(d.year)}"
