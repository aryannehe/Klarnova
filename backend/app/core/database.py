"""Async SQLAlchemy engine, session factory, and dependency."""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings


class Base(DeclarativeBase):
    pass


_engine = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def init_engine(database_url: str | None = None) -> None:
    """Build the engine + session factory. Idempotent; call from app lifespan."""
    global _engine, _session_factory
    if _engine is not None:
        return
    url = database_url or get_settings().database_url
    _engine = create_async_engine(url, pool_pre_ping=True, pool_size=5, max_overflow=10)
    _session_factory = async_sessionmaker(_engine, class_=AsyncSession, expire_on_commit=False)


async def close_engine() -> None:
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    if _session_factory is None:
        raise RuntimeError("Engine not initialised — call init_engine() first")
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with get_session_factory()() as session:
        yield session
