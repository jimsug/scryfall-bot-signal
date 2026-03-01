"""
Admin panel routes.

All routes except /login and /verify require authentication via the
session cookie set during TOTP login.
"""

import os
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Request, Form, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from admin.auth import (
    request_code,
    verify_code,
    create_session_token,
    validate_session,
    require_auth,
    SESSION_COOKIE,
    SignalSender,
)
from db.usage import (
    get_suspicious_users,
    get_usage_log,
    get_banned_users,
    ban_user,
    unban_user,
    get_total_lookups_today,
)
from db.cache import search_cache, purge_key, purge_all, get_cache_stats

logger = logging.getLogger(__name__)

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


def _timestamp_fmt(ts: int) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


templates.env.filters["timestamp_fmt"] = _timestamp_fmt


def create_router(signal_sender: SignalSender) -> APIRouter:
    router = APIRouter()
    owner_phone = os.environ.get("OWNER_PHONE_NUMBER", "")

    # ── Auth routes ─────────────────────────────────────────────────────

    @router.get("/login", response_class=HTMLResponse)
    async def login_page(request: Request):
        return templates.TemplateResponse("login.html", {"request": request})

    @router.post("/login")
    async def login_submit(request: Request, phone: str = Form(...)):
        await request_code(phone, owner_phone, signal_sender)
        return templates.TemplateResponse("verify.html", {
            "request": request,
            "message": "A code has been sent if that number is registered.",
        })

    @router.get("/verify", response_class=HTMLResponse)
    async def verify_page(request: Request):
        return templates.TemplateResponse("verify.html", {"request": request, "message": None})

    @router.post("/verify")
    async def verify_submit(request: Request, code: str = Form(...)):
        if verify_code(code.strip()):
            token = create_session_token()
            response = RedirectResponse(url="/", status_code=303)
            response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="strict")
            return response
        return templates.TemplateResponse("verify.html", {
            "request": request,
            "message": "Invalid or expired code. Try again.",
        })

    @router.get("/logout")
    async def logout():
        response = RedirectResponse(url="/login", status_code=303)
        response.delete_cookie(SESSION_COOKIE)
        return response

    # ── Protected routes ────────────────────────────────────────────────

    @router.get("/", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    async def dashboard(request: Request):
        suspicious = await get_suspicious_users()
        lookups_today = await get_total_lookups_today()
        cache_stats = await get_cache_stats()
        return templates.TemplateResponse("dashboard.html", {
            "request": request,
            "suspicious": suspicious,
            "lookups_today": lookups_today,
            "cache_stats": cache_stats,
        })

    @router.get("/usage", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    async def usage_page(request: Request, page: int = 1, user_uuid: str | None = None):
        rows, total = await get_usage_log(page=page, user_uuid=user_uuid)
        total_pages = max(1, (total + 49) // 50)
        return templates.TemplateResponse("usage.html", {
            "request": request,
            "rows": rows,
            "page": page,
            "total_pages": total_pages,
            "total": total,
            "user_uuid": user_uuid or "",
        })

    @router.get("/bans", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    async def bans_page(request: Request):
        bans = await get_banned_users()
        return templates.TemplateResponse("bans.html", {
            "request": request,
            "bans": bans,
        })

    @router.post("/bans", dependencies=[Depends(require_auth)])
    async def ban_submit(user_uuid: str = Form(...), reason: str = Form("")):
        await ban_user(user_uuid.strip(), reason.strip() or None)
        return RedirectResponse(url="/bans", status_code=303)

    @router.post("/bans/{user_uuid}/unban", dependencies=[Depends(require_auth)])
    async def unban_submit(user_uuid: str):
        await unban_user(user_uuid)
        return RedirectResponse(url="/bans", status_code=303)

    @router.get("/cache", response_class=HTMLResponse, dependencies=[Depends(require_auth)])
    async def cache_page(request: Request, q: str = ""):
        entries = await search_cache(q) if q else []
        stats = await get_cache_stats()
        return templates.TemplateResponse("cache.html", {
            "request": request,
            "entries": entries,
            "query": q,
            "stats": stats,
        })

    @router.post("/cache/purge", dependencies=[Depends(require_auth)])
    async def cache_purge(key: str = Form(...)):
        await purge_key(key.strip())
        return RedirectResponse(url="/cache", status_code=303)

    @router.post("/cache/purge-all", dependencies=[Depends(require_auth)])
    async def cache_purge_all():
        await purge_all()
        return RedirectResponse(url="/cache", status_code=303)

    return router
