"""Tests for bot/parser.py"""
import pytest
from bot.parser import parse_queries, FLAG_IMAGE, FLAG_RULINGS, FLAG_LEGALITY, FLAG_PRICE


def test_basic_lookup():
    queries = parse_queries("Check out [[Lightning Bolt]]")
    assert len(queries) == 1
    q = queries[0]
    assert q.name == "Lightning Bolt"
    assert q.flag is None
    assert q.set_code is None
    assert q.collector_number is None


def test_image_flag():
    queries = parse_queries("[[!Force of Will]]")
    assert queries[0].flag == FLAG_IMAGE
    assert queries[0].name == "Force of Will"


def test_rulings_flag():
    queries = parse_queries("[[?Past in Flames]]")
    assert queries[0].flag == FLAG_RULINGS
    assert queries[0].name == "Past in Flames"


def test_legality_flag():
    queries = parse_queries("[[#Treasure Cruise]]")
    assert queries[0].flag == FLAG_LEGALITY
    assert queries[0].name == "Treasure Cruise"


def test_price_flag():
    queries = parse_queries("[[$Tarmogoyf]]")
    assert queries[0].flag == FLAG_PRICE
    assert queries[0].name == "Tarmogoyf"


def test_set_code():
    queries = parse_queries("[[Jace|WWK]]")
    assert queries[0].name == "Jace"
    assert queries[0].set_code == "WWK"
    assert queries[0].collector_number is None


def test_set_and_collector_number():
    queries = parse_queries("[[Black Lotus|LEA|232]]")
    assert queries[0].name == "Black Lotus"
    assert queries[0].set_code == "LEA"
    assert queries[0].collector_number == "232"


def test_multiple_cards():
    queries = parse_queries("[[Lightning Bolt]] deals 3 to [[Grizzly Bears]]")
    assert len(queries) == 2
    assert queries[0].name == "Lightning Bolt"
    assert queries[1].name == "Grizzly Bears"


def test_no_matches():
    queries = parse_queries("Just a normal message with no cards")
    assert queries == []


def test_fuzzy_name_passthrough():
    """Names don't get cleaned up by the parser - fuzzy matching is Scryfall's job."""
    queries = parse_queries("[[thalia guardian]]")
    assert queries[0].name == "thalia guardian"


def test_image_flag_with_set():
    queries = parse_queries("[[!Counterspell|MMQ]]")
    assert queries[0].flag == FLAG_IMAGE
    assert queries[0].name == "Counterspell"
    assert queries[0].set_code == "MMQ"


# ── Dot-prefix shorthand tests ──────────────────────────────────────────────

def test_dot_basic():
    queries = parse_queries(".Lightning Bolt")
    assert len(queries) == 1
    assert queries[0].name == "Lightning Bolt"
    assert queries[0].flag is None


def test_dot_image_flag():
    queries = parse_queries(".!Force of Will")
    assert queries[0].flag == FLAG_IMAGE
    assert queries[0].name == "Force of Will"


def test_dot_price_flag():
    queries = parse_queries(".$Tarmogoyf")
    assert queries[0].flag == FLAG_PRICE
    assert queries[0].name == "Tarmogoyf"


def test_dot_with_set():
    queries = parse_queries(".Jace|WWK")
    assert queries[0].name == "Jace"
    assert queries[0].set_code == "WWK"


def test_dot_with_set_and_number():
    queries = parse_queries(".Black Lotus|LEA|232")
    assert queries[0].name == "Black Lotus"
    assert queries[0].set_code == "LEA"
    assert queries[0].collector_number == "232"


def test_dot_mid_sentence_ignored():
    """A dot mid-sentence should not trigger a lookup."""
    queries = parse_queries("I think Mr. Smith is right")
    assert queries == []


def test_dot_only_ignored():
    """A lone dot should not trigger a lookup."""
    queries = parse_queries(".")
    assert queries == []