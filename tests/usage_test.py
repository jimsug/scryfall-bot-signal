"""Tests for db/usage.py"""

import time
import pytest
import pytest_asyncio
import aiosqlite

from db.cache import DB_PATH
from db.usage import (
    init_tables,
    log_usage,
    is_banned,
    ban_user,
    unban_user,
    get_banned_users,
    get_user_lookup_count,
    get_suspicious_users,
    get_usage_log,
)


@pytest_asyncio.fixture(autouse=True)
async def setup_db(tmp_path, monkeypatch):
    """Use a temporary DB for each test."""
    test_db = tmp_path / "test.db"
    monkeypatch.setattr("db.cache.DB_PATH", test_db)
    monkeypatch.setattr("db.usage.DB_PATH", test_db)

    # Create the card_cache table (usage module shares the same DB)
    async with aiosqlite.connect(test_db) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS card_cache (
                cache_key TEXT PRIMARY KEY,
                data TEXT NOT NULL,
                cached_at INTEGER NOT NULL
            )
        """)
        await db.commit()

    await init_tables()
    yield


@pytest.mark.asyncio
async def test_log_and_count():
    await log_usage("uuid-1", "+61400000000", "Lightning Bolt")
    await log_usage("uuid-1", "+61400000000", "Grizzly Bears")
    count = await get_user_lookup_count("uuid-1")
    assert count == 2


@pytest.mark.asyncio
async def test_ban_and_unban():
    assert await is_banned("uuid-1") is False
    await ban_user("uuid-1", "testing")
    assert await is_banned("uuid-1") is True

    bans = await get_banned_users()
    assert len(bans) == 1
    assert bans[0]["user_uuid"] == "uuid-1"
    assert bans[0]["reason"] == "testing"

    await unban_user("uuid-1")
    assert await is_banned("uuid-1") is False


@pytest.mark.asyncio
async def test_suspicious_users():
    # Log 20 lookups for one user (should trigger), 5 for another (should not)
    for i in range(20):
        await log_usage("uuid-heavy", None, f"card-{i}")
    for i in range(5):
        await log_usage("uuid-light", None, f"card-{i}")

    suspicious = await get_suspicious_users(threshold=20, window_seconds=300)
    assert len(suspicious) == 1
    assert suspicious[0]["user_uuid"] == "uuid-heavy"
    assert suspicious[0]["lookup_count"] == 20


@pytest.mark.asyncio
async def test_usage_log_pagination():
    for i in range(75):
        await log_usage("uuid-1", None, f"card-{i}")

    rows, total = await get_usage_log(page=1, per_page=50)
    assert total == 75
    assert len(rows) == 50

    rows, total = await get_usage_log(page=2, per_page=50)
    assert len(rows) == 25


@pytest.mark.asyncio
async def test_usage_log_filter_by_uuid():
    await log_usage("uuid-1", None, "card-a")
    await log_usage("uuid-2", None, "card-b")

    rows, total = await get_usage_log(user_uuid="uuid-1")
    assert total == 1
    assert rows[0]["user_uuid"] == "uuid-1"
