"""Spanish national ids: DNI (8 digits + letter) and NIE (X/Y/Z + 7 digits + letter).

The check letter is a function of the digits, so a misheard id can be told from
a correct one — and a confirmed digit string determines its letter.
"""

import re
from dataclasses import dataclass

_LETTERS = "TRWAGMYFPDXBNJZSQVHLCKE"
_NIE_PREFIX = {"X": "0", "Y": "1", "Z": "2"}


def normalize(raw: str) -> str:
    """Uppercase and drop everything that is not a letter or digit."""
    return re.sub(r"[^0-9A-Za-z]", "", raw or "").upper()


def check_letter(digits: str) -> str:
    return _LETTERS[int(digits) % 23]


@dataclass(frozen=True)
class NationalId:
    normalized: str
    kind: str | None  # "dni", "nie" or None when the shape is wrong
    valid: bool
    expected_letter: str | None  # the letter the digits demand, when the shape allows it

    @property
    def corrected(self) -> str | None:
        """The id with the letter its digits demand."""
        if self.expected_letter is None:
            return None
        return self.normalized[:-1] + self.expected_letter


def parse(raw: str) -> NationalId:
    value = normalize(raw)
    if re.fullmatch(r"\d{8}[A-Z]", value):
        expected = check_letter(value[:8])
        return NationalId(value, "dni", value[8] == expected, expected)
    if re.fullmatch(r"[XYZ]\d{7}[A-Z]", value):
        expected = check_letter(_NIE_PREFIX[value[0]] + value[1:8])
        return NationalId(value, "nie", value[8] == expected, expected)
    # Digits heard but the letter missing: still tell the caller-facing code what it should be.
    if re.fullmatch(r"\d{8}", value):
        return NationalId(value, None, False, None)
    return NationalId(value, None, False, None)
