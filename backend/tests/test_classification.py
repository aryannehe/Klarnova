"""Classification service tests (KLR-C6)."""

from app.schemas.incident import AlertmanagerWebhook, Priority, Severity
from app.services.classification import (
    affected_resource_from_labels,
    classify_alert,
    classify_labels,
    fingerprint_alert,
)


def test_alert_name_table_overrides_severity_label():
    alert = AlertmanagerWebhook(
        status="firing",
        labels={"alertname": "KubePodCrashLooping", "severity": "info"},
    )
    severity, priority = classify_alert(alert)
    assert severity == Severity.SEV_2
    assert priority == Priority.P2


def test_severity_label_fallback():
    alert = AlertmanagerWebhook(labels={"alertname": "UnknownThing", "severity": "critical"})
    severity, priority = classify_alert(alert)
    assert severity == Severity.SEV_1
    assert priority == Priority.P1


def test_default_classification_when_no_hints():
    severity, priority = classify_alert(AlertmanagerWebhook(labels={"alertname": "X"}))
    assert severity == Severity.SEV_2
    assert priority == Priority.P2


def test_classify_labels_matches_classify_alert():
    labels = {"alertname": "SampleAppHighCPU", "severity": "warning"}
    assert classify_labels(labels) == classify_alert(AlertmanagerWebhook(labels=labels))


def test_fingerprint_from_explicit_value():
    alert = AlertmanagerWebhook(labels={"alertname": "A"}, fingerprint="abc123")
    assert fingerprint_alert(alert) == "abc123"


def test_fingerprint_stable_for_same_labels():
    a = AlertmanagerWebhook(labels={"alertname": "A", "pod": "x"})
    b = AlertmanagerWebhook(labels={"pod": "x", "alertname": "A"})
    assert fingerprint_alert(a) == fingerprint_alert(b)


def test_affected_resource_compilation():
    labels = {"namespace": "sample", "pod": "checkout-abc", "deployment": "checkout"}
    assert affected_resource_from_labels(labels) == "sample/Pod/checkout-abc"
