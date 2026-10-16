import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Request
from sqlalchemy import select

from app.agents.graph import (
    build_investigation_graph,
    build_remediation_graph,
)
from app.agents.monitoring import classify_severity
from app.bandit.learning import record_learning
from app.config import settings
from app.core.database import SessionLocal
from app.models.domain import AgentRun, AuditLog, Incident, Remediation
from app.rag.writeback import writeback_incident
from app.services.notify import notify

router = APIRouter()

investigation_graph = build_investigation_graph()
remediation_graph = build_remediation_graph()

MAX_RETRIES = 2

# Terminal statuses: incidents in any other status are considered live, and a
# repeated firing notification for the same alert/resource is deduplicated.
FINAL_STATUSES = ("Resolved", "Escalated", "Closed")

_background_tasks: set[asyncio.Task] = set()


def _log_task_error(task: asyncio.Task) -> None:
    if not task.cancelled() and task.exception() is not None:
        logging.getLogger(__name__).error(
            "alert processing failed: %s", task.exception()
        )


def _authorized(authorization) -> bool:
    token = settings.ALERTMANAGER_WEBHOOK_TOKEN
    if not token:
        return False
    return authorization in (f"Bearer {token}", token)


def _resource_from_labels(labels: dict[str, Any]):
    name = (
        labels.get("pod")
        or labels.get("deployment")
        or labels.get("node")
        or labels.get("resource_name")
        or "unknown"
    )
    kind = labels.get("kind", "pod")
    if "deployment" in labels:
        kind = "deployment"
    elif "node" in labels:
        kind = "node"
    return kind, name


def build_state(incident_id: int, alert: dict[str, Any]) -> dict[str, Any]:
    labels = alert.get("labels", {})
    severity, priority = classify_severity(labels)
    kind, resource = _resource_from_labels(labels)
    now = datetime.now(UTC).isoformat()
    return {
        "incident_id": str(incident_id),
        "incident_data": {
            "alert_name": labels.get("alertname", "unknown"),
            "labels": labels,
            "annotations": alert.get("annotations", {}),
        },
        "severity": severity,
        "priority": priority,
        "detected_at": now,
        "namespace": labels.get("namespace", "default"),
        "target_resource": resource,
        "resource_kind": kind,
        "logs": [],
        "events": [],
        "metrics": {},
        "retrieved_docs": [],
        "root_cause": None,
        "confidence_score": 0.0,
        "candidate_actions": [],
        "selected_action": None,
        "is_safe": False,
        "requires_approval": False,
        "approval_status": None,
        "remediation_result": None,
        "remediation_success": False,
        "is_resolved": False,
        "retry_count": 0,
        "max_retries": MAX_RETRIES,
        "escalated": False,
        "resolved_at": None,
        "report": None,
        "messages": [],
    }


def _agent_name(content: str) -> str:
    lowered = content.lower()
    for prefix, name in (
        ("monitoring:", "monitoring"),
        ("investigation:", "investigation"),
        ("retrieval:", "retrieval"),
        ("diagnosis", "root_cause"),
        ("planning:", "planning"),
        ("safety:", "safety"),
        ("remediation:", "remediation"),
        ("validation:", "validation"),
        ("reporting:", "reporting"),
    ):
        if lowered.startswith(prefix):
            return name
    return "graph"


async def _persist_results(incident_id: int, state: dict[str, Any], labels: dict[str, Any]):
    now = datetime.now(UTC)
    requires_approval = bool(state.get("requires_approval"))
    pending = requires_approval and state.get("approval_status") in (None, "pending", "rejected")

    if state.get("is_resolved"):
        status = "Resolved"
    elif state.get("escalated"):
        status = "Escalated"
    elif pending:
        status = "Awaiting Approval"
    else:
        status = "Closed"

    async with SessionLocal() as session:
        incident = await session.get(Incident, incident_id)
        if incident is None:
            return
        incident.status = status
        incident.root_cause = state.get("root_cause")
        incident.confidence_score = state.get("confidence_score")
        incident.requires_approval = requires_approval
        incident.state_snapshot = state
        if state.get("is_resolved"):
            incident.remediated_at = now

        for msg in state.get("messages", []):
            session.add(
                AgentRun(
                    incident_id=incident_id,
                    agent_name=_agent_name(str(msg.get("content", ""))),
                    status="completed",
                    inputs=msg,
                    outputs=msg,
                )
            )

        selected = state.get("selected_action") or {}
        if state.get("remediation_success") and selected.get("action_type"):
            detected_at = incident.detected_at or now
            # Some drivers (and SQLite in tests) return naive datetimes even
            # for tz-aware columns; normalise before subtracting.
            if detected_at.tzinfo is None:
                detected_at = detected_at.replace(tzinfo=UTC)
            session.add(
                Remediation(
                    incident_id=incident_id,
                    action=selected["action_type"],
                    incident_category=labels.get("alertname", "unknown"),
                    outcome="success",
                    time_to_resolve=(now - detected_at).total_seconds(),
                )
            )

        session.add(
            AuditLog(
                actor="monitoring",
                action="incident_processed",
                target=state.get("target_resource"),
                details={
                    "incident_id": incident_id,
                    "status": status,
                    "approval_status": state.get("approval_status"),
                    "escalated": state.get("escalated"),
                },
            )
        )
        await session.commit()

    await record_learning(state)

    if state.get("is_resolved") or state.get("escalated"):
        await writeback_incident(incident_id, state, labels)
    if state.get("escalated"):
        await notify("escalated", state, labels)
    elif state.get("is_resolved"):
        await notify("resolved", state, labels)


async def _create_incident(alert: dict[str, Any]) -> int | None:
    labels = alert.get("labels", {})
    severity, priority = classify_severity(labels)
    kind, resource = _resource_from_labels(labels)
    # Dedup: a repeated firing notification for the same alert/resource should
    # not spawn a second incident while the first one is still live.
    async with SessionLocal() as session:
        existing = (
            await session.execute(
                select(Incident.id).where(
                    Incident.alert_name == labels.get("alertname", "unknown"),
                    Incident.namespace == labels.get("namespace", "default"),
                    Incident.resource_name == resource,
                    Incident.status.not_in(FINAL_STATUSES),
                )
            )
        ).scalars().first()
        if existing is not None:
            return None
    incident = Incident(
        alert_name=labels.get("alertname", "unknown"),
        severity=severity,
        priority=priority,
        status="Investigating",
        namespace=labels.get("namespace", "default"),
        resource_kind=kind,
        resource_name=resource,
        labels=labels,
        detected_at=datetime.now(UTC),
    )
    async with SessionLocal() as session:
        session.add(incident)
        await session.commit()
        await session.refresh(incident)
        return incident.id


async def process_alert(alert: dict[str, Any]):
    incident_id = await _create_incident(alert)
    if incident_id is None:
        return
    labels = alert.get("labels", {})
    state = build_state(incident_id, alert)
    if state.get("severity") in ("SEV-1", "SEV-2"):
        await notify("alert", state, labels)
    try:
        s1 = await asyncio.to_thread(investigation_graph.invoke, state)
        if s1.get("is_safe") and not s1.get("requires_approval"):
            state = await asyncio.to_thread(remediation_graph.invoke, s1)
        else:
            state = s1
    except Exception as exc:  # fail safe: never leave an incident silently stuck
        state["escalated"] = True
        state["messages"].append(
            {"role": "system", "content": f"Reporting: pipeline failed - escalated ({exc})"}
        )
    await _persist_results(incident_id, state, labels)


@router.post("/alertmanager")
async def alertmanager_webhook(
    request: Request,
    authorization: str = Header(None),
):
    if not _authorized(authorization):
        raise HTTPException(status_code=401, detail="Unauthorized")

    payload = await request.json()
    alerts = payload.get("alerts", [])
    for alert in alerts:
        if alert.get("status") == "firing":
            task = asyncio.create_task(process_alert(alert))
            _background_tasks.add(task)
            task.add_done_callback(_background_tasks.discard)
            task.add_done_callback(_log_task_error)

    return {"status": "success", "alerts_processed": len(alerts)}
