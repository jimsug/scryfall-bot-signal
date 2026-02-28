"""Tests for bot/formatter.py"""
import pytest
from bot.formatter import (
    format_default,
    format_image,
    format_rulings,
    format_legality,
    format_price,
)

MOCK_CARD = {
    "name": "Lightning Bolt",
    "mana_cost": "{R}",
    "type_line": "Instant",
    "oracle_text": "Lightning Bolt deals 3 damage to any target.",
    "set": "lea",
    "set_name": "Limited Edition Alpha",
    "rarity": "common",
    "scryfall_uri": "https://scryfall.com/card/lea/161",
    "id": "e3285e6b-3e79-4d7c-bf96-d920f973b122",
    "image_uris": {
        "small": "https://cards.scryfall.io/small/front/e/3/e3285e6b.jpg",
        "normal": "https://cards.scryfall.io/normal/front/e/3/e3285e6b.jpg",
    },
    "legalities": {
        "standard": "not_legal",
        "modern": "legal",
        "legacy": "legal",
        "vintage": "legal",
        "commander": "legal",
        "pauper": "legal",
    },
    "prices": {
        "usd": "1499.99",
        "usd_foil": None,
        "eur": "1200.00",
        "tix": None,
    },
}

MOCK_RULINGS = [
    {
        "published_at": "2004-10-04",
        "comment": "Lightning Bolt can target a player or any creature.",
    }
]


def test_format_default_contains_name():
    text, image_url = format_default(MOCK_CARD)
    assert "Lightning Bolt" in text
    assert "{R}" in text
    assert "Instant" in text
    assert image_url is not None
    assert "small" in image_url


def test_format_default_contains_oracle():
    text, _ = format_default(MOCK_CARD)
    assert "3 damage to any target" in text


def test_format_image_returns_normal_image():
    text, image_url = format_image(MOCK_CARD)
    assert "Lightning Bolt" in text
    assert image_url is not None
    assert "normal" in image_url


def test_format_rulings():
    text, image_url = format_rulings(MOCK_CARD, MOCK_RULINGS)
    assert "Rulings for Lightning Bolt" in text
    assert "2004-10-04" in text
    assert image_url is None


def test_format_rulings_no_rulings():
    text, _ = format_rulings(MOCK_CARD, [])
    assert "No rulings available" in text


def test_format_legality():
    text, image_url = format_legality(MOCK_CARD)
    assert "Legality: Lightning Bolt" in text
    assert "Legal" in text
    assert "Not legal" in text
    assert image_url is None


def test_format_price():
    text, image_url = format_price(MOCK_CARD)
    assert "Prices: Lightning Bolt" in text
    assert "$1499.99" in text
    assert "\u20ac1200.00" in text
    assert "N/A" in text  # usd_foil is None
    assert image_url is None


def test_format_dfc():
    """Double-faced cards should show text from both faces."""
    dfc = {
        "name": "Delver of Secrets // Insectile Aberration",
        "mana_cost": "",
        "type_line": "Creature // Creature",
        "card_faces": [
            {
                "name": "Delver of Secrets",
                "oracle_text": "At the beginning of your upkeep, look at the top card of your library.",
                "image_uris": {
                    "small": "https://cards.scryfall.io/small/front/d/d/dd.jpg",
                    "normal": "https://cards.scryfall.io/normal/front/d/d/dd.jpg",
                },
            },
            {
                "name": "Insectile Aberration",
                "oracle_text": "Flying",
                "image_uris": {},
            },
        ],
        "set": "isd",
        "set_name": "Innistrad",
        "rarity": "common",
        "scryfall_uri": "https://scryfall.com/card/isd/51",
        "id": "abc123",
    }
    text, image_url = format_default(dfc)
    assert "Delver of Secrets" in text
    assert "Insectile Aberration" in text
    assert "//" in text
    assert image_url is not None