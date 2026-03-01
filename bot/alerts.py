"""
Suspicious usage alerting.

After each lookup is logged, checks whether the user has crossed the
threshold and sends a one-time Signal alert to the owner (with a 30-minute
cooldown per user to avoid spam).
"""

import time
import logging
from typing import Callable, Awaitable

from db.usage import get_user_lookup_count, SUSPICIOUS_THRESHOLD, SUSPICIOUS_WINDOW

logger = logging.getLogger(__name__)

ALERT_COOLDOWN = 1800  # 30 minutes

# {user_uuid: last_alert_timestamp}
_alert_cooldowns: dict[str, float] = {}

SignalSender = Callable[[str, str], Awaitable[None]]


async def check_and_alert(
    user_uuid: str,
    signal_sender: SignalSender,
    owner_phone: str,
) -> None:
    """Send an alert if the user just crossed the suspicious threshold."""
    now = time.time()
    last_alert = _alert_cooldowns.get(user_uuid, 0)
    if now - last_alert < ALERT_COOLDOWN:
        return

    count = await get_user_lookup_count(user_uuid)
    if count < SUSPICIOUS_THRESHOLD:
        return

    _alert_cooldowns[user_uuid] = now
    msg = (
        f"Suspicious usage alert: user {user_uuid} "
        f"has made {count} lookups in the last {SUSPICIOUS_WINDOW // 60} minutes."
    )
    logger.warning(msg)
    try:
        await signal_sender(owner_phone, msg)
    except Exception:
        logger.exception("Failed to send suspicious-usage alert")
