"""Minimal LangGraph detection wiring tests (KLR-C7)."""

from app.agents.graph import run_detection
from app.agents.state import AgentState, IncidentSchema
from app.schemas.incident import Priority, Severity


def test_detection_graph_classifies_incident():
    state = AgentState(
        incident=IncidentSchema(
            alert_name="KubePodImagePullBackOff",
            severity=Severity.SEV_4,
            priority=Priority.P4,
            affected_resource="sample/Deployment/checkout",
            labels={"alertname": "KubePodImagePullBackOff", "severity": "warning"},
        )
    )
    result = run_detection(state)
    assert result.severity == Severity.SEV_2
    assert result.priority == Priority.P2
    assert result.incident is not None
    assert result.incident.severity == Severity.SEV_2
