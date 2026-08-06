"""Incident + Alertmanager webhook schemas (frozen contract, KLR-A4).

Severity/priority follow PRD §4.3: SEV-1…4 / P1…4.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Severity(StrEnum):
    SEV_1 = "SEV-1"
    SEV_2 = "SEV-2"
    SEV_3 = "SEV-3"
    SEV_4 = "SEV-4"


class Priority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class IncidentStatus(StrEnum):
    DETECTED = "DETECTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"
    CLOSED = "CLOSED"


class AlertStatus(StrEnum):
    FIRING = "firing"
    RESOLVED = "resolved"


class IncidentCreate(BaseModel):
    alert_fingerprint: str | None = None
    alert_name: str | None = None
    source: str = "alertmanager"
    severity: Severity
    priority: Priority
    affected_resource: str
    summary: str | None = None
    evidence: dict | None = None
    started_at: datetime | None = None


class IncidentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    alert_fingerprint: str | None = None
    alert_name: str | None = None
    source: str
    severity: Severity
    priority: Priority
    status: IncidentStatus
    affected_resource: str
    summary: str | None = None
    evidence: dict | None = None
    root_cause: str | None = None
    confidence: float | None = None
    started_at: datetime
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AlertmanagerWebhook(BaseModel):
    """Per-alert entry in an Alertmanager notification (webhook v4 format)."""

    model_config = ConfigDict(extra="allow")

    status: AlertStatus = AlertStatus.FIRING
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: datetime | None = None
    endsAt: datetime | None = None
    generatorURL: str | None = None
    fingerprint: str | None = None


class AlertmanagerPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    version: str = "4"
    status: AlertStatus = AlertStatus.FIRING
    groupLabels: dict[str, str] = Field(default_factory=dict)
    commonLabels: dict[str, str] = Field(default_factory=dict)
    commonAnnotations: dict[str, str] = Field(default_factory=dict)
    alerts: list[AlertmanagerWebhook] = Field(default_factory=list)
