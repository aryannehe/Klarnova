"""Alertmanager webhook receiver (KLR-C4) — token-protected.

POST /api/v1/webhooks/alertmanager
Header: X-Klarnova-Token: <shared token>
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.dependencies import require_webhook_token
from app.schemas.incident import AlertmanagerPayload, AlertStatus, IncidentRead
from app.services.ingestion import ingest_alert

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/alertmanager",
    response_model=list[IncidentRead],
    dependencies=[Depends(require_webhook_token)],
)
async def alertmanager_webhook(
    payload: AlertmanagerPayload,
    session: AsyncSession = Depends(get_db),
) -> list[IncidentRead]:
    created: list[IncidentRead] = []
    for alert in payload.alerts:
        if alert.status != AlertStatus.FIRING:
            continue
        incident = await ingest_alert(session, alert)
        created.append(incident)
    return created
