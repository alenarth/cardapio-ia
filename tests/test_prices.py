import pytest

from menu_extractor.prices import parse_price


@pytest.mark.parametrize("text, expected", [
    ("R$ 12,90", 12.9),
    ("R$12,90", 12.9),
    ("12,90", 12.9),
    ("12.90", 12.9),
    ("R$ 1.299,00", 1299.0),
    ("1,299.00", 1299.0),
    ("R$ 1.500", 1500.0),
    ("R$ 35", 35.0),
    ("Grande: R$ 58,00", 58.0),
    ("12,90.", 12.9),
])
def test_parses_brazilian_formats(text, expected):
    assert parse_price(text) == expected


@pytest.mark.parametrize("text", [None, "", "Consulte", "R$ --"])
def test_returns_none_without_number(text):
    assert parse_price(text) is None
