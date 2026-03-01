"""
FastAPI application factory for the admin panel.
"""

import os

from fastapi import FastAPI
from admin.auth import SignalSender
from admin.routes import create_router


def create_app(signal_sender: SignalSender) -> FastAPI:
    base_path = os.environ.get("ADMIN_BASE_PATH", "").rstrip("/")
    app = FastAPI(
        title="MTG Signal Bot Admin",
        docs_url=None,
        redoc_url=None,
        root_path=base_path,
    )
    router = create_router(signal_sender)
    app.include_router(router)
    return app
