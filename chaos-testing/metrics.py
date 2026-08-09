"""Metric functions for the Epic I evaluation (docs/evaluation.md §2).

All scoring is deterministic and operates on per-run records written by the
harness. Records carry the fields listed in the protocol (timestamps, incident
id, severity, diagnosis vs ground truth, retrieved docs, candidate actions,
decision verdict, executed action, validation outcome, retry count, escalation
flag, confidence, prompt versions).
"""
import json
from pathlib import Path
from typing import Any, Iterable

RUN_RECORD_FIELDS = (
    "run_id",
    "scenario_id",
    "config",
    "injected_at",
    "detected_at",
    "resolved_at",
    "incident_id",
    "severity",
    "diagnosis",
    "diagnosis_matched",
    "retrieved_docs",
    "retrieval_hit",
    "candidate_actions",
    "decision_verdict",
    "selected_action",
    "action_correct",
    "executed_action",
    "validation_outcome",
    "remediation_success",
    "retry_count",
    "escalated",
    "confidence",
    "prompt_version",
    "source",  # offline | live
)

# Allowed actions and their static bandit priors (mirrors app.bandit.model).
ACTION_PRIORS = {
    "restart_pod": 0.6,
    "delete_pod": 0.5,
    "scale_deployment": 0.4,
    "rollback_deployment": 0.3,
    "cordon_node": 0.1,
}


def load_record(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_records(results_dir: str | Path) -> list[dict[str, Any]]:
    out = []
    for path in sorted(Path(results_dir).glob("**/*.json")):
        record = load_record(path)
        # skip aggregate outputs (metrics.json) that live beside the records
        if "scenario_id" in record and "config" in record:
            out.append(record)
    return out


def mttd_seconds(record: dict[str, Any]) -> float | None:
    """Time from failure injection to detection (0 when not detectable)."""
    injected = record.get("injected_at")
    detected = record.get("detected_at")
    if not injected or not detected:
        return None
    return max(0.0, float(detected) - float(injected))


def mttr_seconds(record: dict[str, Any]) -> float | None:
    """Time from detection to validated resolution."""
    detected = record.get("detected_at")
    resolved = record.get("resolved_at")
    if not detected or not resolved:
        return None
    return max(0.0, float(resolved) - float(detected))


def diagnosis_matches(record: dict[str, Any], keywords: Iterable[str]) -> bool:
    text = (record.get("diagnosis") or "").lower()
    return any(k.lower() in text for k in keywords)


def retrieval_hits(record: dict[str, Any], expected_ids: Iterable[str]) -> bool:
    got = {d.get("doc_id") for d in record.get("retrieved_docs", [])}
    return bool(set(expected_ids) & got)


def action_correct(record: dict[str, Any], expected_actions: Iterable[str]) -> bool:
    return (record.get("selected_action") or {}).get("action_type") in set(expected_actions)


def resolved(record: dict[str, Any]) -> bool:
    return bool(record.get("is_resolved"))


def escalated(record: dict[str, Any]) -> bool:
    return bool(record.get("escalated"))


def mean(values: Iterable[float | None]) -> float | None:
    nums = [v for v in values if v is not None]
    return sum(nums) / len(nums) if nums else None


def aggregate(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Roll up a set of run records into the committed metric set."""
    return {
        "n": len(records),
        "mttd_mean_s": mean(mttd_seconds(r) for r in records),
        "mttr_mean_s": mean(mttr_seconds(r) for r in records),
        "success_rate": mean(1.0 if resolved(r) else 0.0 for r in records),
        "escalation_rate": mean(1.0 if escalated(r) else 0.0 for r in records),
    }


def accuracy_by_scenario(records: list[dict[str, Any]], scenarios: dict[str, dict]) -> dict:
    """Root-cause accuracy + retrieval relevance + action accuracy per scenario."""
    out = {}
    for sid, sc in scenarios.items():
        runs = [r for r in records if r.get("scenario_id") == sid]
        if not runs:
            continue
        out[sid] = {
            "n": len(runs),
            "diagnosis_accuracy": mean(
                1.0 if r.get("diagnosis_matched") else 0.0 for r in runs
            ),
            "retrieval_relevance": mean(
                1.0 if r.get("retrieval_hit") else 0.0 for r in runs
            ),
            "action_accuracy": mean(
                1.0 if r.get("action_correct") else 0.0 for r in runs
            ),
        }
    return out
