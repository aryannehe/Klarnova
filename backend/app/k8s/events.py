"""Kubernetes events collection for the Investigation agent."""

from app.k8s.client import k8s_client


def _fmt_event(event) -> str:
    involved = getattr(event, "involved_object", None)
    name = getattr(involved, "name", "unknown") if involved else "unknown"
    reason = getattr(event, "reason", "")
    message = getattr(event, "message", "")
    count = getattr(event, "count", 1)
    return f"[{reason}] {name}: {message} (count={count})"


def get_events(namespace: str = "default", limit: int = 50) -> list[str]:
    """Return formatted events for a namespace, most recent first."""
    try:
        events = k8s_client.get_events(namespace)
    except Exception:
        return []
    items = sorted(
        getattr(events, "items", []),
        key=lambda e: getattr(e, "last_timestamp", None) or getattr(e, "first_timestamp", None),
        reverse=True,
    )
    return [_fmt_event(e) for e in items[:limit]]


def get_resource_events(
    resource_name: str, namespace: str = "default", limit: int = 20
) -> list[str]:
    """Return events whose involved object matches the target resource."""
    try:
        events = k8s_client.get_events(namespace)
    except Exception:
        return []
    items = getattr(events, "items", [])
    filtered = [
        e
        for e in items
        if getattr(getattr(e, "involved_object", None), "name", None) == resource_name
    ]
    filtered.sort(
        key=lambda e: getattr(e, "last_timestamp", None) or getattr(e, "first_timestamp", None),
        reverse=True,
    )
    return [_fmt_event(e) for e in filtered[:limit]]


def get_errors(namespace: str = "default", limit: int = 20) -> list[str]:
    """Return only error/warning events to surface crash-loop and OOM signals."""
    events = get_events(namespace, limit=200)
    keywords = ("Failed", "Error", "BackOff", "OOM", "Killing")
    return [e for e in events if any(k in e for k in keywords)][:limit]


def get_oom_events(namespace: str = "default") -> str | None:
    """Return a snippet when OOMKilled events exist, else None."""
    events = get_events(namespace, limit=200)
    oom = [e for e in events if "OOM" in e or "OOMKilled" in e]
    return oom[0] if oom else None
