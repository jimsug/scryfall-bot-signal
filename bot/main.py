"""
Entry point for the MTG Signal bot.

Reads configuration from environment variables and starts the signalbot
event loop. The bot connects to signal-cli-rest-api running in a sibling
Docker container (or locally for dev).

Required environment variables:
    SIGNAL_SERVICE    - URL of signal-cli-rest-api, e.g. http://localhost:8080
    BOT_PHONE_NUMBER  - E.164 phone number the bot is registered under,
                        e.g. +61400000000

Optional:
    LOG_LEVEL         - Python log level, default INFO
"""

import asyncio
import logging
import os

from dotenv import load_dotenv
from signalbot import SignalBot, Config

from bot.command import MTGCommand
from db.cache import init_db, purge_expired
from bot.scryfall import close as close_scryfall

load_dotenv()

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


async def _periodic_cache_purge(interval_seconds: int = 3600) -> None:
    """Run cache purge once per hour."""
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            await purge_expired()
        except Exception:
            logger.exception("Cache purge failed")


def main() -> None:
    signal_service = os.environ["SIGNAL_SERVICE"]
    phone_number = os.environ["BOT_PHONE_NUMBER"]

    logger.info("Initialising database...")
    asyncio.get_event_loop().run_until_complete(init_db())

    logger.info("Starting MTG Signal Bot on %s", phone_number)

    bot = SignalBot(
        Config(
            signal_service=signal_service,
            phone_number=phone_number,
        )
    )
    bot.register(MTGCommand())

    # Schedule cache purge on the bot's event loop
    bot._event_loop.create_task(_periodic_cache_purge())

    try:
        bot.start()
    finally:
        bot._event_loop.run_until_complete(close_scryfall())


if __name__ == "__main__":
    main()