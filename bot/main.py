"""
Entry point for the MTG Signal bot.

Reads configuration from environment variables and starts the signalbot
event loop. The bot connects to signal-cli-rest-api running in a sibling
Docker container (or locally for dev).

Required environment variables:
    SIGNAL_SERVICE    - URL of signal-cli-rest-api, e.g. localhost:8080
    BOT_PHONE_NUMBER  - E.164 phone number the bot is registered under,
                        e.g. +61400000000

Optional:
    LOG_LEVEL           - Python log level, default INFO
    OWNER_PHONE_NUMBER  - Owner's phone for admin TOTP and alerts
    ADMIN_PORT          - Port for admin web panel, default 8081
    ADMIN_SECRET_KEY    - Secret key for session signing
"""

import asyncio
import logging
import os

import uvicorn
from dotenv import load_dotenv
from signalbot import SignalBot, Config

from bot.command import MTGCommand
from db.cache import init_db, purge_expired
from db.usage import init_tables as init_usage_tables
from bot.scryfall import close as close_scryfall
from admin.app import create_app

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


async def _serve_admin(app, port: int) -> None:
    """Run the admin FastAPI app on uvicorn."""
    config = uvicorn.Config(app, host="0.0.0.0", port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()


def main() -> None:
    signal_service = os.environ["SIGNAL_SERVICE"]
    phone_number = os.environ["BOT_PHONE_NUMBER"]
    owner_phone = os.environ.get("OWNER_PHONE_NUMBER", "")
    admin_port = int(os.environ.get("ADMIN_PORT", "8081"))

    logger.info("Initialising database...")
    loop = asyncio.get_event_loop()
    loop.run_until_complete(init_db())
    loop.run_until_complete(init_usage_tables())

    logger.info("Starting MTG Signal Bot on %s", phone_number)

    bot = SignalBot(
        Config(
            signal_service=signal_service,
            phone_number=phone_number,
        )
    )

    # Create a signal_sender closure that uses the bot's signal client
    async def signal_sender(phone: str, message: str) -> None:
        await bot._signal.send(phone, message)

    bot.register(MTGCommand(signal_sender=signal_sender, owner_phone=owner_phone))

    # Schedule cache purge on the bot's event loop
    bot._event_loop.create_task(_periodic_cache_purge())

    # Start admin web panel
    if owner_phone:
        admin_app = create_app(signal_sender)
        bot._event_loop.create_task(_serve_admin(admin_app, admin_port))
        logger.info("Admin panel starting on port %d", admin_port)
    else:
        logger.info("OWNER_PHONE_NUMBER not set, admin panel disabled")

    try:
        bot.start()
    finally:
        bot._event_loop.run_until_complete(close_scryfall())


if __name__ == "__main__":
    main()
