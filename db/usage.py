"""
Usage tracking and ban management.

Stores per-user lookup counts for suspicious-usage detection, and a ban list
that the bot checks before responding to queries.
"""

import time
import logging
import aiosqlite

from db.cache import DB_PATH

logger = logging.getLogger(__name__)

SUSPICIOUS_THRESHOLD = 20
SUSPICIOUS_WINDOW = 300  # 5 minutes


async def init_tables() -> None:
    """Create usage and ban tables if they don't exist."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS usage_log (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_uuid   TEXT NOT NULL,
                user_phone  TEXT,
                query       TEXT NOT NULL,
                timestamp   INTEGER NOT NULL
            )
        """)
        await db.execute("""
            CREATE INDEX IF NOT EXISTS idx_usage_user_ts
            ON usage_log (user_uuid, timestamp)
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS banned_users (
                user_uuid   TEXT PRIMARY KEY,
                banned_at   INTEGER NOT NULL,
                reason      TEXT
            )
        """)
        await db.commit()
    logger.info("Usage/ban tables initialised")


async def log_usage(user_uuid: str, user_phone: str | None, query: str) -> None:
    """Record a single card lookup."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO usage_log (user_uuid, user_phone, query, timestamp) VALUES (?, ?, ?, ?)",
            (user_uuid, user_phone, query, int(time.time())),
        )
        await db.commit()


async def is_banned(user_uuid: str) -> bool:
    """Check whether a user is banned."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM banned_users WHERE user_uuid = ?", (user_uuid,)
        ) as cursor:
            return await cursor.fetchone() is not None


async def ban_user(user_uuid: str, reason: str | None = None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR REPLACE INTO banned_users (user_uuid, banned_at, reason) VALUES (?, ?, ?)",
            (user_uuid, int(time.time()), reason),
        )
        await db.commit()
    logger.info("Banned user %s: %s", user_uuid, reason)


async def unban_user(user_uuid: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM banned_users WHERE user_uuid = ?", (user_uuid,))
        await db.commit()
    logger.info("Unbanned user %s", user_uuid)


async def get_banned_users() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT user_uuid, banned_at, reason FROM banned_users ORDER BY banned_at DESC"
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def get_user_lookup_count(user_uuid: str, window_seconds: int = SUSPICIOUS_WINDOW) -> int:
    """Count lookups by a user in the recent window."""
    cutoff = int(time.time()) - window_seconds
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM usage_log WHERE user_uuid = ? AND timestamp >= ?",
            (user_uuid, cutoff),
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0


async def get_suspicious_users(
    threshold: int = SUSPICIOUS_THRESHOLD, window_seconds: int = SUSPICIOUS_WINDOW
) -> list[dict]:
    """Return users exceeding the lookup threshold in the given window."""
    cutoff = int(time.time()) - window_seconds
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT user_uuid, MAX(user_phone) AS user_phone, COUNT(*) AS lookup_count
            FROM usage_log
            WHERE timestamp >= ?
            GROUP BY user_uuid
            HAVING COUNT(*) >= ?
            ORDER BY lookup_count DESC
            """,
            (cutoff, threshold),
        ) as cursor:
            return [dict(row) for row in await cursor.fetchall()]


async def get_usage_log(
    page: int = 1, per_page: int = 50, user_uuid: str | None = None
) -> tuple[list[dict], int]:
    """Return paginated usage log. Returns (rows, total_count)."""
    offset = (page - 1) * per_page
    where = "WHERE user_uuid = ?" if user_uuid else ""
    params: tuple = (user_uuid,) if user_uuid else ()

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            f"SELECT COUNT(*) FROM usage_log {where}", params
        ) as cursor:
            total = (await cursor.fetchone())[0]

        async with db.execute(
            f"SELECT * FROM usage_log {where} ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (*params, per_page, offset),
        ) as cursor:
            rows = [dict(row) for row in await cursor.fetchall()]

    return rows, total


async def get_total_lookups_today() -> int:
    """Count all lookups since midnight UTC."""
    import calendar
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    midnight = int(calendar.timegm(now.replace(hour=0, minute=0, second=0, microsecond=0).timetuple()))
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT COUNT(*) FROM usage_log WHERE timestamp >= ?", (midnight,)
        ) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else 0
