"""Tests for image downloads in bot/command.py."""

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from bot.command import MTGCommand
from bot.scryfall import USER_AGENT

BOT_PHONE = "+61400000000"


@pytest.mark.asyncio
async def test_image_download_sends_scryfall_headers():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=b"img")

    real_client = httpx.AsyncClient

    def client_factory(**kwargs):
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    cmd = MTGCommand(bot_phone=BOT_PHONE)
    ctx = MagicMock()
    ctx.send = AsyncMock()

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("bot.command.httpx.AsyncClient", client_factory)
        await cmd._send_with_images(ctx, "text", ["https://cards.scryfall.io/a.jpg"])

    assert len(seen) == 1
    assert seen[0].headers["User-Agent"] == USER_AGENT
    assert seen[0].headers["Accept"] == "image/*"
    assert ctx.send.await_args.kwargs["base64_attachments"]
