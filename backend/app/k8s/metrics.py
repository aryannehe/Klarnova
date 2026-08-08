"""Prometheus metric helpers used by the Monitoring and Validation agents.

All functions are async and return plain Python values; they degrade to
``None`` when Prometheus is unreachable so the rest of the pipeline can
fail safe (escalate rather than act on missing data).
"""

from app.discovery.scraper import prometheus_scraper


def _first_value(result: dict) -> float | None:
    """Extract the scalar value from a Prometheus instant-query result."""
    try:
        return float(result["data"]["result"][0]["value"][1])
    except (KeyError, IndexError, TypeError, ValueError):
        return None


async def query_value(query_str: str) -> float | None:
    result = await prometheus_scraper.query(query_str)
    if result.get("status") != "success":
        return None
    return _first_value(result)


async def get_up_status() -> float | None:
    """Fraction of scrape targets that are up (0.0-1.0)."""
    return await query_value("sum(up) / count(up)")


async def get_unavailable_replicas(deployment: str, namespace: str) -> float | None:
    return await query_value(
        'kube_deployment_status_replicas_unavailable'
        f'{{namespace="{namespace}", deployment="{deployment}"}}'
    )


async def get_available_replicas(deployment: str, namespace: str) -> float | None:
    return await query_value(
        'kube_deployment_status_replicas_available'
        f'{{namespace="{namespace}", deployment="{deployment}"}}'
    )


async def get_restart_count(pod: str, namespace: str) -> float | None:
    return await query_value(
        'sum(kube_pod_container_status_restarts_total'
        f'{{namespace="{namespace}", pod="{pod}"}})'
    )


async def get_cpu_usage(pod: str, namespace: str) -> float | None:
    """CPU cores used, averaged over the last 5 minutes."""
    return await query_value(
        'sum(rate(container_cpu_usage_seconds_total'
        f'{{namespace="{namespace}", pod="{pod}"}}[5m]))'
    )


async def get_memory_usage(pod: str, namespace: str) -> float | None:
    """Memory used in bytes."""
    return await query_value(
        'sum(container_memory_working_set_bytes'
        f'{{namespace="{namespace}", pod="{pod}"}})'
    )


async def pod_restarting(pod: str, namespace: str, threshold: float = 1.0) -> bool:
    restarts = await get_restart_count(pod, namespace)
    return restarts is not None and restarts >= threshold


async def cluster_healthy() -> bool:
    """Overall health used by the Validation agent after remediation."""
    up = await get_up_status()
    if up is None:
        return False
    return up >= 0.9
