"""Shared pytest fixtures for the Klarnova backend suite.

Two concerns live here:

1. **A real (SQLite) database.** The production app talks to Postgres via the
   module-level ``SessionLocal`` sessionmaker. We point that sessionmaker at a
   throwaway SQLite file so the API integration tests exercise the real models,
   routers and background pipeline instead of hand-rolled fakes. ``NullPool``
   keeps every connection loop-local, so pytest-asyncio's per-test event loops
   never share an aiosqlite connection.

2. **A mock cluster + deterministic diagnosis.** The incident pipeline reaches
   for the Kubernetes API and the LLM. Both are swapped for the scenario-aware
   ``MockCluster`` and the deterministic diagnosis fallback so the full
   webhook -> investigate -> approve -> remediate -> validate flow runs
   offline and deterministically.
"""
import asyncio
import csv
from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.ablation import ablation
from app.core.database import Base, SessionLocal, get_db
from app.core.database import engine as _prod_engine  # noqa: F401  (import to bind models)
from app.main import app
from tests.mock_cluster import (
    MockCluster,
    fast_validation,
    force_fallback_llm,
    install_mock,
    real_validation,
    restore_mock,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SCENARIOS_PATH = REPO_ROOT / "chaos-testing" / "scenarios.yaml"

_ABLATION_FIELDS = (
    "disable_rag",
    "disable_validation",
    "disable_safety",
    "disable_planning",
    "disable_bandit",
)


# --- Database ----------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _configure_db(tmp_path_factory):
    """Bind the shared ``SessionLocal`` sessionmaker to a throwaway SQLite file."""
    db_path = tmp_path_factory.mktemp("klarnova-db") / "test.db"
    test_engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_path}",
        poolclass=NullPool,
        future=True,
    )

    async def _create_schema():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_schema())
    SessionLocal.configure(bind=test_engine)

    async def _override_get_db():
        async with SessionLocal() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    yield test_engine
    app.dependency_overrides.pop(get_db, None)
    asyncio.run(test_engine.dispose())


@pytest.fixture(autouse=True)
def _clean_db(_configure_db):
    """Start every test with empty tables."""

    async def _wipe():
        async with _configure_db.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(table.delete())

    asyncio.run(_wipe())
    yield


@pytest.fixture(autouse=True)
def _reset_ablation():
    for field in _ABLATION_FIELDS:
        setattr(ablation, field, False)
    yield
    for field in _ABLATION_FIELDS:
        setattr(ablation, field, False)


# --- HTTP client -------------------------------------------------------------

@pytest.fixture
async def api():
    """Async HTTP client driving the real FastAPI app in-process."""
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# --- Auth helper -------------------------------------------------------------

@pytest.fixture
def auth():
    from app.core.security import create_access_token

    def _headers(role: str = "admin") -> dict:
        token = create_access_token({"sub": role, "role": role.capitalize()})
        return {"Authorization": f"Bearer {token}"}

    return _headers


# --- Scenarios + mock pipeline ----------------------------------------------

@pytest.fixture(scope="session")
def scenarios() -> dict[str, dict]:
    with open(SCENARIOS_PATH, encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    return {s["id"]: s for s in data.get("scenarios", [])}


@pytest.fixture
def pipeline():
    """Install the mock cluster + deterministic diagnosis for one scenario.

    Returns a factory: ``cluster = pipeline(scenarios["S1"])``.
    The diagnosis fallback is restored afterwards so later tests can still
    stub the LLM themselves.
    """
    from app.agents import root_cause

    installed: dict = {}
    original_diagnose = root_cause._diagnose_with_llm

    def _install(scenario: dict) -> MockCluster:
        cluster = MockCluster(scenario)
        installed["pairs"] = install_mock(cluster)
        force_fallback_llm()
        fast_validation()
        return cluster

    yield _install
    restore_mock(installed.get("pairs", []))
    root_cause._diagnose_with_llm = original_diagnose
    real_validation()


# --- CSV result reporting (test-reports/backend-tests.csv) -------------------

_CSV_PATH = REPO_ROOT / "test-reports" / "backend-tests.csv"
_results: dict[str, dict] = {}


def pytest_runtest_logreport(report):
    """Record one row per test (outcome/duration/error) for analysis."""
    try:
        path, lineno, _ = report.location
        row = _results.setdefault(
            report.nodeid,
            {
                "test_id": report.nodeid,
                "file": path,
                "line": lineno,
                "outcome": "",
                "duration_ms": 0.0,
                "markers": "",
                "error": "",
            },
        )
        if report.when == "call" or row["outcome"] in ("", "passed", "skipped"):
            row["outcome"] = report.outcome
            row["duration_ms"] = round(report.duration * 1000, 1)
        if report.outcome != "passed":
            row["error"] = (getattr(report, "longreprtext", "") or "").replace(
                "\n", " | "
            )
        keywords = report.keywords or {}
        row["markers"] = ",".join(
            k
            for k in keywords
            if k not in ("nodeid", "module", "file", "class", "keywords")
            and k[0].isalpha()
        )
    except Exception:  # pragma: no cover - reporting must never fail tests
        pass


def pytest_sessionfinish(session, exitstatus):
    try:
        _CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(_CSV_PATH, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(
                fh,
                fieldnames=[
                    "timestamp",
                    "test_id",
                    "file",
                    "line",
                    "outcome",
                    "duration_ms",
                    "markers",
                    "error",
                ],
            )
            writer.writeheader()
            stamp = datetime.now(UTC).isoformat(timespec="seconds")
            for row in _results.values():
                writer.writerow({**row, "timestamp": stamp})
    except Exception:  # pragma: no cover
        pass
