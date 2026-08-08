"""Monitoring agent - detection and severity/priority classification.

Severity/priority per the PRD section 4.3:

    SEV-1 (P1) critical  -> service down / customer-facing outage
    SEV-2 (P2) high      -> major degradation
    SEV-3 (P3) medium    -> partial / localised issue
    SEV-4 (P4) low       -> minor or non-urgent

Classification is deterministic (rule-based), never LLM-driven, so the
safety guarantees never depend on probabilistic model output.
"""
import re
from typing import Any

from app.agents.state import AgentState

SEV_MAP = {
    "critical": "SEV-1",
    "high": "SEV-2",
    "warning": "SEV-3",
    "warn": "SEV-3",
    "info": "SEV-4",
    "severe": "SEV-1",
}

PRIORITY_MAP = {"SEV-1": "P1", "SEV-2": "P2", "SEV-3": "P3", "SEV-4": "P4"}

KEYWORD_RULES = [
    (r"down|unavailable|notready|outage|nodebooting|connectionlost", "SEV-1"),
    (r"highmemory|highcpu|high.*load|degraded|elevated|replica.*unavailable", "SEV-2"),
    (r"restart|crashloop|backoff|imagerullback|oom", "SEV-3"),
    (r"info|minor|low|warning", "SEV-4"),
]


def classify_severity(labels: dict[str, Any]) -> tuple[str, str]:
    """Map Alertmanager labels to (severity, priority)."""
    sev_label = (labels.get("severity") or "").lower()
    alertname = (labels.get("alertname") or "").lower()

    if sev_label in SEV_MAP:
        severity = SEV_MAP[sev_label]
    else:
        severity = "SEV-3"
        for pattern, sev in KEYWORD_RULES:
            if re.search(pattern, alertname):
                severity = sev
                break

    return severity, PRIORITY_MAP.get(severity, "P3")


def detect_anomaly(metrics: dict[str, Any]) -> str | None:
    """Return a reason string when a metric anomaly is detected, else None.

    ``metrics`` is a dict of named PromQL results (see k8s.metrics helpers).
    """
    unavailable = metrics.get("unavailable_replicas")
    if unavailable is not None and unavailable > 0:
        return f"{unavailable} replica(s) unavailable"

    restarts = metrics.get("restart_count")
    if restarts is not None and restarts >= 3:
        return f"pod restart count {restarts} (>= 3)"

    up = metrics.get("up")
    if up is not None and up < 0.9:
        return f"Prometheus scrape success below 90% ({up})"

    return None


def monitoring_node(state: AgentState):
    """Classify severity/priority when the webhook did not provide labels."""
    labels = state.get("incident_data", {}).get("labels", {})
    severity, priority = classify_severity(labels)
    return {
        "severity": severity,
        "priority": priority,
        "messages": [
            {
                "role": "system",
                "content": f"Monitoring: incident classified {severity} ({priority})",
            }
        ],
    }
