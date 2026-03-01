"""
TOTP-over-Signal authentication for the admin panel.

Flow:
1. User enters their phone number at /login
2. If it matches OWNER_PHONE_NUMBER, a 6-digit code is sent via Signal
3. User enters the code at /verify
4. A signed session cookie is set (30 min expiry)
"""

import os
import time
import secrets
import logging
from typing import Callable, Awaitable

from fastapi import Request, HTTPException
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

logger = logging.getLogger(__name__)

TOTP_EXPIRY = 300  # 5 minutes
SESSION_MAX_AGE = 1800  # 30 minutes
SESSION_COOKIE = "admin_session"

SignalSender = Callable[[str, str], Awaitable[None]]

# In-memory pending codes: {code: {"phone": str, "expires": float}}
_pending_codes: dict[str, dict] = {}


def get_serializer() -> URLSafeTimedSerializer:
    secret = os.environ.get("ADMIN_SECRET_KEY", "change-me-in-production")
    return URLSafeTimedSerializer(secret)


def generate_totp() -> str:
    """Generate a 6-digit numeric code."""
    return f"{secrets.randbelow(1000000):06d}"


async def request_code(
    phone: str,
    owner_phone: str,
    signal_sender: SignalSender,
) -> None:
    """
    Generate and send a TOTP code if the phone matches the owner.

    Always returns without error — no information leak about whether the
    phone number was correct.
    """
    if phone.strip() != owner_phone:
        logger.debug("Login attempt with non-owner phone")
        return

    code = generate_totp()
    _pending_codes[code] = {
        "phone": owner_phone,
        "expires": time.time() + TOTP_EXPIRY,
    }
    logger.info("Sending TOTP to owner")
    try:
        await signal_sender(owner_phone, f"Admin login code: {code}")
    except Exception:
        logger.exception("Failed to send TOTP via Signal")


def verify_code(code: str) -> bool:
    """Validate a TOTP code. Consumes it on success."""
    entry = _pending_codes.pop(code, None)
    if entry is None:
        return False
    if time.time() > entry["expires"]:
        return False
    return True


def create_session_token() -> str:
    """Create a signed session token."""
    s = get_serializer()
    return s.dumps({"authenticated": True})


def validate_session(token: str) -> bool:
    """Validate and check expiry of a session token."""
    s = get_serializer()
    try:
        s.loads(token, max_age=SESSION_MAX_AGE)
        return True
    except (BadSignature, SignatureExpired):
        return False


async def require_auth(request: Request) -> None:
    """FastAPI dependency that enforces authentication."""
    token = request.cookies.get(SESSION_COOKIE)
    if not token or not validate_session(token):
        base_path = os.environ.get("ADMIN_BASE_PATH", "").rstrip("/")
        raise HTTPException(status_code=303, headers={"Location": f"{base_path}/login"})


def cleanup_expired_codes() -> None:
    """Remove expired pending codes."""
    now = time.time()
    expired = [k for k, v in _pending_codes.items() if now > v["expires"]]
    for k in expired:
        _pending_codes.pop(k, None)
