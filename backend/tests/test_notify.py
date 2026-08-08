from app.services import notify


def _state():
    return {
        "incident_id": "7",
        "target_resource": "catalogue-abc",
        "namespace": "sock-shop",
        "severity": "SEV-3",
        "root_cause": "crash loop",
        "selected_action": {"action_type": "restart_pod"},
    }


async def test_notify_is_noop_when_unconfigured():
    # Default settings have no webhook -> silent no-op, no exceptions.
    assert await notify.notify("escalated", _state(), {}) is False


async def test_notify_sends_slack_payload(monkeypatch):
    sent: list[dict] = []

    class _FakePost:
        def raise_for_status(self):
            return None

    class _FakeClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            sent.append(json or {})
            return _FakePost()

    monkeypatch.setattr(notify.settings, "SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")
    monkeypatch.setattr(notify.settings, "SLACK_CHANNEL", "#ops")
    monkeypatch.setattr("app.services.notify.httpx.AsyncClient", lambda **kwargs: _FakeClient())

    ok = await notify.notify("escalated", _state(), {})
    assert ok is True
    assert len(sent) == 1
    text = sent[0]["text"]
    assert "Incident `7`" in text
    assert "catalogue-abc" in text
    assert "restart_pod" in text
    assert sent[0]["channel"] == "#ops"


async def test_notify_handles_failure(monkeypatch):
    class _BoomClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def post(self, url, json=None):
            raise RuntimeError("connection refused")

    monkeypatch.setattr(notify.settings, "SLACK_WEBHOOK_URL", "https://hooks.slack.com/x")
    monkeypatch.setattr("app.services.notify.httpx.AsyncClient", lambda **kwargs: _BoomClient())

    assert await notify.notify("resolved", _state(), {}) is False
