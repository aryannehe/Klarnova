"""Ingestion + webhook endpoint tests (KLR-C4)."""


from app.schemas.incident import AlertmanagerWebhook, IncidentStatus
from app.services.ingestion import ingest_alert

WEBHOOK_PAYLOAD = {
    "version": "4",
    "status": "firing",
    "receiver": "klarnova-webhook",
    "alerts": [
        {
            "status": "firing",
            "labels": {
                "alertname": "SampleAppErrorRateHigh",
                "severity": "warning",
                "app": "checkout",
                "namespace": "sample",
                "pod": "checkout-abc",
            },
            "annotations": {
                "summary": "High error rate on checkout",
                "description": "checkout is returning 5xx responses.",
            },
            "startsAt": "2026-08-06T10:00:00Z",
            "fingerprint": "fp-error-rate-1",
        }
    ],
}


async def test_ingest_alert_creates_record(session):
    alert = AlertmanagerWebhook(**WEBHOOK_PAYLOAD["alerts"][0])
    incident = await ingest_alert(session, alert)

    assert incident.alert_name == "SampleAppErrorRateHigh"
    assert incident.severity == "SEV-2"
    assert incident.priority == "P2"
    assert incident.status == IncidentStatus.DETECTED
    assert incident.affected_resource == "sample/Pod/checkout-abc"
    assert incident.alert_fingerprint == "fp-error-rate-1"


async def test_ingest_alert_dedupes_by_fingerprint(session):
    alert = AlertmanagerWebhook(**WEBHOOK_PAYLOAD["alerts"][0])
    first = await ingest_alert(session, alert)
    second = await ingest_alert(session, alert)

    assert first.id == second.id


def test_webhook_requires_token(client):
    resp = client.post("/api/v1/webhooks/alertmanager", json=WEBHOOK_PAYLOAD)
    assert resp.status_code == 401


def test_webhook_rejects_wrong_token(client):
    resp = client.post(
        "/api/v1/webhooks/alertmanager",
        json=WEBHOOK_PAYLOAD,
        headers={"X-Klarnova-Token": "wrong"},
    )
    assert resp.status_code == 401


def test_webhook_creates_incident(client):
    resp = client.post(
        "/api/v1/webhooks/alertmanager",
        json=WEBHOOK_PAYLOAD,
        headers={"X-Klarnova-Token": "test-token"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["alert_name"] == "SampleAppErrorRateHigh"
    assert body[0]["severity"] == "SEV-2"
