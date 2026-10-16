"""Small helpers shared by the API integration tests."""
import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from app.config import settings

WEBHOOK_PATH = "/v1/webhooks/alertmanager"


def webhook_headers() -> dict:
    return {"Authorization": f"Bearer {settings.ALERTMANAGER_WEBHOOK_TOKEN}"}


def scenario_labels(scenario: dict, resource_key: str = "pod") -> dict:
    """Turn a chaos scenario into realistic Alertmanager labels."""
    return {
        **scenario["labels"],
        resource_key: scenario["target_resource"],
        "namespace": scenario["namespace"],
    }


def alertmanager_payload(labels: dict[str, Any], status: str = "firing") -> dict:
    return {
        "version": "4",
        "status": status,
        "alerts": [
            {
                "status": status,
                "labels": labels,
                "annotations": {},
            }
        ],
    }


async def wait_until(
    fetch: Callable[[], Awaitable[Any]],
    predicate: Callable[[Any], bool],
    *,
    timeout: float = 15.0,
    interval: float = 0.05,
    description: str = "condition",
) -> Any:
    """Poll ``fetch`` until ``predicate`` is true, else fail."""
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = await fetch()
        if predicate(last):
            return last
        await asyncio.sleep(interval)
    raise AssertionError(f"timed out waiting for {description}; last={last!r}")


async def incident_with_status(api, headers, status: str | None = None):
    """Return the most recent incident (optionally filtered by status)."""
    params = {"status": status} if status else {}
    res = await api.get("/v1/incidents", headers=headers, params=params)
    assert res.status_code == 200, res.text
    return res.json()


async def wait_for_incident(api, headers, status: str, timeout: float = 15.0) -> dict:
    async def _fetch():
        incidents = await incident_with_status(api, headers, status)
        return incidents[0] if incidents else None

    return await wait_until(
        _fetch,
        lambda inc: inc is not None,
        timeout=timeout,
        description=f"incident in status {status}",
    )
