from app.api.webhooks import _authorized, _resource_from_labels, build_state
from app.config import settings


def test_authorized_bearer():
    assert _authorized(f"Bearer {settings.ALERTMANAGER_WEBHOOK_TOKEN}") is True


def test_authorized_raw_token():
    assert _authorized(settings.ALERTMANAGER_WEBHOOK_TOKEN) is True


def test_unauthorized():
    assert _authorized("Bearer wrong") is False
    assert _authorized(None) is False


def test_resource_from_labels():
    kind, name = _resource_from_labels(
        {"pod": "catalogue-abc", "namespace": "default"}
    )
    assert (kind, name) == ("pod", "catalogue-abc")


def test_build_state_defaults():
    state = build_state(42, {"labels": {"alertname": "KubePodCrashLooping"}})
    assert state["incident_id"] == "42"
    assert state["target_resource"] == "unknown"
    assert state["max_retries"] == 2
    assert state["approval_status"] is None
    assert state["logs"] == []
