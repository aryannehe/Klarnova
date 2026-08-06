"""Health endpoints — liveness + readiness (api-reference §3.1)."""

from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy import text

from app.core.database import get_session_factory

router = APIRouter()


@router.get("")
async def liveness() -> dict:
    return {"status": "ok", "service": "klarnova-backend"}


@router.get("/ready")
async def readiness() -> dict:
    checks = {"database": False}
    try:
        async with get_session_factory()() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:
        checks["database"] = False
    ready = all(checks.values())
    return {"status": "ok" if ready else "degraded", "checks": checks}
