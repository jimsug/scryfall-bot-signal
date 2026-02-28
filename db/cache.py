"""
SQLite cache for Scryfall card data.

Cards are cached for 24 hours (matching Scryfall's own update cadence for
gameplay data and prices).
"""

import json
import time
import logging
import aiosqlite
from pathlib import Path

logger = logging.getLogger(__name__)

DB_PATH = Path("/app/data/cache.db")
CACHE_TTL_SECONDS = 86400  # 24 hours


async def init_db() -> None:
    """Create tables if they don't already exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS card_cache (
                cache_key   TEXT PRIMARY KEY,
                data        TEXT NOT NULL,
                cached_at   INTEGER NOT NULL
            )
        """)
        await db.commit()
    logger.info("Database initialised at %s", DB_PATH)


async def get_cached(key: str) -> dict | None:
    """Return cached card data if present and not expired, else None."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT data, cached_at FROM card_cache WHERE cache_key = ?", (key,)
        ) as cursor:
            row = await cursor.fetchone()

    if row is None:
        return None

    data, cached_at = row
    if time.time() - cached_at > CACHE_TTL_SECONDS:
        logger.debug("Cache expired for key: %s", key)
        return None

    logger.debug("Cache hit for key: %s", key)
    return json.loads(data)


async def set_cached(key: str, data: dict) -> None:
    """Insert or replace a cache entry."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT OR REPLACE INTO card_cache (cache_key, data, cached_at)
            VALUES (?, ?, ?)
            """,
            (key, json.dumps(data), int(time.time())),
        )
        await db.commit()
    logger.debug("Cached data for key: %s", key)


async def purge_expired() -> int:
    """Delete all expired cache entries. Returns the number of rows deleted."""
    cutoff = int(time.time()) - CACHE_TTL_SECONDS
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM card_cache WHERE cached_at < ?", (cutoff,)
        )
        await db.commit()
        count = cursor.rowcount
    logger.info("Purged %d expired cache entries", count)
    return count