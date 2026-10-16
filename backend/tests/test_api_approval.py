"""Human-in-the-loop approval: pending queue, approve (with operator override),
reject, and RBAC enforcement.
"""
from tests.api_helpers import (
    WEBHOOK_PATH,
    alertmanager_payload,
    scenario_labels,
    wait_for_incident,
    webhook_headers,
)


async def _raise_alert(api, scenario, resource_key: str = "pod"):
    await api.post(
        WEBHOOK_PATH,
        json=alertmanager_payload(scenario_labels(scenario, resource_key)),
        headers=webhook_headers(),
    )


async def test_pending_queue_lists_high_severity_incident(api, auth, pipeline, scenarios):
    pipeline(scenarios["S3"])
    await _raise_alert(api, scenarios["S3"], "deployment")
    incident = await wait_for_incident(api, auth(), "Awaiting Approval")

    pending = (await api.get("/v1/actions/pending", headers=auth("engineer"))).json()
    assert len(pending["pending"]) == 1
    entry = pending["pending"][0]
    assert entry["incident_id"] == incident["id"]
    assert entry["severity"] == "SEV-1"
    assert entry["selected_action"]["action_type"]


async def test_approve_with_operator_override_resolves(api, auth, pipeline, scenarios):
    pipeline(scenarios["S3"])
    await _raise_alert(api, scenarios["S3"], "deployment")
    incident = await wait_for_incident(api, auth(), "Awaiting Approval")

    res = await api.post(
        "/v1/actions/approve",
        json={
            "incident_id": str(incident["id"]),
            "action_type": "rollback_deployment",
            "approved": True,
            "target_resource": scenarios["S3"]["target_resource"],
            "namespace": scenarios["S3"]["namespace"],
        },
        headers=auth("engineer"),
    )
    assert res.status_code == 200
    assert res.json()["approved"] is True

    resolved = await wait_for_incident(api, auth(), "Resolved")
    assert resolved["id"] == incident["id"]

    trace = (
        await api.get(f"/v1/incidents/{incident['id']}/trace", headers=auth())
    ).json()
    assert trace["remediations"][0]["action"] == "rollback_deployment"


async def test_reject_escalates_incident(api, auth, pipeline, scenarios):
    pipeline(scenarios["S6"])
    await _raise_alert(api, scenarios["S6"], "node")
    incident = await wait_for_incident(api, auth(), "Awaiting Approval")

    res = await api.post(
        "/v1/actions/approve",
        json={
            "incident_id": str(incident["id"]),
            "action_type": "cordon_node",
            "approved": False,
        },
        headers=auth("admin"),
    )
    assert res.status_code == 200
    assert res.json()["approved"] is False

    escalated = await wait_for_incident(api, auth(), "Escalated")
    assert escalated["id"] == incident["id"]


async def test_viewer_cannot_approve(api, auth, pipeline, scenarios):
    pipeline(scenarios["S3"])
    await _raise_alert(api, scenarios["S3"], "deployment")
    incident = await wait_for_incident(api, auth(), "Awaiting Approval")

    res = await api.post(
        "/v1/actions/approve",
        json={
            "incident_id": str(incident["id"]),
            "action_type": "rollback_deployment",
            "approved": True,
        },
        headers=auth("viewer"),
    )
    assert res.status_code == 403


async def test_approve_unknown_incident_returns_404(api, auth):
    res = await api.post(
        "/v1/actions/approve",
        json={"incident_id": "9999", "action_type": "restart_pod", "approved": True},
        headers=auth("admin"),
    )
    assert res.status_code == 404
