"""
MTGCommand - the signalbot Command that handles card lookups.

Listens to every message (in groups and DMs) and responds whenever it
finds [[card name]] syntax. Multiple cards per message are supported.
"""

import io
import logging
import tempfile
import asyncio
from pathlib import Path

import httpx
from signalbot import Command, Context

from bot.parser import (
    parse_queries,
    FLAG_IMAGE,
    FLAG_RULINGS,
    FLAG_LEGALITY,
    FLAG_PRICE,
)
from bot.formatter import (
    format_default,
    format_image,
    format_rulings,
    format_legality,
    format_price,
)
from bot.scryfall import (
    get_card_by_name,
    get_rulings,
    ScryfallError,
)

logger = logging.getLogger(__name__)

# Scryfall asks for 100ms between requests; when handling multiple cards in
# one message we add a small additional gap between sends to be polite.
BETWEEN_CARD_DELAY = 0.15


class MTGCommand(Command):
    """
    Responds to [[Card Name]] lookups in Signal messages.

    Flags:
        [[Card Name]]   - oracle text + mana cost + thumbnail (default)
        [[!Card Name]]  - full card image
        [[?Card Name]]  - rulings
        [[#Card Name]]  - format legalities
        [[$Card Name]]  - prices
        [[Card|SET]]    - specific set printing
        [[Card|SET|N]]  - specific set + collector number
    """

    async def handle(self, c: Context) -> None:
        text = c.message.text
        if not text:
            return

        queries = parse_queries(text)
        if not queries:
            return

        for i, query in enumerate(queries):
            if i > 0:
                await asyncio.sleep(BETWEEN_CARD_DELAY)

            try:
                await self._handle_query(c, query)
            except ScryfallError as e:
                logger.warning("Scryfall error for query '%s': %s", query.raw, e)
                await c.send(f"Could not find card '{query.name}': {e.details}")
            except Exception as e:
                logger.exception("Unexpected error for query '%s'", query.raw)
                await c.send(f"Something went wrong looking up '{query.name}'.")

    async def _handle_query(self, c: Context, query) -> None:
        card = await get_card_by_name(
            name=query.name,
            set_code=query.set_code,
            collector_number=query.collector_number,
        )

        flag = query.flag

        if flag == FLAG_IMAGE:
            text, image_url = format_image(card)
        elif flag == FLAG_RULINGS:
            rulings = await get_rulings(card["id"])
            text, image_url = format_rulings(card, rulings)
        elif flag == FLAG_LEGALITY:
            text, image_url = format_legality(card)
        elif flag == FLAG_PRICE:
            text, image_url = format_price(card)
        else:
            text, image_url = format_default(card)

        if image_url:
            await self._send_with_image(c, text, image_url)
        else:
            await c.send(text)

    async def _send_with_image(
        self, c: Context, text: str, image_url: str
    ) -> None:
        """
        Download an image from Scryfall and send it as an attachment.

        signal-cli-rest-api accepts base64-encoded attachments or file paths
        depending on configuration. We write to a temp file and pass the path.
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(image_url, timeout=15.0)
                response.raise_for_status()

            suffix = ".jpg" if "jpg" in image_url else ".png"
            with tempfile.NamedTemporaryFile(
                suffix=suffix, delete=False, dir="/tmp"
            ) as f:
                f.write(response.content)
                tmp_path = f.name

            await c.send(text, base64_attachments=[_file_to_base64(tmp_path)])

            Path(tmp_path).unlink(missing_ok=True)

        except Exception as e:
            logger.warning("Failed to fetch/send image %s: %s", image_url, e)
            # Fall back to text-only
            await c.send(text)


def _file_to_base64(path: str) -> str:
    import base64
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()