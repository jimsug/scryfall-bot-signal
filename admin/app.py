"""
FastAPI application factory for the admin panel.
"""

from fastapi import FastAPI
from admin.auth import SignalSender
from admin.routes import create_router


def create_app(signal_sender: SignalSender) -> FastAPI:
    app = FastAPI(title="MTG Signal Bot Admin", docs_url=None, redoc_url=None)
    router = create_router(signal_sender)
    app.include_router(router)
    return app
