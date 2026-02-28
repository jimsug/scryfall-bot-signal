"""
Parser for the [[Card Name]] syntax used in messages.

Supported syntax (mirroring the official Scryfall Discord/Slack bots):

  [[Card Name]]           Default: oracle text + mana cost + thumbnail image
  [[!Card Name]]          Full card image
  [[?Card Name]]          Rulings
  [[#Card Name]]          Format legalities
  [[$Card Name]]          Prices
  [[Card Name|SET]]       Specific set printing
  [[Card Name|SET|NUM]]   Specific set + collector number
"""

import re
from dataclasses import dataclass

# Matches [[...]] including any flags and pipe-separated set codes
CARD_PATTERN = re.compile(r"\[\[([^\[\]]+?)\]\]")

# Recognised prefix flags
FLAG_IMAGE    = "!"
FLAG_RULINGS  = "?"
FLAG_LEGALITY = "#"
FLAG_PRICE    = "$"


@dataclass
class CardQuery:
    raw: str              # The original text inside [[ ]]
    flag: str | None      # One of !, ?, #, $ or None
    name: str             # Card name (cleaned)
    set_code: str | None  # e.g. "WWK"
    collector_number: str | None


def parse_queries(text: str) -> list[CardQuery]:
    """
    Extract card queries from a message body.

    Supports two syntaxes:
    - [[Card Name]] inline brackets (multiple per message)
    - .Card Name as the entire message (mobile-friendly shorthand)
    """
    # Dot-prefix: entire message is a single query
    stripped = text.strip()
    if stripped.startswith(".") and len(stripped) > 1:
        return [_parse_single(stripped[1:].strip())]

    # Standard [[...]] bracket syntax
    queries = []
    for match in CARD_PATTERN.finditer(text):
        raw = match.group(1).strip()
        queries.append(_parse_single(raw))
    return queries


def _parse_single(raw: str) -> CardQuery:
    flag = None
    name_part = raw

    # Check for a leading flag character
    if raw and raw[0] in (FLAG_IMAGE, FLAG_RULINGS, FLAG_LEGALITY, FLAG_PRICE):
        flag = raw[0]
        name_part = raw[1:].strip()

    # Split off set code and optional collector number via pipe
    parts = [p.strip() for p in name_part.split("|")]
    name = parts[0]
    set_code = parts[1].upper() if len(parts) > 1 else None
    collector_number = parts[2] if len(parts) > 2 else None

    return CardQuery(
        raw=raw,
        flag=flag,
        name=name,
        set_code=set_code,
        collector_number=collector_number,
    )