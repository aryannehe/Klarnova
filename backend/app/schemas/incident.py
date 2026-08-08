from datetime import datetime

from pydantic import BaseModel, Field


class IncidentBase(BaseModel):
    alert_name: str
    severity: str # SEV-1 to SEV-4
    priority: str # P1 to P4
    namespace: str
    resource_kind: str
    resource_name: str
    description: str | None = None
    labels: dict[str, str] = Field(default_factory=dict)

class IncidentCreate(IncidentBase):
    pass

class Incident(IncidentBase):
    id: int
    status: str # Open, Investigating, Awaiting Approval, Remediating, Resolved, Escalated
    created_at: datetime = Field(default_factory=datetime.utcnow)
    detected_at: datetime | None = None
    remediated_at: datetime | None = None
    root_cause: str | None = None
    confidence_score: float | None = None

    class Config:
        from_attributes = True
