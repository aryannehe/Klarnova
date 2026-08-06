"""Klarnova backend entrypoint (KLR-A5)."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.config import get_settings
from app.core.database import close_engine, init_engine
from app.core.logging import setup_logging
from app.services.poller import MonitoringPoller

logger = logging.getLogger("klarnova")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    init_engine()
    poller = MonitoringPoller(settings)
    await poller.start()
    logger.info("Klarnova backend started (env=%s)", settings.env)
    yield
    await poller.stop()
    await close_engine()


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging(settings.log_level)
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    return app


app = create_app()
