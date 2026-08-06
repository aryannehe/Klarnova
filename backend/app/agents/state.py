"""Frozen AgentState contract (KLR-A3).

Golden rule (agent-design §4): this schema is frozen before parallel development;
changes require a cross-team review and a migration note. Phase 1 only populates
the detection subset; later agents extend it via the documented ownership table.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from app.schemas.incident import Priority, Severity


class IncidentStatus(StrEnum):
    DETECTED = "DETECTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"


class IncidentSchema(BaseModel):
    alert_fingerprint: str | None = None
    alert_name: str | None = None
    source: str = "alertmanager"
    severity: Severity
    priority: Priority
    status: IncidentStatus = IncidentStatus.DETECTED
    affected_resource: str
    summary: str | None = None
    evidence: dict | None = None
    labels: dict[str, str] | None = None
    started_at: datetime | None = None


class AgentState(BaseModel):
    # Detection (Phase 1)
    incident_id: str | None = None
    incident: IncidentSchema | None = None
    severity: Severity | None = None
    priority: Priority | None = None

    # Phase 2+
    investigation: dict | None = None
    retrieval: list[dict] = Field(default_factory=list)
    diagnosis: dict | None = None
    candidates: list[dict] = Field(default_factory=list)
    decision: list[dict] = Field(default_factory=list)
    remediation: dict | None = None
    validation: dict | None = None
    report: dict | None = None
    audit: list[dict] = Field(default_factory=list)
    retries: int = 0
    status: IncidentStatus = IncidentStatus.DETECTED
