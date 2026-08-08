from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.core.database import get_db
from app.core.rbac import require_roles
from app.models.domain import AgentRun, Incident, Remediation
from app.schemas.incident import Incident as IncidentSchema

router = APIRouter()


@router.get("", response_model=list[IncidentSchema])
async def list_incidents(
    status: str | None = Query(None, description="Filter by status"),
    limit: int = Query(50, le=500),
    db=Depends(get_db),
    _=Depends(require_roles("admin", "engineer", "viewer")),
):
    stmt = select(Incident).order_by(Incident.detected_at.desc()).limit(limit)
    if status:
        stmt = stmt.where(Incident.status == status)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{incident_id}", response_model=IncidentSchema)
async def get_incident(
    incident_id: int,
    db=Depends(get_db),
    _=Depends(require_roles("admin", "engineer", "viewer")),
):
    incident = await db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    return incident


@router.get("/{incident_id}/trace")
async def get_incident_trace(
    incident_id: int,
    db=Depends(get_db),
    _=Depends(require_roles("admin", "engineer", "viewer")),
):
    incident = await db.get(Incident, incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    runs = (
        await db.execute(
            select(AgentRun)
            .where(AgentRun.incident_id == incident_id)
            .order_by(AgentRun.id)
        )
    ).scalars().all()

    remediations = (
        await db.execute(
            select(Remediation)
            .where(Remediation.incident_id == incident_id)
            .order_by(Remediation.id)
        )
    ).scalars().all()

    return {
        "incident": IncidentSchema.model_validate(incident),
        "agent_runs": [
            {
                "agent": r.agent_name,
                "status": r.status,
                "inputs": r.inputs,
                "outputs": r.outputs,
            }
            for r in runs
        ],
        "remediations": [
            {
                "action": r.action,
                "category": r.incident_category,
                "outcome": r.outcome,
                "time_to_resolve": r.time_to_resolve,
            }
            for r in remediations
        ],
    }
