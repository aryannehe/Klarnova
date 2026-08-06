"""Auto-Discovery & Auto-Configuration module (KLR-C3).

Detects the Kubernetes API, Prometheus, and Alertmanager and self-configures.
Detection order is always: explicit env override → cluster discovery → default fallback.
"""

from app.discovery.auto_discovery import (
    detect_kube_mode,
    discover_alertmanager_url,
    discover_prometheus_url,
)

__all__ = ["detect_kube_mode", "discover_alertmanager_url", "discover_prometheus_url"]
