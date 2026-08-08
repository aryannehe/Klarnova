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
import types
from typing import Any

from app.ablation import ablation

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


# --- Mock Kubernetes client -------------------------------------------------

def _failing_container_status():
    return types.SimpleNamespace(
        state=types.SimpleNamespace(
            waiting=types.SimpleNamespace(reason="CrashLoopBackOff"),
            terminated=None,
        )
    )


class _CoreV1:
    def __init__(self, cluster):
        self._cluster = cluster

    def read_namespaced_pod(self, name, namespace):
        if self._cluster._fixed():
            return types.SimpleNamespace(
                status=types.SimpleNamespace(phase="Running", container_statuses=[])
            )
        return types.SimpleNamespace(
            status=types.SimpleNamespace(
                phase="Running",
                container_statuses=[_failing_container_status()],
            )
        )

    def delete_namespaced_pod(self, name, namespace):
        # restart_pod and delete_pod share this API call; both reset the pod,
        # so the simulator records restart_pod (delete_pod is never a ground
        # truth action in the scenario set).
        self._cluster._apply("restart_pod", name)
        return types.SimpleNamespace(metadata=types.SimpleNamespace(name=name))

    def patch_node(self, name, body):
        self._cluster._apply("cordon_node", name)
        return types.SimpleNamespace(metadata=types.SimpleNamespace(name=name))

    def list_namespaced_event(self, namespace):
        return types.SimpleNamespace(items=[])


class _AppsV1:
    def __init__(self, cluster):
        self._cluster = cluster

    def read_namespaced_deployment(self, name, namespace):
        fixed = self._cluster._fixed()
        return types.SimpleNamespace(
            metadata=types.SimpleNamespace(
                annotations={"deployment.kubernetes.io/revision": "2"}
            ),
            spec=types.SimpleNamespace(
                template=types.SimpleNamespace(
                    spec=types.SimpleNamespace(
                        containers=[types.SimpleNamespace(name="app", image="sock-shop/app:bad")]
                    )
                )
            ),
            status=types.SimpleNamespace(
                replicas=3, available_replicas=3 if fixed else 0
            ),
        )

    def list_namespaced_replica_set(self, namespace):
        return types.SimpleNamespace(
            items=[
                types.SimpleNamespace(
                    metadata=types.SimpleNamespace(
                        annotations={"deployment.kubernetes.io/revision": "1"},
                        creation_timestamp=None,
                    ),
                    spec=types.SimpleNamespace(
                        template=types.SimpleNamespace(
                            spec=types.SimpleNamespace(
                                containers=[types.SimpleNamespace(image="sock-shop/app:good")]
                            )
                        )
                    ),
                )
            ]
        )

    def patch_namespaced_deployment(self, name, namespace, body):
        self._cluster._apply("rollback_deployment", name)
        return types.SimpleNamespace(metadata=types.SimpleNamespace(name=name))

    def patch_namespaced_deployment_scale(self, name, namespace, body):
        self._cluster._apply("scale_deployment", name)
        return types.SimpleNamespace(metadata=types.SimpleNamespace(name=name))


class MockCluster:
    """Scenario-aware fake of ``app.k8s.client.k8s_client``.

    Health follows the ground truth: once any ``expected_actions`` has been
    applied, the cluster reads as healthy and validation passes.
    """

    def __init__(self, scenario: dict):
        self.scenario = scenario
        self.applied: list[dict[str, Any]] = []
        self.core_v1 = _CoreV1(self)
        self.apps_v1 = _AppsV1(self)

    def _apply(self, action_type: str, target: str):
        self.applied.append({"action_type": action_type, "target": target})

    def _fixed(self) -> bool:
        applied_types = {a["action_type"] for a in self.applied}
        return bool(applied_types & set(self.scenario.get("expected_actions", [])))

    def get_pod_logs(self, name, namespace="default", tail_lines=100):
        return self.scenario.get("logs", "")

    def get_previous_pod_logs(self, name, namespace="default", tail_lines=100):
        return None

    def get_pods(self, namespace="default"):
        return types.SimpleNamespace(items=[])

    def get_deployments(self, namespace="default"):
        return types.SimpleNamespace(items=[])


def install_mock(cluster: MockCluster):
    """Swap the k8s client binding in every module that imported it."""
    import app.k8s.actions as actions_mod
    import app.k8s.client as client_mod
    from app.agents import investigation as inv_mod
    from app.agents import validation as val_mod

    client_mod.k8s_client = cluster
    inv_mod.k8s_client = cluster
    val_mod.k8s_client = cluster
    actions_mod.k8s_client = cluster


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


def _force_fallback_llm():
    from app.agents import root_cause

    def _raise(_state):
        raise RuntimeError("offline eval uses deterministic fallback")
    root_cause._diagnose_with_llm = _raise


def _fast_validation():
    """The mock cluster is deterministic, so the 120s health poll is pointless."""
    from app.agents import validation as val_mod

    val_mod.HEALTH_POLL_TIMEOUT = 0.0
    val_mod.HEALTH_POLL_INTERVAL = 0.0


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
