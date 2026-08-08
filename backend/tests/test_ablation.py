"""Ablation switch tests (Epic I): each toggle changes exactly one behaviour
and the rest of the pipeline is unaffected."""
import pytest

from app.ablation import ablation


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
        "severity": "SEV-1",
        "priority": "P1",
        "detected_at": "2026-01-01T00:00:00",
        "namespace": "default",
        "target_resource": "catalogue-abc",
        "resource_kind": "pod",
        "logs": ["CrashLoopBackOff: Back-off restarting failed container"],
        "events": [],
        "metrics": {},
        "retrieved_docs": [
            {
                "doc_id": "runbook-crashloopbackoff",
                "document": "CrashLoopBackOff runbook: restart the pod after fixing the config",
                "distance": 0.3,
                "metadata": {},
            }
        ],
        "root_cause": "container is crash-looping",
        "confidence_score": 0.9,
        "candidate_actions": [],
        "selected_action": {"action_type": "restart_pod", "namespace": "default"},
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


def test_disable_rag_returns_no_docs():
    from app.agents.retrieval import retrieve

    ablation.disable_rag = True
    assert retrieve("crash loop") == []


def test_rag_enabled_returns_docs(monkeypatch):
    from app.agents.retrieval import retrieve

    monkeypatch.setattr(
        "app.agents.retrieval.vector_store",
        type("_S", (), {"query_text": lambda self, *a, **k: [{"doc_id": "x"}]})(),
    )
    assert retrieve("crash loop") == [{"doc_id": "x"}]


def test_disable_validation_assumes_resolved():
    from app.agents.validation import validation_node

    ablation.disable_validation = True
    result = validation_node(_state(retry_count=3))
    assert result["is_resolved"] is True
    assert result["escalated"] is False


def test_disable_safety_auto_approves_sev1():
    from app.agents.safety import safety_node

    ablation.disable_safety = True
    result = safety_node(_state(severity="SEV-1"))
    assert result["is_safe"] is True
    assert result["requires_approval"] is False
    assert result["approval_status"] == "approved"


def test_safety_gate_still_guards_sev1_when_enabled():
    from app.agents.safety import safety_node

    result = safety_node(_state(severity="SEV-1"))
    assert result["requires_approval"] is True
    assert result["approval_status"] == "pending"


def test_disable_bandit_uses_static_priorities():
    from app.agents.planning import planning_node

    ablation.disable_bandit = True
    result = planning_node(_state())
    assert all(c["source"] == "static" for c in result["candidate_actions"])
    # static priors rank restart_pod first
    assert result["selected_action"]["action_type"] == "restart_pod"


def test_disable_planning_ignores_retrieval_hints():
    """With planning disabled the plan is mechanical: retrieval runbooks do
    not inflate the expected reward of the hinted action."""
    from app.agents.planning import planning_node

    hinting_docs = [
        {
            "doc_id": "runbook-liveness-probe-failing",
            "document": "rollback the deployment to the previous revision",
            "distance": 0.2,
            "metadata": {},
        }
    ]
    state = _state(severity="SEV-2", resource_kind="deployment",
                   target_resource="catalogue", retrieved_docs=hinting_docs)

    def _reward(result, action):
        return next(c["expected_reward"] for c in result["candidate_actions"]
                    if c["action_type"] == action)

    ablation.disable_planning = True
    mechanical = planning_node(state)
    assert _reward(mechanical, "rollback_deployment") == pytest.approx(0.3)

    ablation.disable_planning = False
    informed = planning_node(state)
    assert _reward(informed, "rollback_deployment") == pytest.approx(0.5)
