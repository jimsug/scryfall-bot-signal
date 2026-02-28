"""
Formatters for Signal message output.

Signal doesn't support markdown, embeds, or emoji rendering the way Discord
does, so we format everything as clean plain text. Mana symbols are rendered
using their text equivalents (e.g. {W}, {U}, {B}, {R}, {G}).

Each formatter returns a tuple of (text: str, image_url: str | None).
The image_url is the Scryfall image to attach, or None if no image is needed.
"""

from __future__ import annotations


# ── Helpers ──────────────────────────────────────────────────────────────────

def _mana(cost: str) -> str:
    """Return mana cost as-is (already in {X} notation from Scryfall)."""
    return cost or ""


def _type_and_pt(card: dict) -> str:
    """Return type line, plus P/T or loyalty if applicable."""
    line = card.get("type_line", "")
    if "power" in card and "toughness" in card:
        line += f" ({card['power']}/{card['toughness']})"
    elif "loyalty" in card:
        line += f" [Loyalty: {card['loyalty']}]"
    elif "defense" in card:
        line += f" [Defense: {card['defense']}]"
    return line


def _oracle(card: dict) -> str:
    """
    Return oracle text. For double-faced cards, join both faces with //.
    """
    if "card_faces" in card:
        faces = card["card_faces"]
        parts = []
        for face in faces:
            face_text = face.get("oracle_text", "").strip()
            if face_text:
                parts.append(f"[{face['name']}]\n{face_text}")
        return "\n//\n".join(parts)
    return card.get("oracle_text", "").strip()


def _image_url(card: dict, size: str = "small") -> str | None:
    """
    Return an image URL for the card. Falls back to the first face for DFCs.
    size can be: small, normal, large, png, art_crop, border_crop
    """
    images = card.get("image_uris")
    if not images and "card_faces" in card:
        images = card["card_faces"][0].get("image_uris")
    if images:
        return images.get(size)
    return None


def _scryfall_url(card: dict) -> str:
    return card.get("scryfall_uri", "")


# ── Per-flag formatters ───────────────────────────────────────────────────────

def format_default(card: dict) -> tuple[str, str | None]:
    """
    Default response: name, mana cost, type, oracle text, set info, and
    a link to Scryfall. Returns a thumbnail image.
    """
    name = card.get("name", "Unknown")
    mana = _mana(card.get("mana_cost", ""))
    header = f"{name} {mana}".strip()
    type_line = _type_and_pt(card)
    oracle = _oracle(card)
    set_name = card.get("set_name", "")
    set_code = card.get("set", "").upper()
    rarity = card.get("rarity", "").capitalize()

    lines = [
        header,
        type_line,
        "",
        oracle,
        "",
        f"{set_name} ({set_code}) - {rarity}",
        _scryfall_url(card),
    ]
    text = "\n".join(line for line in lines if line is not None)
    return text, _image_url(card, size="small")


def format_image(card: dict) -> tuple[str, str | None]:
    """Return just the card name and a full-size image."""
    name = card.get("name", "Unknown")
    return name, _image_url(card, size="normal")


def format_rulings(card: dict, rulings: list[dict]) -> tuple[str, str | None]:
    """Format Oracle rulings for a card."""
    name = card.get("name", "Unknown")
    if not rulings:
        return f"{name}\nNo rulings available.", None

    lines = [f"Rulings for {name}:", ""]
    for ruling in rulings:
        date = ruling.get("published_at", "")
        comment = ruling.get("comment", "").strip()
        lines.append(f"[{date}] {comment}")
        lines.append("")

    return "\n".join(lines).strip(), None


def format_legality(card: dict) -> tuple[str, str | None]:
    """Format a legality table for a card."""
    name = card.get("name", "Unknown")
    legalities: dict = card.get("legalities", {})

    if not legalities:
        return f"{name}\nNo legality data available.", None

    # Group by legal/not_legal/restricted/banned for readability
    groups: dict[str, list[str]] = {
        "Legal": [],
        "Restricted": [],
        "Banned": [],
        "Not legal": [],
    }
    label_map = {
        "legal": "Legal",
        "restricted": "Restricted",
        "banned": "Banned",
        "not_legal": "Not legal",
    }
    for fmt, status in legalities.items():
        group = label_map.get(status, status)
        if group in groups:
            groups[group].append(fmt.replace("_", " ").title())

    lines = [f"Legality: {name}", ""]
    for group, formats in groups.items():
        if formats:
            lines.append(f"{group}: {', '.join(sorted(formats))}")

    return "\n".join(lines), None


def format_price(card: dict) -> tuple[str, str | None]:
    """Format price data for a card."""
    name = card.get("name", "Unknown")
    prices: dict = card.get("prices", {})
    set_name = card.get("set_name", "")
    set_code = card.get("set", "").upper()

    def fmt_price(val: str | None, symbol: str) -> str:
        return f"{symbol}{val}" if val else "N/A"

    lines = [
        f"Prices: {name} ({set_name} {set_code})",
        "",
        f"USD:      {fmt_price(prices.get('usd'), '$')}",
        f"USD Foil: {fmt_price(prices.get('usd_foil'), '$')}",
        f"EUR:      {fmt_price(prices.get('eur'), '€')}",
        f"TIX:      {fmt_price(prices.get('tix'), '')}",
        "",
        _scryfall_url(card),
    ]
    return "\n".join(lines), None