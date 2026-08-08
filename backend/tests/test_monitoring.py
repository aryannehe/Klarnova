from app.agents.monitoring import classify_severity, detect_anomaly


def test_severity_label_used_directly():
    sev, prio = classify_severity({"severity": "critical"})
    assert (sev, prio) == ("SEV-1", "P1")


def test_alertname_keyword_raises_severity():
    sev, prio = classify_severity({"alertname": "KubePodCrashLooping"})
    assert (sev, prio) == ("SEV-3", "P3")


def test_outage_keyword_is_sev1():
    sev, _ = classify_severity({"alertname": "KubeNodeNotReady"})
    assert sev == "SEV-1"


def test_default_sev3():
    sev, prio = classify_severity({"alertname": "SomethingOdd"})
    assert (sev, prio) == ("SEV-3", "P3")


def test_detect_anomaly():
    assert detect_anomaly({"unavailable_replicas": 2}) is not None
    assert detect_anomaly({"restart_count": 5}) is not None
    assert detect_anomaly({"up": 1.0}) is None
