"""Shared plumbing for Klarnova sample microservices (KLR-B3).

Structured JSON logging, Prometheus metrics, error-rate injection, and
failure-injection endpoints used by the chaos scripts (KLR-B7).
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
import threading
import uuid
from typing import Callable

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest


def json_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)

        class _Fmt(logging.Formatter):
            def format(self, record):
                payload = {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "level": record.levelname,
                    "service": name,
                    "message": record.getMessage(),
                }
                if record.exc_info:
                    payload["exception"] = self.formatException(record.exc_info)
                return json.dumps(payload)

        handler.setFormatter(_Fmt())
        logger.addHandler(handler)
        logger.setLevel(os.getenv("LOG_LEVEL", "INFO"))
        logger.propagate = False
    return logger


REQUESTS = Counter("app_requests_total", "HTTP requests", ["app", "method", "status"])
DURATION = Histogram(
    "app_request_duration_seconds", "HTTP request latency", ["app", "method"]
)

_CPU_STOP = threading.Event()
_CPU_THREADS: list[threading.Thread] = []
_OOM_CHUNKS: list[bytes] = []


class AppState:
    def __init__(self, app: str) -> None:
        self.app = app
        self.fail_requests = False
        self.error_rate = float(os.getenv("ERROR_RATE", "0"))


def create_app(app_name: str, routes: dict[str, Callable]) -> FastAPI:
    """Build a FastAPI app with health/metrics/failure endpoints."""
    log = json_logger(app_name)
    state = AppState(app_name)

    fail_mode = os.getenv("FAIL_MODE", "").strip().lower()
    if fail_mode == "crash":
        log.critical("FAIL_MODE=crash configured; exiting on startup")
        os._exit(1)
    if fail_mode == "oom":
        log.warning("FAIL_MODE=oom configured; allocating memory")
        chunk = bytearray(64 * 1024 * 1024)
        _OOM_CHUNKS.append(chunk)
        chunk.extend(bytearray(64 * 1024 * 1024))
        _OOM_CHUNKS.append(bytes(chunk))

    app = FastAPI(title=app_name, docs_url="/docs")

    @app.middleware("http")
    async def _metrics_middleware(request, call_next):
        start = time.perf_counter()
        response = await call_next(request)
        duration = time.perf_counter() - start
        DURATION.labels(app=app_name, method=request.method).observe(duration)
        status = str(getattr(response, "status_code", 500))
        REQUESTS.labels(app=app_name, method=request.method, status=status).inc()
        return response

    @app.get("/")
    async def root():
        return {"service": app_name, "instance": uuid.uuid4().hex[:8], "time": time.time()}

    @app.get("/health")
    async def health():
        if state.fail_requests:
            return JSONResponse(status_code=503, content={"status": "degraded"})
        return {"status": "ok", "service": app_name}

    @app.get("/metrics")
    async def metrics():
        return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

    @app.post("/fail/crash")
    async def fail_crash():
        log.critical("failure injection: crash (os._exit)")
        os._exit(1)

    @app.post("/fail/oom")
    async def fail_oom():
        log.error("failure injection: oom")
        chunks = [bytes(32 * 1024 * 1024) for _ in range(16)]
        _OOM_CHUNKS.extend(chunks)
        return {"injected": "oom"}

    @app.post("/fail/cpu")
    async def fail_cpu():
        log.error("failure injection: cpu spin")
        if not _CPU_THREADS:
            for _ in range(max(1, os.cpu_count() or 2)):
                t = threading.Thread(target=_spin, daemon=True)
                t.start()
                _CPU_THREADS.append(t)
        return {"injected": "cpu"}

    @app.post("/fail/error")
    async def fail_error():
        log.error("failure injection: request failures")
        state.fail_requests = True
        return {"injected": "error"}

    @app.post("/fail/reset")
    async def fail_reset():
        state.fail_requests = False
        _CPU_STOP.set()
        _CPU_THREADS.clear()
        _OOM_CHUNKS.clear()
        log.info("failure injection reset")
        return {"injected": "reset"}

    async def _business(name: str, handler: Callable):
        if state.fail_requests or (state.error_rate and _roll_error(state.error_rate)):
            REQUESTS.labels(app=app_name, method="GET", status="500").inc()
            return JSONResponse(status_code=500, content={"error": "injected failure"})
        return handler()

    for path, handler in routes.items():
        app.add_api_route(path, lambda h=handler, n=path: _business(n, h), methods=["GET"])

    return app


def _spin() -> None:
    while not _CPU_STOP.is_set():
        _ = sum(range(1000))


def _roll_error(rate: float) -> bool:
    import random

    return random.random() < rate
