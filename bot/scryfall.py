"""
Scryfall API client.

Handles all communication with api.scryfall.com, sitting in front of the
SQLite cache so that repeated lookups within a 24-hour window don't hammer
the API.

Rate limiting: Scryfall asks for 50-100ms between requests (~10 req/s max).
We use httpx with a small delay between calls.
"""

import asyncio
import logging
import httpx

from db.cache import get_cached, set_cached

logger = logging.getLogger(__name__)

BASE_URL = "https://api.scryfall.com"
USER_AGENT = "MTGSignalBot/1.0 (github.com/jimsug/mtg-signal-bot)"
REQUEST_DELAY = 0.1  # 100ms between requests as per Scryfall guidelines


class ScryfallError(Exception):
    """Raised when Scryfall returns an error object."""
    def __init__(self, status: int, details: str, warnings: list[str] | None = None):
        self.status = status
        self.details = details
        self.warnings = warnings or []
        super().__init__(details)


_client: httpx.AsyncClient | None = None


def get_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        _client = httpx.AsyncClient(
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json",
            },
            timeout=10.0,
        )
    return _client


async def _get(path: str, params: dict | None = None) -> dict:
    """Raw GET against the Scryfall API with rate-limit delay."""
    await asyncio.sleep(REQUEST_DELAY)
    client = get_client()
    url = f"{BASE_URL}{path}"
    logger.debug("GET %s params=%s", url, params)
    response = await client.get(url, params=params)
    data = response.json()
    if data.get("object") == "error":
        raise ScryfallError(
            status=data.get("status", response.status_code),
            details=data.get("details", "Unknown error"),
            warnings=data.get("warnings"),
        )
    return data


async def get_card_by_name(
    name: str, set_code: str | None = None, collector_number: str | None = None
) -> dict:
    """
    Fetch a card by fuzzy name, optionally limited to a set/collector number.

    Cache key includes name + set + number so different printings cache
    independently.
    """
    cache_key = f"named:{name.lower()}:{set_code or ''}:{collector_number or ''}"
    cached = await get_cached(cache_key)
    if cached:
        return cached

    if collector_number and set_code:
        # Direct lookup by set + collector number - most precise
        data = await _get(f"/cards/{set_code.lower()}/{collector_number}")
    else:
        params: dict = {"fuzzy": name}
        if set_code:
            params["set"] = set_code.lower()
        data = await _get("/cards/named", params=params)

    await set_cached(cache_key, data)
    return data


async def get_rulings(card_id: str) -> list[dict]:
    """Fetch Oracle rulings for a card by its Scryfall UUID."""
    cache_key = f"rulings:{card_id}"
    cached = await get_cached(cache_key)
    if cached:
        return cached["data"]

    data = await _get(f"/cards/{card_id}/rulings")
    await set_cached(cache_key, data)
    return data["data"]


async def close() -> None:
    """Close the shared httpx client."""
    global _client
    if _client:
        await _client.aclose()
        _client = None