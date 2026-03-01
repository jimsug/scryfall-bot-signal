"""Tests for reaction-based message deletion in bot/command.py."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bot.command import MTGCommand, DELETE_EMOJIS

BOT_PHONE = "+61400000000"


def _make_context(emoji: str, target_author: str, target_timestamp: int,
                  is_remove: bool = False) -> MagicMock:
    """Build a mock Context whose message looks like a Signal reaction."""
    raw = {
        "envelope": {
            "dataMessage": {
                "reaction": {
                    "emoji": emoji,
                    "targetAuthor": target_author,
                    "targetSentTimestamp": target_timestamp,
                    "isRemove": is_remove,
                },
            },
        },
    }
    message = MagicMock()
    message.reaction = emoji
    message.raw_message = json.dumps(raw)
    message.source_uuid = "user-uuid-123"

    ctx = MagicMock()
    ctx.message = message
    ctx.remote_delete = AsyncMock()
    ctx.send = AsyncMock()
    return ctx


@pytest.mark.asyncio
async def test_trash_emoji_deletes_bot_message():
    cmd = MTGCommand(bot_phone=BOT_PHONE)
    ctx = _make_context("\U0001f5d1\ufe0f", BOT_PHONE, 1700000000000)

    await cmd._handle_reaction(ctx)

    ctx.remote_delete.assert_awaited_once_with(1700000000000)


@pytest.mark.asyncio
async def test_x_emoji_deletes_bot_message():
    cmd = MTGCommand(bot_phone=BOT_PHONE)
    ctx = _make_context("\u274c", BOT_PHONE, 1700000000000)

    await cmd._handle_reaction(ctx)

    ctx.remote_delete.assert_awaited_once_with(1700000000000)


@pytest.mark.asyncio
async def test_reaction_on_other_user_message_ignored():
    cmd = MTGCommand(bot_phone=BOT_PHONE)
    ctx = _make_context("\U0001f5d1\ufe0f", "+61499999999", 1700000000000)

    await cmd._handle_reaction(ctx)

    ctx.remote_delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_reaction_removal_ignored():
    cmd = MTGCommand(bot_phone=BOT_PHONE)
    ctx = _make_context("\U0001f5d1\ufe0f", BOT_PHONE, 1700000000000,
                        is_remove=True)

    await cmd._handle_reaction(ctx)

    ctx.remote_delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_unrelated_emoji_ignored():
    cmd = MTGCommand(bot_phone=BOT_PHONE)
    ctx = _make_context("\U0001f44d", BOT_PHONE, 1700000000000)  # 👍

    await cmd._handle_reaction(ctx)

    ctx.remote_delete.assert_not_awaited()


@pytest.mark.asyncio
async def test_handle_dispatches_reaction():
    """Verify that handle() routes to _handle_reaction for reaction messages."""
    cmd = MTGCommand(bot_phone=BOT_PHONE)
    ctx = _make_context("\U0001f5d1\ufe0f", BOT_PHONE, 1700000000000)

    await cmd.handle(ctx)

    ctx.remote_delete.assert_awaited_once_with(1700000000000)
    # Should not attempt to send a card lookup response
    ctx.send.assert_not_awaited()
