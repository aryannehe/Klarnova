"""Pod log collection including previous-container (--previous) logs."""

from app.k8s.client import k8s_client


def get_pod_logs(
    name: str,
    namespace: str = "default",
    tail_lines: int = 200,
    include_previous: bool = True,
) -> str:
    """Fetch current container logs, plus previous logs when a crash occurred."""
    current = k8s_client.get_pod_logs(name, namespace, tail_lines=tail_lines)
    parts: list[str] = []

    if include_previous:
        previous = k8s_client.get_previous_pod_logs(name, namespace, tail_lines=tail_lines)
        if previous:
            parts.append(f"===== PREVIOUS CONTAINER LOGS ({name}) =====")
            parts.append(previous)

    if current and not current.startswith("Error"):
        parts.append(f"===== CURRENT LOGS ({name}) =====")
        parts.append(current)

    return "\n".join(parts)


def get_pod_logs_snippet(name: str, namespace: str = "default", tail_lines: int = 200) -> str:
    logs = get_pod_logs(name, namespace, tail_lines=tail_lines)
    return logs if logs else "(no logs available)"


def get_previous_logs(name: str, namespace: str = "default", tail_lines: int = 100) -> str | None:
    """Return only the previous container logs, or None if absent."""
    return k8s_client.get_previous_pod_logs(name, namespace, tail_lines=tail_lines)
