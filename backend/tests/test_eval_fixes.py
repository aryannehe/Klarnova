"""Regression tests for the round-2 eval-found fixes.

Covers the three gaps closed after the N=5 offline run:
- S4 diagnosis: image-pull logs ("Back-off pulling image ...") must resolve to
  an image-pull diagnosis, not be misread as a crash loop.
- S6 (and every scenario): planning only offers actions the resource kind can
  accept (node -> cordon, deployment -> scale/rollback), so the fallback loop
  can never burn retries on impossible actions.
- S5 action selection: a loose top-k retrieval match (large distance) must not
  override the static priors -- a CPU incident that incidentally surfaces a
  rollout-stuck runbook must not steer the plan to roll back.
"""
import pytest

from app.ablation import ablation
from app.agents import planning, root_cause


@pytest.fixture(autouse=True)
def _reset_ablation():
    for field in ("disable_rag", "disable_validation", "disable_safety",
                  "disable_planning", "disable_bandit"):
        setattr(ablation, field, False)
    yield
    for field in ("disable_rag", "disable_validation", "disable_safety",
                  "disable_planning", "disable_bandit"):
        setattr(ablation, field, False)


def _state(**overrides):
    state = {
        "incident_id": "1",
        "incident_data": {"alert_name": "KubePodCrashLooping", "labels": {}},
        "severity": "SEV-3",
        "priority": "P3",
        "detected_at": "2026-01-01T00:00:00",
        "namespace": "default",
        "target_resource": "catalogue-abc",
        "resource_kind": "pod",
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
        "max_retries": 2,
        "escalated": False,
        "resolved_at": None,
        "report": None,
        "messages": [],
    }
    state.update(overrides)
    return state


# --- S4: image-pull must win over crash-loop in the fallback diagnosis -----

def test_image_pull_not_misdiagnosed_as_crashloop():
    logs = [
        "Failed to pull image user-service:latest: rpc error: not found",
        "ImagePullBackOff",
        "Back-off pulling image user-service:latest",
    ]
    diagnosis = root_cause._fallback_diagnosis(_state(logs=logs))
    assert "image pull" in diagnosis
    assert "crash" not in diagnosis


def test_crashloop_still_detected_without_image_pull_signal():
    diagnosis = root_cause._fallback_diagnosis(
        _state(logs=["CrashLoopBackOff: Back-off restarting failed container"])
    )
    assert "crash" in diagnosis


# --- S6: kind-appropriate action set is a planner invariant -----------------

def test_kind_filter_node_offers_only_cordon():
    result = planning.planning_node(_state(resource_kind="node",
                                           target_resource="node-a"))
    types = [c["action_type"] for c in result["candidate_actions"]]
    assert types == ["cordon_node"]
    assert result["selected_action"]["action_type"] == "cordon_node"


def test_kind_filter_deployment_excludes_pod_actions():
    result = planning.planning_node(_state(resource_kind="deployment",
                                           severity="SEV-2"))
    types = [c["action_type"] for c in result["candidate_actions"]]
    assert "restart_pod" not in types
    assert "delete_pod" not in types
    assert "scale_deployment" in types
    assert "rollback_deployment" in types


def test_kind_filter_pod_keeps_pod_actions():
    result = planning.planning_node(_state(resource_kind="pod",
                                           severity="SEV-2"))
    types = [c["action_type"] for c in result["candidate_actions"]]
    assert "restart_pod" in types
    assert "delete_pod" in types


# --- S5: retrieval hints must be strongly relevant --------------------------

def _doc(document: str, distance: float) -> dict:
    return {"doc_id": "runbook-x", "document": document,
            "distance": distance, "metadata": {}}


def test_hint_ignored_when_retrieval_match_is_loose():
    state = _state(retrieved_docs=[
        _doc("rollback to the previous revision with kubectl rollout undo", 0.61)
    ])
    assert planning._prior_bump(state, "rollback_deployment") == 0.0


def test_hint_counts_when_retrieval_match_is_relevant():
    state = _state(retrieved_docs=[
        _doc("rollback the deployment to the previous revision", 0.2)
    ])
    assert planning._prior_bump(state, "rollback_deployment") == 0.2
