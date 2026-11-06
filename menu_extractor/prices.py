"""Deterministic parsing of Brazilian price strings."""

import re

_NUMBER = re.compile(r"\d[\d.,]*")


def parse_price(text: str | None) -> float | None:
    """Convert a printed price into a float.

    >>> parse_price("R$ 12,90")
    12.9
    >>> parse_price("1.299,00")
    1299.0
    >>> parse_price("Consulte")  # no number
    """
    if not text:
        return None
    match = _NUMBER.search(text.replace(" ", ""))
    if not match:
        return None
    raw = match.group().rstrip(".,")

    has_comma, has_dot = "," in raw, "." in raw
    if has_comma and has_dot:
        # The last separator is the decimal one: "1.299,90" or "1,299.90"
        decimal_sep = "," if raw.rfind(",") > raw.rfind(".") else "."
        thousands_sep = "." if decimal_sep == "," else ","
        raw = raw.replace(thousands_sep, "").replace(decimal_sep, ".")
    elif has_comma:
        raw = _single_separator(raw, ",")
    elif has_dot:
        raw = _single_separator(raw, ".")

    try:
        return round(float(raw), 2)
    except ValueError:
        return None


def _single_separator(raw: str, sep: str) -> str:
    """'12,90' -> '12.90' (decimal) but '1.500' -> '1500' (thousands)."""
    head, _, tail = raw.rpartition(sep)
    if len(tail) == 3 and raw.count(sep) >= 1 and len(head.replace(sep, "")) <= 3:
        return raw.replace(sep, "")
    return raw.replace(sep, "", raw.count(sep) - 1).replace(sep, ".")
