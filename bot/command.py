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
from db.usage import log_usage, is_banned
from bot.alerts import check_and_alert, SignalSender

logger = logging.getLogger(__name__)

# Scryfall asks for 100ms between requests; when handling multiple cards in
# one message we add a small additional gap between sends to be polite.
BETWEEN_CARD_DELAY = 0.15

HELP_TEXT = """\
MTG Signal Bot - Card Lookup

Bracket syntax (works in groups and DMs):
  [[Card Name]]         Oracle text + image
  [[!Card Name]]        Full card image
  [[?Card Name]]        Rulings
  [[#Card Name]]        Legalities
  [[$Card Name]]        Prices
  [[Card|SET]]          Specific set printing
  [[Card|SET|NUM]]      Set + collector number

Shorthand (entire message):
  .Card Name            Same as [[Card Name]]
  .!Card Name           Same as [[!Card Name]]

Fuzzy matching and partial names are supported."""


class MTGCommand(Command):
    """
    Responds to [[Card Name]] lookups in Signal messages.

    Flags:
        [[Card Name]]   - oracle text + mana cost + image (default)
        [[!Card Name]]  - full card image
        [[?Card Name]]  - rulings
        [[#Card Name]]  - format legalities
        [[$Card Name]]  - prices
        [[Card|SET]]    - specific set printing
        [[Card|SET|N]]  - specific set + collector number
    """

    def __init__(
        self,
        signal_sender: SignalSender | None = None,
        owner_phone: str | None = None,
    ):
        super().__init__()
        self._signal_sender = signal_sender
        self._owner_phone = owner_phone

    async def handle(self, c: Context) -> None:
        text = c.message.text
        if not text:
            return

        if text.strip().lower() == "/help":
            await c.send(HELP_TEXT)
            return

        queries = parse_queries(text)
        if not queries:
            return

        user_uuid = getattr(c.message, "source_uuid", None) or "unknown"
        user_phone = getattr(c.message, "source_number", None)

        if await is_banned(user_uuid):
            return

        for i, query in enumerate(queries):
            if i > 0:
                await asyncio.sleep(BETWEEN_CARD_DELAY)

            try:
                await self._handle_query(c, query)
                await log_usage(user_uuid, user_phone, query.raw)
                if self._signal_sender and self._owner_phone:
                    await check_and_alert(
                        user_uuid, self._signal_sender, self._owner_phone
                    )
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
            text, image_urls = format_image(card)
        elif flag == FLAG_RULINGS:
            rulings = await get_rulings(card["id"])
            text, image_urls = format_rulings(card, rulings)
        elif flag == FLAG_LEGALITY:
            text, image_urls = format_legality(card)
        elif flag == FLAG_PRICE:
            text, image_urls = format_price(card)
        else:
            text, image_urls = format_default(card)

        if image_urls:
            await self._send_with_images(c, text, image_urls)
        else:
            await c.send(text)

    async def _send_with_images(
        self, c: Context, text: str, image_urls: list[str]
    ) -> None:
        """
        Download image(s) from Scryfall and send them as attachments.

        For double-faced cards this attaches both face images.
        signal-cli-rest-api accepts base64-encoded attachments.
        """
        tmp_paths: list[str] = []
        try:
            async with httpx.AsyncClient() as client:
                for url in image_urls:
                    response = await client.get(url, timeout=15.0)
                    response.raise_for_status()
                    suffix = ".jpg" if "jpg" in url else ".png"
                    with tempfile.NamedTemporaryFile(
                        suffix=suffix, delete=False, dir="/tmp"
                    ) as f:
                        f.write(response.content)
                        tmp_paths.append(f.name)

            attachments = [_file_to_base64(p) for p in tmp_paths]
            await c.send(text, base64_attachments=attachments)

        except Exception as e:
            logger.warning("Failed to fetch/send images %s: %s", image_urls, e)
            await c.send(text)
        finally:
            for p in tmp_paths:
                Path(p).unlink(missing_ok=True)


def _file_to_base64(path: str) -> str:
    import base64
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()