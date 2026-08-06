"""Monitoring / Ingestion Agent (KLR-C5) — rule-based.

Polls Prometheus (ALERTS) and the K8s API, evaluates detection rules, and
classifies incidents (SEV-1…4 / P1…4). Rule-based only, per agent-design §1.
"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import AgentState, IncidentSchema
from app.config import Settings
from app.k8s.client import get_k8s_client
from app.k8s.metrics import PrometheusClient, get_prometheus_url
from app.services.classification import (
    affected_resource_from_labels,
    classify_labels,
    fingerprint_alert,
)

logger = logging.getLogger(__name__)


class MonitoringAgent:
    """Poll-loop agent. Each detection decision writes to AgentState."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._prometheus: PrometheusClient | None = None

    @property
    def prometheus(self) -> PrometheusClient:
        if self._prometheus is None:
            self._prometheus = PrometheusClient(get_prometheus_url())
        return self._prometheus

    async def detect_from_alerts(self, session: AsyncSession) -> list[AgentState]:
        """Poll Prometheus for firing alerts and build detection decisions."""
        alerts = await asyncio.to_thread(self.prometheus.firing_alerts)
        decisions: list[AgentState] = []
        for alert in alerts:
            labels = alert.get("labels") or {}
            severity, priority = classify_labels(labels)
            fingerprint = alert.get("fingerprint") or fingerprint_alert(
                _alert_from_labels(labels, alert.get("annotations") or {})
            )
            state = AgentState(
                severity=severity,
                priority=priority,
                incident=IncidentSchema(
                    alert_fingerprint=fingerprint,
                    alert_name=labels.get("alertname"),
                    source="monitoring_agent",
                    severity=severity,
                    priority=priority,
                    affected_resource=affected_resource_from_labels(labels),
                    summary=(alert.get("annotations") or {}).get("summary"),
                    evidence=alert.get("annotations") or {},
                    started_at=_parse_dt(alert.get("starts_at")),
                ),
            )
            decisions.append(state)
        return decisions

    async def detect_unhealthy_pods(self, session: AsyncSession) -> list[AgentState]:
        """Poll K8s API for crash-looping / not-ready pods (rule-based detection)."""
        client = get_k8s_client()
        pods = await asyncio.to_thread(
            client.list_pods, self.settings.monitoring_namespace
        )
        decisions: list[AgentState] = []
        for pod in pods:
            statuses = pod.get("container_statuses", [])
            restart_count = sum(s.get("restart_count", 0) for s in statuses)
            all_ready = bool(statuses) and all(s.get("ready") for s in statuses)
            phase = pod.get("phase")
            if phase == "Running" and restart_count < 2 and all_ready:
                continue
            if restart_count >= 2:
                reason = "CrashLoopBackOff"
            elif not all_ready:
                reason = "NotReady"
            else:
                reason = phase
            severity, priority = classify_labels(
                {"alertname": "KubePodCrashLooping", "severity": "warning"}
            )
            # Stable per-pod identity (no restart_count) so repeated polls of the
            # same ongoing problem update one incident instead of creating a new
            # row every poll tick.
            fingerprint = f"pod:{pod['namespace']}/{pod['name']}"
            state = AgentState(
                severity=severity,
                priority=priority,
                incident=IncidentSchema(
                    alert_fingerprint=fingerprint,
                    alert_name="KubePodCrashLooping",
                    source="monitoring_agent",
                    severity=severity,
                    priority=priority,
                    affected_resource=f"{pod['namespace']}/Pod/{pod['name']}",
                    summary=f"Pod {pod['name']} in phase {reason} with {restart_count} restarts",
                    evidence={"phase": phase, "restart_count": restart_count, "ready": all_ready},
                ),
            )
            decisions.append(state)
        return decisions

    async def run_once(self, session: AsyncSession) -> list[AgentState]:
        decisions = []
        try:
            decisions.extend(await self.detect_from_alerts(session))
        except Exception as exc:  # pragma: no cover - network dependent
            logger.warning("Monitoring: Prometheus poll failed: %s", exc)
        try:
            decisions.extend(await self.detect_unhealthy_pods(session))
        except Exception as exc:  # pragma: no cover - network dependent
            logger.warning("Monitoring: K8s poll failed: %s", exc)
        return decisions


def _alert_from_labels(labels: dict[str, str], annotations: dict[str, str]):
    """Adapter so label-only alerts reuse the fingerprint helper."""
    from app.schemas.incident import AlertmanagerWebhook

    return AlertmanagerWebhook(status="firing", labels=labels, annotations=annotations)


def _parse_dt(value) -> None:
    return None  # kept simple; timestamps come from webhook path in Phase 1
