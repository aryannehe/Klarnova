"""Shared pytest fixtures — hermetic SQLite-backed session + app overrides."""

from __future__ import annotations

import os

os.environ["WEBHOOK_TOKEN"] = "test-token"
os.environ["MONITORING_ENABLED"] = "false"

import pytest
import pytest_asyncio
from app.api.router import api_router
from app.core.database import Base, get_db
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def session(session_factory):
    async with session_factory() as s:
        yield s


@pytest.fixture
def client(session_factory):
    async def override_get_db():
        async with session_factory() as s:
            yield s

    app.dependency_overrides[get_db] = override_get_db
    app.include_router(api_router)
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
