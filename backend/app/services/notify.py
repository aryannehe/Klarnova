"""Outbound human notifications (Slack webhook, Epic F9).

Non-blocking and non-fatal: when no webhook is configured, or a delivery
fails, we only log a warning and never disturb the incident pipeline.
"""
import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

EVENT_TEXTS = {
    "alert": "High-severity alert detected",
    "escalated": "Incident escalated to a human",
    "rejected": "Operator rejected the proposed action",
    "resolved": "Incident auto-remediated",
}


async def notify(event: str, state: dict, labels: dict) -> bool:
    """Send a Slack message about an incident event. Returns True if delivered."""
    webhook = settings.SLACK_WEBHOOK_URL
    if not webhook:
        return False

    incident_id = state.get("incident_id", "unknown")
    target = state.get("target_resource", "unknown")
    namespace = state.get("namespace", "default")
    severity = state.get("severity", "SEV-3")
    root_cause = state.get("root_cause") or "not diagnosed"
    action = (state.get("selected_action") or {}).get("action_type", "none")

    text = (
        f"*{EVENT_TEXTS.get(event, event)}*\n"
        f"Incident `{incident_id}` ({severity}) on `{target}` in `{namespace}`\n"
        f"Root cause: {root_cause}\n"
        f"Selected action: `{action}`"
    )
    payload: dict = {"text": text}
    if settings.SLACK_CHANNEL:
        payload["channel"] = settings.SLACK_CHANNEL

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(webhook, json=payload)
            resp.raise_for_status()
    except Exception as exc:
        logger.warning(
            "Slack notification failed (%s) for incident %s: %s", event, incident_id, exc
        )
        return False

    logger.info("Slack notification sent (%s) for incident %s", event, incident_id)
    return True
