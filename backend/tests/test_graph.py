"""Graph behaviour tests.

These exercise the routing and safety contracts offline: k8s calls fail
safely (no cluster), and the LLM path is stubbed so diagnosis uses the
deterministic fallback.
"""
import pytest

from app.agents import root_cause
from app.agents.graph import (
    build_graph,
    build_investigation_graph,
    build_remediation_graph,
)


@pytest.fixture(autouse=True)
def _stub_llm(monkeypatch):
    def _raise(state):
        raise RuntimeError("no LLM in tests")

    monkeypatch.setattr(root_cause, "_diagnose_with_llm", _raise)
    # Offline: k8s calls fail immediately, so health polling must not wait.
    monkeypatch.setattr("app.agents.validation.HEALTH_POLL_TIMEOUT", 0)


def _base_state():
    return {
        "incident_id": "1",
        "incident_data": {
            "alert_name": "KubePodCrashLooping",
            "labels": {"alertname": "KubePodCrashLooping", "namespace": "default"},
        },
        "severity": "SEV-3",
        "priority": "P3",
        "detected_at": "2026-01-01T00:00:00",
        "namespace": "default",
        "target_resource": "catalogue-abc",
        "resource_kind": "pod",
        "logs": ["CrashLoopBackOff: Back-off restarting failed container"],
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
        "max_retries": 2,
        "escalated": False,
        "resolved_at": None,
        "report": None,
        "messages": [],
    }


def test_investigation_graph_full_path():
    graph = build_investigation_graph()
    result = graph.invoke(_base_state())

    assert result["root_cause"]
    assert result["selected_action"]["action_type"] in {
        "restart_pod",
        "delete_pod",
        "scale_deployment",
        "rollback_deployment",
        "cordon_node",
    }
    assert result["approval_status"] in ("pending", "approved", "rejected")
    # logs contain the crash-loop signal
    assert "CrashLoopBackOff" in " ".join(result["logs"])


def test_graph_alias():
    assert build_graph() is not None


def test_auto_incident_runs_remediation_then_retries_offline():
    """An offline cluster never shows 'resolved', so validation retries and
    eventually escalates instead of looping forever."""
    graph = build_remediation_graph()
    state = _base_state()
    state.update(
        {
            "is_safe": True,
            "requires_approval": False,
            "approval_status": "approved",
            "selected_action": {
                "action_type": "restart_pod",
                "target_resource": "catalogue-abc",
                "namespace": "default",
            },
        }
    )
    result = graph.invoke(state)

    assert result["retry_count"] > state["max_retries"]
    assert result["escalated"] is True
    assert result["is_resolved"] is False
    assert result["report"]


def test_pending_approval_never_remediates():
    from app.agents.remediation import can_execute

    state = _base_state()
    state.update(
        {
            "is_safe": True,
            "requires_approval": True,
            "approval_status": "pending",
            "selected_action": {"action_type": "restart_pod"},
        }
    )
    assert can_execute(state) is not None


def test_whitelist_enforced_in_remediation():
    from app.agents.remediation import remediation_node

    state = _base_state()
    state.update(
        {
            "is_safe": True,
            "requires_approval": False,
            "approval_status": "approved",
            "selected_action": {"action_type": "rm_rf"},
        }
    )
    result = remediation_node(state)
    assert result["remediation_success"] is False
