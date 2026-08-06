"""Incident endpoints — list + detail (api-reference §3.3)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.incident import Incident
from app.schemas.incident import IncidentRead

router = APIRouter()


@router.get("", response_model=list[IncidentRead])
async def list_incidents(
    limit: int = Query(default=50, ge=1, le=200),
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = Query(default=None),
    resource: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
) -> list[IncidentRead]:
    stmt = select(Incident)
    if status_filter:
        stmt = stmt.where(Incident.status == status_filter.upper())
    if severity:
        stmt = stmt.where(Incident.severity == severity.upper())
    if resource:
        stmt = stmt.where(Incident.affected_resource.like(f"%{resource}%"))
    stmt = stmt.order_by(Incident.started_at.desc()).limit(limit)
    result = await session.execute(stmt)
    return [IncidentRead.model_validate(i) for i in result.scalars().all()]


@router.get("/{incident_id}", response_model=IncidentRead)
async def get_incident(incident_id: str, session: AsyncSession = Depends(get_db)) -> IncidentRead:
    result = await session.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalars().first()
    if incident is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Incident not found")
    return IncidentRead.model_validate(incident)
