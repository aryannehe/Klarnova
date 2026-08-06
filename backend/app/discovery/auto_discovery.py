"""Auto-Discovery implementation (KLR-C3)."""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_PROMETHEUS_SERVICE_NAME_PATTERNS = (
    "prometheus-kube-prometheus-stack-prometheus",
    "kube-prometheus-stack-prometheus",
    "prometheus-operated",
    "prometheus",
)
_ALERTMANAGER_SERVICE_NAME_PATTERNS = (
    "alertmanager-operated",
    "kube-prometheus-stack-alertmanager",
    "prometheus-kube-prometheus-stack-alertmanager",
    "alertmanager",
)


def detect_kube_mode() -> bool:
    """True when running inside a cluster (service account present)."""
    if os.getenv("KUBERNETES_SERVICE_HOST") and os.getenv("KUBERNETES_SERVICE_PORT"):
        return True
    sa_path = "/var/run/secrets/kubernetes.io/serviceaccount"
    return bool(os.name != "nt" and os.path.isdir(sa_path))


def _discover_service_url(
    name_patterns: tuple[str, ...], port: int, protocol: str = "http"
) -> str | None:
    from app.k8s.client import KubernetesClient

    try:
        client = KubernetesClient(in_cluster=detect_kube_mode())
        namespaces = client.list_namespaces()
    except Exception as exc:  # pragma: no cover - environment dependent
        logger.warning("Discovery: could not reach K8s API: %s", exc)
        return None

    for namespace in namespaces:
        try:
            services = client.core.list_namespaced_service(namespace).items
        except Exception:  # pragma: no cover
            continue
        for svc in services:
            name = svc.metadata.name
            if any(name.startswith(p) for p in name_patterns):
                host = f"{name}.{namespace}.svc"
                logger.info("Discovery: found %s at %s://%s:%s", name, protocol, host, port)
                return f"{protocol}://{host}:{port}"
    return None


def discover_prometheus_url() -> str:
    url = os.getenv("PROMETHEUS_URL")
    if url:
        return url
    discovered = _discover_service_url(_PROMETHEUS_SERVICE_NAME_PATTERNS, 9090)
    if discovered:
        return discovered
    logger.info("Discovery: no Prometheus service found, defaulting to localhost:9090")
    return "http://localhost:9090"


def discover_alertmanager_url() -> str:
    url = os.getenv("ALERTMANAGER_URL")
    if url:
        return url
    discovered = _discover_service_url(_ALERTMANAGER_SERVICE_NAME_PATTERNS, 9093)
    if discovered:
        return discovered
    logger.info("Discovery: no Alertmanager service found, defaulting to localhost:9093")
    return "http://localhost:9093"
