from datetime import UTC, datetime

from app.agents.state import AgentState


def reporting_node(state: AgentState):
    """Compile the incident report record."""
    incident_id = state.get("incident_id", "unknown")
    severity = state.get("severity", "SEV-3")
    priority = state.get("priority", "P3")
    target = state.get("target_resource", "unknown")
    ns = state.get("namespace", "default")
    root_cause = state.get("root_cause") or "not diagnosed"
    confidence = state.get("confidence_score", 0.0)
    action = (state.get("selected_action") or {}).get("action_type", "none")
    approval = state.get("approval_status", "n/a")
    resolved = state.get("is_resolved", False)
    escalated = state.get("escalated", False)

    outcome = "resolved"
    if escalated:
        outcome = "escalated to human"
    elif not resolved and not state.get("remediation_result"):
        outcome = "pending approval"

    report = (
        f"Incident {incident_id} ({severity}/{priority}): {target} in namespace {ns}.\n"
        f"Root cause: {root_cause}\n"
        f"Confidence: {confidence:.2f}\n"
        f"Selected action: {action} (approval: {approval})\n"
        f"Outcome: {outcome}\n"
        f"Trace: {state.get('remediation_result') or 'no action executed'}"
    )

    now = datetime.now(UTC).isoformat()
    return {
        "report": report,
        "resolved_at": now if resolved else None,
        "messages": [{"role": "system", "content": f"Reporting: {outcome}"}],
    }
