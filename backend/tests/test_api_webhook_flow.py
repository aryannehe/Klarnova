"""End-to-end webhook tests.

They POST a real Alertmanager payload at the live endpoint and let the actual
background pipeline (investigation -> planning -> safety -> remediation ->
validation -> reporting) run against the mock cluster and deterministic
diagnosis, then assert on the persisted incident.
"""
from tests.api_helpers import (
    WEBHOOK_PATH,
    alertmanager_payload,
    scenario_labels,
    wait_for_incident,
    webhook_headers,
)


async def test_crashloop_is_diagnosed_and_autoremediated(api, auth, pipeline, scenarios):
    pipeline(scenarios["S1"])
    res = await api.post(
        WEBHOOK_PATH,
        json=alertmanager_payload(scenario_labels(scenarios["S1"])),
        headers=webhook_headers(),
    )
    assert res.status_code == 200
    assert res.json()["status"] == "success"

    incident = await wait_for_incident(api, auth(), "Resolved")
    assert incident["severity"] == "SEV-3"
    assert incident["resource_kind"] == "pod"
    assert incident["root_cause"] and "crash" in incident["root_cause"].lower()

    trace = (
        await api.get(f"/v1/incidents/{incident['id']}/trace", headers=auth())
    ).json()
    assert trace["agent_runs"], "expected an agent-run trace"
    assert trace["remediations"], "expected a recorded remediation"
    assert trace["remediations"][0]["action"] == "restart_pod"
    assert trace["remediations"][0]["outcome"] == "success"


async def test_webhook_rejects_missing_or_bad_token(api, scenarios):
    payload = alertmanager_payload(scenario_labels(scenarios["S1"]))
    assert (await api.post(WEBHOOK_PATH, json=payload)).status_code == 401
    assert (
        await api.post(
            WEBHOOK_PATH, json=payload, headers={"Authorization": "Bearer wrong"}
        )
    ).status_code == 401


async def test_duplicate_alert_is_deduplicated_while_live(api, auth, pipeline, scenarios):
    pipeline(scenarios["S3"])
    payload = alertmanager_payload(scenario_labels(scenarios["S3"], "deployment"))
    await api.post(WEBHOOK_PATH, json=payload, headers=webhook_headers())
    first = await wait_for_incident(api, auth(), "Awaiting Approval")

    # A repeated firing notification for the same live alert/resource must not
    # spawn a second incident.
    await api.post(WEBHOOK_PATH, json=payload, headers=webhook_headers())

    incidents = (await api.get("/v1/incidents", headers=auth())).json()
    matching = [i for i in incidents if i["alert_name"] == first["alert_name"]]
    assert len(matching) == 1


async def test_ignores_resolved_alerts(api, auth, pipeline, scenarios):
    pipeline(scenarios["S1"])
    payload = alertmanager_payload(scenario_labels(scenarios["S1"]), status="resolved")
    await api.post(WEBHOOK_PATH, json=payload, headers=webhook_headers())

    incidents = (await api.get("/v1/incidents", headers=auth())).json()
    assert incidents == []
