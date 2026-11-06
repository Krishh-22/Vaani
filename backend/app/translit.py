"""Very small Devanagari -> Roman fallback, used only for the PDF (the PDF font has no Devanagari).

The preferred path is asking Prisma for format=transliterate, which returns Roman letters
directly. This only runs if a name still arrives in Devanagari.
"""
import unicodedata

_V = {"अ": "a", "आ": "a", "इ": "i", "ई": "i", "उ": "u", "ऊ": "u", "ऋ": "ri", "ए": "e", "ऐ": "ai",
      "ओ": "o", "औ": "au", "ऑ": "o", "ऍ": "e"}
_M = {"ा": "a", "ि": "i", "ी": "i", "ु": "u", "ू": "u", "ृ": "ri", "े": "e", "ै": "ai", "ो": "o",
      "ौ": "au", "ॉ": "o", "ॅ": "e"}
_C = {"क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n", "च": "ch", "छ": "chh", "ज": "j", "झ": "jh",
      "ञ": "n", "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n", "त": "t", "थ": "th", "द": "d",
      "ध": "dh", "न": "n", "प": "p", "फ": "f", "ब": "b", "भ": "bh", "म": "m", "य": "y", "र": "r",
      "ल": "l", "व": "v", "श": "sh", "ष": "sh", "स": "s", "ह": "h"}
_VIRAMA, _ANUSVARA, _CHANDRA, _VISARGA = "्", "ं", "ँ", "ः"


def has_devanagari(s: str) -> bool:
    return any("ऀ" <= ch <= "ॿ" for ch in s)


def to_roman(text: str) -> str:
    text = unicodedata.normalize("NFC", text).replace("़", "")
    out = []
    for word in text.split():
        chars, res, i = list(word), "", 0
        while i < len(chars):
            ch = chars[i]
            nxt = chars[i + 1] if i + 1 < len(chars) else ""
            if ch in _C:
                res += _C[ch]
                if nxt == _VIRAMA:
                    i += 1                      # conjunct: no vowel
                elif nxt in _M:
                    pass                        # the matra supplies the vowel
                elif i + 1 < len(chars):
                    res += "a"                  # inherent 'a' (dropped only at the end of a word)
            elif ch in _M:
                res += _M[ch]
            elif ch in _V:
                res += _V[ch]
            elif ch in (_ANUSVARA, _CHANDRA):
                res += "n"
            elif ch == _VISARGA:
                res += "h"
            elif ch == _VIRAMA:
                pass
            elif ch.isascii():
                res += ch
            i += 1
        out.append(res[:1].upper() + res[1:])
    return " ".join(out)
