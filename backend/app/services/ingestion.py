"""Ingestion service — dedup + persist incident records (KLR-C4/C5)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.graph import run_detection
from app.agents.state import AgentState, IncidentSchema
from app.models.incident import Incident
from app.schemas.incident import (
    AlertmanagerWebhook,
    IncidentCreate,
    IncidentRead,
    IncidentStatus,
    Priority,
    Severity,
)
from app.services.classification import (
    affected_resource_from_labels,
    fingerprint_alert,
)


async def find_open_by_fingerprint(session: AsyncSession, fingerprint: str) -> Incident | None:
    result = await session.execute(
        select(Incident).where(
            Incident.alert_fingerprint == fingerprint,
            Incident.status.not_in([IncidentStatus.RESOLVED.value, IncidentStatus.CLOSED.value]),
        )
    )
    return result.scalars().first()


async def ingest_alert(session: AsyncSession, alert: AlertmanagerWebhook) -> IncidentRead:
    """Turn a webhook alert into an incident record (upsert semantics on fingerprint)."""
    fingerprint = fingerprint_alert(alert)

    existing = await find_open_by_fingerprint(session, fingerprint)
    if existing is not None:
        existing.evidence = alert.annotations
        existing.summary = alert.annotations.get("summary") or alert.annotations.get("description")
        await session.commit()
        await session.refresh(existing)
        return IncidentRead.model_validate(existing)

    # Route through the detection graph (KLR-C7) rather than calling the
    # classifier directly, so the graph is the real orchestration entry point.
    detected = run_detection(
        AgentState(
            incident=IncidentSchema(
                alert_fingerprint=fingerprint,
                alert_name=alert.labels.get("alertname"),
                source="alertmanager",
                severity=Severity.SEV_4,
                priority=Priority.P4,
                affected_resource=affected_resource_from_labels(alert.labels),
                summary=alert.annotations.get("summary") or alert.annotations.get("description"),
                evidence=alert.annotations,
                labels=alert.labels,
                started_at=alert.startsAt,
            )
        )
    )
    severity, priority = detected.incident.severity, detected.incident.priority
    incident = Incident(
        alert_fingerprint=fingerprint,
        alert_name=alert.labels.get("alertname"),
        source="alertmanager",
        severity=severity.value,
        priority=priority.value,
        status=IncidentStatus.DETECTED.value,
        affected_resource=affected_resource_from_labels(alert.labels),
        summary=alert.annotations.get("summary") or alert.annotations.get("description"),
        evidence=alert.annotations,
        started_at=alert.startsAt,
    )
    session.add(incident)
    await session.commit()
    await session.refresh(incident)
    return IncidentRead.model_validate(incident)


async def persist_incident(session: AsyncSession, data: IncidentCreate) -> IncidentRead:
    """Persist an incident record directly (used by the monitoring poller path).

    Dedup: if an open incident exists for the same fingerprint, update its evidence
    and return the existing record instead of creating a duplicate.
    """
    if data.alert_fingerprint:
        existing = await find_open_by_fingerprint(session, data.alert_fingerprint)
        if existing is not None:
            if data.summary:
                existing.summary = data.summary
            if data.evidence is not None:
                existing.evidence = data.evidence
            await session.commit()
            await session.refresh(existing)
            return IncidentRead.model_validate(existing)
    incident = Incident(
        alert_fingerprint=data.alert_fingerprint,
        alert_name=data.alert_name,
        source=data.source,
        severity=data.severity.value,
        priority=data.priority.value,
        status=IncidentStatus.DETECTED.value,
        affected_resource=data.affected_resource,
        summary=data.summary,
        evidence=data.evidence,
        started_at=data.started_at,
    )
    session.add(incident)
    await session.commit()
    await session.refresh(incident)
    return IncidentRead.model_validate(incident)
