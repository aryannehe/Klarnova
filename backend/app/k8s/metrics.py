"""Prometheus query wrapper (KLR-C2) — thin client over the HTTP API.

Uses httpx for async access. Endpoints used in Phase 1:
  - GET /api/v1/query        (instant queries, e.g. ALERTS)
  - GET /api/v1/query_range  (trend data)
  - GET /api/v1/alerts       (active alerts)
  - GET /api/v1/rules        (recording + alert rules)
"""

from __future__ import annotations

import httpx


class PrometheusError(RuntimeError):
    pass


class PrometheusClient:
    def __init__(self, base_url: str, *, timeout: float = 10.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _get(self, path: str, params: dict | None = None) -> dict:
        try:
            resp = httpx.get(
                f"{self.base_url}{path}", params=params, timeout=self.timeout, follow_redirects=True
            )
        except httpx.HTTPError as exc:  # pragma: no cover - network dependent
            raise PrometheusError(f"Prometheus unreachable at {self.base_url}: {exc}") from exc
        resp.raise_for_status()
        body = resp.json()
        if body.get("status") != "success":
            raise PrometheusError(f"Prometheus API error: {body.get('error')}")
        return body["data"]

    def query(self, expr: str, time: str | None = None) -> list[dict]:
        """Instant vector query. Returns list of {metric, value}."""
        params = {"query": expr}
        if time:
            params["time"] = time
        data = self._get("/api/v1/query", params)
        return _normalise_result(data.get("result", []))

    def query_range(self, expr: str, start: str, end: str, step: str) -> list[dict]:
        data = self._get(
            "/api/v1/query_range",
            {"query": expr, "start": start, "end": end, "step": step},
        )
        return _normalise_result(data.get("result", []))

    def active_alerts(self) -> list[dict]:
        data = self._get("/api/v1/alerts")
        return data.get("alerts", [])

    def firing_alerts(self) -> list[dict]:
        """Alerts currently firing, as {name, labels, annotations, startsAt, fingerprint}."""
        result = []
        for alert in self.active_alerts():
            if alert.get("state") != "firing":
                continue
            result.append(
                {
                    "name": alert.get("labels", {}).get("alertname"),
                    "labels": alert.get("labels", {}),
                    "annotations": alert.get("annotations", {}),
                    "starts_at": alert.get("startsAt"),
                    "fingerprint": alert.get("fingerprint"),
                }
            )
        return result


def _normalise_result(result: list[dict]) -> list[dict]:
    """Prometheus result vector → [{metric, value}] with parsed floats."""
    out = []
    for item in result:
        metric = item.get("metric", {})
        raw = item.get("value", [None, "0"])[1]
        out.append({"metric": metric, "value": float(raw)})
    return out


_URL: str | None = None


def set_prometheus_url(url: str) -> None:
    global _URL
    _URL = url


def get_prometheus_url() -> str:
    """Resolve Prometheus base URL: env override → discovery → default."""
    if _URL:
        return _URL
    from app.config import get_settings
    from app.discovery.auto_discovery import discover_prometheus_url

    settings = get_settings()
    url = settings.prometheus_url or discover_prometheus_url()
    set_prometheus_url(url)
    return url
