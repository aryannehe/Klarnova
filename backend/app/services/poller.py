"""Background monitoring poller (KLR-C5/C7)."""

from __future__ import annotations

import asyncio
import logging
from contextlib import suppress

from app.agents.monitoring import MonitoringAgent
from app.config import Settings
from app.core.database import get_session_factory
from app.schemas.incident import IncidentCreate
from app.services.ingestion import persist_incident

logger = logging.getLogger(__name__)


class MonitoringPoller:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.agent = MonitoringAgent(settings)
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def _loop(self) -> None:
        logger.info(
            "Monitoring poller started (interval=%ss)",
            self.settings.monitoring_poll_interval_seconds,
        )
        while not self._stop.is_set():
            try:
                await self._poll_once()
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Monitoring poll iteration failed: %s", exc)  # noqa: TRY401
            try:
                await asyncio.wait_for(
                    self._stop.wait(), timeout=self.settings.monitoring_poll_interval_seconds
                )
            except TimeoutError:
                continue

    async def _poll_once(self) -> None:
        async with get_session_factory()() as session:
            decisions = await self.agent.run_once(session)
            for state in decisions:
                if state.incident is None:
                    continue
                incident = state.incident
                await persist_incident(
                    session,
                    IncidentCreate(
                        alert_fingerprint=incident.alert_fingerprint,
                        alert_name=incident.alert_name,
                        source=incident.source,
                        severity=incident.severity,
                        priority=incident.priority,
                        affected_resource=incident.affected_resource,
                        summary=incident.summary,
                        evidence=incident.evidence,
                        started_at=incident.started_at,
                    ),
                )
                logger.info(
                    "Monitoring: persisted incident %s (%s)",
                    incident.affected_resource,
                    incident.severity.value,
                )

    async def start(self) -> None:
        if not self.settings.monitoring_enabled or self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._stop.set()
        self._task.cancel()
        with suppress(asyncio.CancelledError):
            await self._task
        self._task = None
