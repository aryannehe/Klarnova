import asyncio

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.agents.graph import build_remediation_graph
from app.api.webhooks import MAX_RETRIES, _persist_results
from app.core.database import SessionLocal
from app.core.rbac import require_roles
from app.models.domain import AuditLog, Incident

router = APIRouter()
remediation_graph = build_remediation_graph()


class ApprovalRequest(BaseModel):
    incident_id: str
    action_type: str
    approved: bool
    target_resource: str | None = None
    namespace: str | None = None


@router.post("/approve")
async def approve_action(
    request: ApprovalRequest,
    current_user: dict = Depends(require_roles("admin", "engineer")),
):
    try:
        incident_id = int(request.incident_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid incident id") from None

    async with SessionLocal() as session:
        incident = await session.get(Incident, incident_id)
        if incident is None:
            raise HTTPException(status_code=404, detail="Incident not found")
        snapshot = incident.state_snapshot

    if not snapshot:
        raise HTTPException(
            status_code=409, detail="Incident has no pending approval snapshot"
        )

    if not request.approved:
        async with SessionLocal() as session:
            incident = await session.get(Incident, incident_id)
            incident.status = "Escalated"
            snapshot["approval_status"] = "rejected"
            snapshot["escalated"] = True
            incident.state_snapshot = snapshot
            session.add(
                AuditLog(
                    actor=current_user["username"],
                    action="action_rejected",
                    target=incident.resource_name,
                    details={"incident_id": incident_id, "action": request.action_type},
                )
            )
            await session.commit()
        return {"status": "success", "action": request.action_type, "approved": False}

    snapshot["approval_status"] = "approved"
    snapshot["approved_by"] = current_user["username"]
    snapshot["requires_approval"] = False
    snapshot["is_safe"] = True
    snapshot.setdefault("retry_count", 0)
    snapshot.setdefault("max_retries", MAX_RETRIES)

    # Human override: the approving engineer may select a different action or
    # retarget it (e.g. rollback the deployment instead of restarting a pod).
    if request.action_type != (snapshot.get("selected_action") or {}).get("action_type"):
        snapshot["selected_action"] = {
            "action_type": request.action_type,
            "target_resource": request.target_resource
            or snapshot.get("target_resource"),
            "namespace": request.namespace or snapshot.get("namespace"),
            "expected_reward": 0.0,
            "source": "operator",
            "parameters": {},
        }
    if request.target_resource:
        snapshot["target_resource"] = request.target_resource
    if request.namespace:
        snapshot["namespace"] = request.namespace

    final_state = await asyncio.to_thread(remediation_graph.invoke, snapshot)
    persisted = {str(m) for m in snapshot.get("messages", [])}
    final_state["messages"] = [
        m for m in final_state.get("messages", []) if str(m) not in persisted
    ]
    await _persist_results(incident_id, final_state, incident.labels or {})

    return {"status": "success", "action": request.action_type, "approved": True}
