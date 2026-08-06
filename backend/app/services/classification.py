"""Detection decision + severity/priority classification (KLR-C6).

Rule-based only — no probabilistic output in the detection path
(agent-design §1: "Deterministic core, probabilistic edges").
"""

from __future__ import annotations

import hashlib

from app.schemas.incident import AlertmanagerWebhook, Priority, Severity

# Alert-name → (severity, priority). Higher-severity patterns first.
_ALERT_NAME_TABLE: dict[str, tuple[Severity, Priority]] = {
    "KubeNodeNotReady": (Severity.SEV_1, Priority.P1),
    "KubeNodeUnreachable": (Severity.SEV_1, Priority.P1),
    "TargetDown": (Severity.SEV_1, Priority.P1),
    "KubePodNotReady": (Severity.SEV_2, Priority.P2),
    "KubePodCrashLooping": (Severity.SEV_2, Priority.P2),
    "KubeDeploymentReplicasMismatch": (Severity.SEV_2, Priority.P2),
    "KubeContainerOOMKilled": (Severity.SEV_2, Priority.P2),
    "KubePodImagePullBackOff": (Severity.SEV_2, Priority.P2),
    "KubeCPUThrottlingHigh": (Severity.SEV_3, Priority.P3),
    "KubeMemoryPressure": (Severity.SEV_2, Priority.P2),
    "KubeDiskPressure": (Severity.SEV_2, Priority.P2),
    "KubePersistentVolumeErrors": (Severity.SEV_2, Priority.P2),
    "SampleAppDown": (Severity.SEV_1, Priority.P1),
    "SampleAppErrorRateHigh": (Severity.SEV_2, Priority.P2),
    "SampleAppRestarting": (Severity.SEV_3, Priority.P3),
    "SampleAppHighCPU": (Severity.SEV_3, Priority.P3),
    "SampleAppHighLatency": (Severity.SEV_2, Priority.P2),
}

# Prometheus severity label → (severity, priority) fallback.
_LABEL_SEVERITY_TABLE: dict[str, tuple[Severity, Priority]] = {
    "critical": (Severity.SEV_1, Priority.P1),
    "page": (Severity.SEV_1, Priority.P1),
    "high": (Severity.SEV_2, Priority.P2),
    "warning": (Severity.SEV_2, Priority.P2),
    "medium": (Severity.SEV_3, Priority.P3),
    "low": (Severity.SEV_4, Priority.P4),
    "info": (Severity.SEV_4, Priority.P4),
    "none": (Severity.SEV_4, Priority.P4),
}

_DEFAULT = (Severity.SEV_3, Priority.P3)


def classify_labels(labels: dict[str, str]) -> tuple[Severity, Priority]:
    """Classify from alert labels only (used by the polling path)."""
    name = (labels.get("alertname") or "").lower()
    for key, value in _ALERT_NAME_TABLE.items():
        if key.lower() == name:
            return value
    severity_label = (labels.get("severity") or "warning").lower()
    return _LABEL_SEVERITY_TABLE.get(severity_label, _DEFAULT)


def classify_alert(alert: AlertmanagerWebhook) -> tuple[Severity, Priority]:
    """Classify a webhook alert: alert-name table, then severity label, then default."""
    name = (alert.labels.get("alertname") or "").lower()
    for key, value in _ALERT_NAME_TABLE.items():
        if key.lower() == name:
            return value
    severity_label = (alert.labels.get("severity") or "warning").lower()
    return _LABEL_SEVERITY_TABLE.get(severity_label, _DEFAULT)


def fingerprint_alert(alert: AlertmanagerWebhook) -> str:
    """Deterministic dedup key from the alert fingerprint (falls back to labels)."""
    if alert.fingerprint:
        return alert.fingerprint
    labels = alert.labels or {}
    raw = ",".join(f"{k}={labels.get(k, '')}" for k in sorted(labels))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def affected_resource_from_labels(labels: dict[str, str]) -> str:
    """Compose 'namespace/kind/name' from alert labels."""
    namespace = labels.get("namespace") or labels.get("exported_namespace") or "default"
    if labels.get("pod"):
        kind, name = "Pod", labels["pod"]
    elif labels.get("deployment"):
        kind, name = "Deployment", labels["deployment"]
    elif labels.get("statefulset"):
        kind, name = "StatefulSet", labels["statefulset"]
    elif labels.get("daemonset"):
        kind, name = "DaemonSet", labels["daemonset"]
    elif labels.get("node"):
        kind, name = "Node", labels["node"]
    elif labels.get("kind"):
        kind, name = labels["kind"], labels.get("name") or labels.get("alertname") or "unknown"
    else:
        kind, name = "Resource", labels.get("alertname") or "unknown"
    return f"{namespace}/{kind}/{name}"
