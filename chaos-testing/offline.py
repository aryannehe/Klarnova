"""Offline evaluation engine (Epic I).

Simulates a Kubernetes cluster well enough to run the *real* agent pipeline
(runbook RAG, diagnosis, planning, safety, remediation, validation) without a
live cluster: the k8s client bindings are swapped for a scenario-aware mock,
and the LLM path is forced onto the deterministic fallback unless ``use_llm``
is requested.

Timestamps are simulated from a documented latency model (``LATENCIES``) so
offline MTTD/MTTR are relative, not wall-clock. Live runs (``run_experiments.py
--live``) record real values against a cluster.

Configs (docs/evaluation.md §4): ``full`` plus the five ablation variants
(no-rag, no-validation, no-safety, no-planning, no-bandit) and the two
baselines (manual, threshold-only).
"""
import json
import time
from typing import Any

from app.ablation import ablation
from tests.mock_cluster import (
    MockCluster,
    fast_validation as _fast_validation,
    force_fallback_llm as _force_fallback_llm,
    install_mock,
)

# --- Simulated latency model (seconds). Documented in evaluation-results.md. ---
LATENCIES = {
    "manual_detect": 180.0,
    "manual_investigate": 300.0,
    "manual_fix": 480.0,
    "detect": 2.0,
    "investigation": 5.0,
    "diagnosis": 3.0,
    "planning": 1.0,
    "fix_success": 15.0,
    "fix_retry": 30.0,
    "escalate": 60.0,
}

PROMPT_VERSION_FALLBACK = "root-cause-fallback-v2"
PROMPT_VERSION_LLM = "root-cause-llm-ollama-llama3.2-3b"
PROMPT_VERSION_MANUAL = "manual-baseline"
PROMPT_VERSION_THRESHOLD = "threshold-only-v1"

CONFIG_LABELS = {
    "full": {"disable_rag": False, "disable_validation": False,
             "disable_safety": False, "disable_planning": False, "disable_bandit": False},
    "no-rag": {"disable_rag": True},
    "no-validation": {"disable_validation": True},
    "no-safety": {"disable_safety": True},
    "no-planning": {"disable_planning": True},
    "no-bandit": {"disable_bandit": True},
}


def load_scenarios(path: str = "chaos-testing/scenarios.yaml") -> dict[str, dict]:
    import yaml

    with open(path, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return {s["id"]: s for s in data.get("scenarios", [])}


# MockCluster + install_mock now live in backend/tests/mock_cluster.py and are
# imported above, so the pytest suite and this harness share one cluster double.


# --- State construction ------------------------------------------------------

def build_state(scenario: dict, incident_id: str) -> dict[str, Any]:
    from app.agents.monitoring import classify_severity
    from app.agents.state import AgentState

    severity, priority = classify_severity(scenario.get("labels") or {})
    state: AgentState = {
        "incident_id": incident_id,
        "incident_data": {
            "alert_name": scenario.get("alert_name"),
            "labels": scenario.get("labels") or {},
        },
        "severity": severity,
        "priority": priority,
        "detected_at": None,
        "namespace": scenario.get("namespace", "default"),
        "target_resource": scenario.get("target_resource"),
        "resource_kind": scenario.get("resource_kind", "pod"),
        "logs": [],
        "events": list(scenario.get("events") or []),
        "metrics": scenario.get("metrics") or {},
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
    return state


# --- Config + ablation wiring -------------------------------------------------

def set_config(name: str):
    switches = CONFIG_LABELS.get(name, {})
    for field in ("disable_rag", "disable_validation", "disable_safety",
                  "disable_planning", "disable_bandit"):
        setattr(ablation, field, bool(switches.get(field, False)))


# --- Run engine --------------------------------------------------------------

def run_offline(
    scenario: dict,
    run_id: str,
    config: str = "full",
    human_approves: bool = True,
    use_llm: bool = False,
    incident_id: str | None = None,
) -> dict[str, Any]:
    from app.agents.graph import build_investigation_graph, build_remediation_graph

    set_config(config)
    cluster = MockCluster(scenario)
    install_mock(cluster)
    if not use_llm:
        _force_fallback_llm()
    _fast_validation()

    if incident_id is None:
        incident_id = f"eval-{scenario['id'].lower()}-{run_id}"

    t_injected = time.time()
    state = build_state(scenario, incident_id)
    inv_result = build_investigation_graph().invoke(state)
    detected_at = t_injected + LATENCIES["detect"]

    selected = inv_result.get("selected_action") or {}
    safety = {
        "is_safe": inv_result.get("is_safe"),
        "requires_approval": inv_result.get("requires_approval"),
        "approval_status": inv_result.get("approval_status"),
    }

    # Approval gate (mirrors app.api.approval + webhooks flow).
    decision_verdict = safety["approval_status"]
    executed_action = None
    if safety["requires_approval"] and safety["approval_status"] != "approved":
        if human_approves:
            inv_result["approval_status"] = "approved"
            decision_verdict = "approved"
        else:
            decision_verdict = "pending_human"
            return _make_record(
                scenario=scenario, run_id=run_id, config=config,
                incident_id=incident_id, t_injected=t_injected,
                detected_at=detected_at, inv_result=inv_result,
                decision_verdict=decision_verdict, use_llm=use_llm,
            )

    # Remediation graph (executes approved action, validates, retries, escalates).
    final = build_remediation_graph().invoke(inv_result)
    executed_action = (final.get("selected_action") or {}).get("action_type")
    resolved = bool(final.get("is_resolved"))
    escalated = bool(final.get("escalated"))

    resolve_latency = (
        LATENCIES["escalate"] if escalated
        else LATENCIES["fix_success"] + final.get("retry_count", 0) * LATENCIES["fix_retry"]
    )
    resolved_at = (detected_at + resolve_latency) if (resolved or escalated) else None

    return _make_record(
        scenario=scenario, run_id=run_id, config=config,
        incident_id=incident_id, t_injected=t_injected, detected_at=detected_at,
        resolved_at=resolved_at, inv_result=inv_result, final=final,
        decision_verdict=decision_verdict, executed_action=executed_action,
        use_llm=use_llm,
    )


def _make_record(
    scenario: dict, run_id: str, config: str, incident_id: str,
    t_injected: float, detected_at: float, inv_result: dict[str, Any],
    decision_verdict: str, use_llm: bool, resolved_at: float | None = None,
    final: dict[str, Any] | None = None, executed_action: str | None = None,
) -> dict[str, Any]:
    expected = set(scenario.get("expected_actions", []))
    expected_ids = set(scenario.get("retrieval_ground_truth", []))
    retrieved = inv_result.get("retrieved_docs", [])
    got_ids = {d.get("doc_id") for d in retrieved}
    diagnosis_text = (inv_result.get("root_cause") or "").lower()
    diag_keywords = [k.lower() for k in scenario.get("diagnosis_keywords", [])]

    final = final or {}
    record = {
        "run_id": run_id,
        "scenario_id": scenario["id"],
        "config": config,
        "injected_at": t_injected,
        "detected_at": detected_at,
        "resolved_at": resolved_at,
        "incident_id": incident_id,
        "severity": inv_result.get("severity"),
        "diagnosis": inv_result.get("root_cause"),
        "diagnosis_matched": bool(diag_keywords and any(k in diagnosis_text for k in diag_keywords)),
        "retrieved_docs": [d.get("doc_id") for d in retrieved],
        "retrieval_hit": bool(expected_ids & got_ids),
        "candidate_actions": [
            c.get("action_type") for c in inv_result.get("candidate_actions", [])
        ],
        "decision_verdict": decision_verdict,
        "selected_action": inv_result.get("selected_action"),
        "action_correct": bool(
            (inv_result.get("selected_action") or {}).get("action_type") in expected
        ),
        "executed_action": executed_action,
        "validation_outcome": (
            "resolved" if (final.get("is_resolved")) else
            "escalated" if (final.get("escalated")) else decision_verdict
        ),
        "remediation_success": bool(final.get("remediation_success")),
        "is_resolved": bool(final.get("is_resolved", False)),
        "retry_count": int(final.get("retry_count", inv_result.get("retry_count", 0))),
        "escalated": bool(final.get("escalated", False)),
        "confidence": inv_result.get("confidence_score"),
        "prompt_version": (
            PROMPT_VERSION_LLM if use_llm else PROMPT_VERSION_FALLBACK
        ),
        "source": "offline",
    }
    return record


# --- Baselines (simulated, documented assumptions) ----------------------------

def run_manual_baseline(scenario: dict, run_id: str) -> dict[str, Any]:
    """Simulated human: pages an on-call engineer, investigates, fixes.

    Assumptions (documented): humans always diagnose and fix correctly but are
    slow (5min page + 8min MTTR); they are themselves the escalation.
    """
    t_injected = time.time()
    detected_at = t_injected + LATENCIES["manual_detect"] + LATENCIES["manual_investigate"]
    resolved_at = detected_at + LATENCIES["manual_fix"]
    return {
        "run_id": run_id,
        "scenario_id": scenario["id"],
        "config": "manual",
        "injected_at": t_injected,
        "detected_at": detected_at,
        "resolved_at": resolved_at,
        "incident_id": f"manual-{scenario['id'].lower()}-{run_id}",
        "severity": "SEV-2",
        "diagnosis": scenario.get("ground_truth"),
        "diagnosis_matched": True,
        "retrieved_docs": [],
        "retrieval_hit": False,
        "candidate_actions": [scenario["primary_expected_action"]],
        "decision_verdict": "manual_fix",
        "selected_action": {"action_type": scenario["primary_expected_action"]},
        "action_correct": True,
        "executed_action": scenario["primary_expected_action"],
        "validation_outcome": "resolved",
        "remediation_success": True,
        "is_resolved": True,
        "retry_count": 0,
        "escalated": False,
        "confidence": 0.95,
        "prompt_version": PROMPT_VERSION_MANUAL,
        "source": "offline-simulated",
    }


def run_threshold_baseline(scenario: dict, run_id: str) -> dict[str, Any]:
    """Simulated threshold-only automation: alert fires, a fixed restart action
    runs with no diagnosis, no planning, no validation.

    Only resolves incidents that a blanket restart fixes; everything else
    "escalates" (no human-aware reasoning, so no real validation).
    """
    t_injected = time.time()
    detected_at = t_injected + LATENCIES["detect"]
    restart_works = "restart_pod" in scenario.get("expected_actions", [])
    if restart_works:
        resolved_at = detected_at + LATENCIES["fix_success"]
        escalated, resolved = False, True
    else:
        resolved_at = detected_at + LATENCIES["escalate"]
        escalated, resolved = True, False
    return {
        "run_id": run_id,
        "scenario_id": scenario["id"],
        "config": "threshold-only",
        "injected_at": t_injected,
        "detected_at": detected_at,
        "resolved_at": resolved_at,
        "incident_id": f"threshold-{scenario['id'].lower()}-{run_id}",
        "severity": "SEV-3",
        "diagnosis": None,
        "diagnosis_matched": False,
        "retrieved_docs": [],
        "retrieval_hit": False,
        "candidate_actions": ["restart_pod"],
        "decision_verdict": "auto",
        "selected_action": {"action_type": "restart_pod"},
        "action_correct": "restart_pod" in scenario.get("expected_actions", []),
        "executed_action": "restart_pod",
        "validation_outcome": "resolved" if resolved else "escalated",
        "remediation_success": restart_works,
        "is_resolved": resolved,
        "retry_count": 0,
        "escalated": escalated,
        "confidence": 0.0,
        "prompt_version": PROMPT_VERSION_THRESHOLD,
        "source": "offline-simulated",
    }


def write_record(record: dict[str, Any], results_dir: str):
    import os
    from pathlib import Path

    Path(results_dir).mkdir(parents=True, exist_ok=True)
    path = os.path.join(results_dir, f"{record['config']}-{record['scenario_id']}-{record['run_id']}.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(record, fh, indent=2, default=str)
