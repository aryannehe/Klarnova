"""Incident read endpoints: list/filter, aggregate stats, detail and trace."""
from datetime import UTC, datetime

from app.core.database import SessionLocal
from app.models.domain import AgentRun, Incident, Remediation


async def _add_incident(**overrides) -> int:
    defaults = dict(
        alert_name="KubePodCrashLooping",
        severity="SEV-3",
        priority="P3",
        status="Resolved",
        namespace="default",
        resource_kind="pod",
        resource_name="catalogue-abc",
        labels={"alertname": "KubePodCrashLooping"},
        detected_at=datetime.now(UTC),
    )
    defaults.update(overrides)
    async with SessionLocal() as session:
        incident = Incident(**defaults)
        session.add(incident)
        await session.commit()
        await session.refresh(incident)
        return incident.id


async def test_list_incidents_and_filter_by_status(api, auth):
    resolved_id = await _add_incident(status="Resolved")
    await _add_incident(status="Escalated", alert_name="KubeNodeNotReady")

    all_incidents = (await api.get("/v1/incidents", headers=auth())).json()
    assert len(all_incidents) == 2

    resolved = (
        await api.get("/v1/incidents", headers=auth(), params={"status": "Resolved"})
    ).json()
    assert [i["id"] for i in resolved] == [resolved_id]


async def test_list_incidents_respects_limit(api, auth):
    for _ in range(3):
        await _add_incident()
    limited = (
        await api.get("/v1/incidents", headers=auth(), params={"limit": 2})
    ).json()
    assert len(limited) == 2


async def test_stats_aggregate_status_severity_and_mttr(api, auth):
    await _add_incident(status="Resolved", severity="SEV-3")
    await _add_incident(status="Resolved", severity="SEV-1")
    await _add_incident(status="Escalated", severity="SEV-1")
    async with SessionLocal() as session:
        session.add(
            Remediation(
                incident_id=1,
                action="restart_pod",
                incident_category="KubePodCrashLooping",
                outcome="success",
                time_to_resolve=42.0,
            )
        )
        await session.commit()

    stats = (await api.get("/v1/incidents/stats", headers=auth())).json()
    assert stats["total"] == 3
    assert stats["resolved"] == 2
    assert stats["escalated"] == 1
    assert stats["resolved_rate"] == round(2 / 3, 3)
    assert stats["avg_mttr_seconds"] == 42.0
    assert stats["by_severity"]["SEV-1"] == 2
    assert len(stats["last_7_days"]) == 7


async def test_get_incident_detail_and_trace(api, auth):
    incident_id = await _add_incident(
        root_cause="crash-loop from bad startup",
        confidence_score=0.7,
        requires_approval=True,
        state_snapshot={
            "selected_action": {
                "action_type": "rollback_deployment",
                "target_resource": "api-gateway",
                "namespace": "default",
                "source": "operator",
            }
        },
    )
    async with SessionLocal() as session:
        session.add(
            AgentRun(
                incident_id=incident_id,
                agent_name="root_cause",
                status="completed",
                inputs={"content": "diagnosis"},
                outputs={"content": "diagnosis"},
            )
        )
        session.add(
            Remediation(
                incident_id=incident_id,
                action="rollback_deployment",
                incident_category="KubeDeploymentReplicasUnavailable",
                outcome="success",
                time_to_resolve=12.5,
            )
        )
        await session.commit()

    detail = (await api.get(f"/v1/incidents/{incident_id}", headers=auth())).json()
    assert detail["root_cause"] == "crash-loop from bad startup"
    assert detail["confidence_score"] == 0.7

    trace = (await api.get(f"/v1/incidents/{incident_id}/trace", headers=auth())).json()
    assert trace["requires_approval"] is True
    assert trace["selected_action"]["action_type"] == "rollback_deployment"
    assert trace["selected_action"]["source"] == "operator"
    assert trace["agent_runs"][0]["agent"] == "root_cause"
    assert trace["remediations"][0]["time_to_resolve"] == 12.5


async def test_unknown_incident_returns_404(api, auth):
    assert (await api.get("/v1/incidents/9999", headers=auth())).status_code == 404
    assert (
        await api.get("/v1/incidents/9999/trace", headers=auth())
    ).status_code == 404


async def test_viewer_may_read_incidents(api, auth):
    await _add_incident()
    assert (await api.get("/v1/incidents", headers=auth("viewer"))).status_code == 200
