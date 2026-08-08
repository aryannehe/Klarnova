from collections import Counter
from datetime import date, timedelta

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


@router.get("/stats")
async def incident_stats(
    db=Depends(get_db),
    _=Depends(require_roles("admin", "engineer", "viewer")),
):
    """Aggregate dashboard metrics: status/severity distribution, MTTD/MTTR, daily trend."""
    incidents = (await db.execute(select(Incident))).scalars().all()
    remediations = (await db.execute(select(Remediation))).scalars().all()

    by_status = Counter(i.status for i in incidents)
    by_severity = Counter(i.severity for i in incidents)

    mttd_values = [
        (i.detected_at - i.created_at).total_seconds()
        for i in incidents
        if i.detected_at is not None and i.created_at is not None
    ]
    mttr_values = [r.time_to_resolve for r in remediations if r.time_to_resolve is not None]

    resolved = by_status.get("Resolved", 0)
    total = len(incidents)

    today = date.today()
    trend_days = 7
    counts = {today - timedelta(days=d): 0 for d in range(trend_days - 1, -1, -1)}
    for i in incidents:
        if i.detected_at is not None:
            counts.setdefault(i.detected_at.date(), 0)
            counts[i.detected_at.date()] += 1

    return {
        "total": total,
        "resolved": resolved,
        "escalated": by_status.get("Escalated", 0),
        "open": sum(
            v for k, v in by_status.items() if k not in ("Resolved", "Escalated", "Closed")
        ),
        "resolved_rate": round(resolved / total, 3) if total else 0.0,
        "by_status": dict(sorted(by_status.items())),
        "by_severity": dict(sorted(by_severity.items())),
        "avg_mttd_seconds": round(sum(mttd_values) / len(mttd_values), 1) if mttd_values else None,
        "avg_mttr_seconds": round(sum(mttr_values) / len(mttr_values), 1) if mttr_values else None,
        "last_7_days": [{"date": str(d), "count": counts[d]} for d in counts],
    }


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

    snapshot = incident.state_snapshot or {}
    selected = snapshot.get("selected_action") or {}

    return {
        "incident": IncidentSchema.model_validate(incident),
        "requires_approval": bool(incident.requires_approval),
        "selected_action": {
            "action_type": selected.get("action_type"),
            "target_resource": selected.get("target_resource"),
            "namespace": selected.get("namespace"),
            "source": selected.get("source", "agent"),
        }
        if selected
        else None,
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
