"""Prepare the backend for E2E: create the schema and seed users/policy/KB.

Designed to run before uvicorn in the Playwright ``webServer`` chain (with
cwd=backend), for example::

    .venv/Scripts/python ../scripts/e2e_bootstrap.py && \
    .venv/Scripts/python -m uvicorn app.main:app --port 8000

It honours an already-set ``DATABASE_URL`` (the Playwright config injects an
isolated SQLite file) and only fills in safe E2E defaults otherwise.
"""
import asyncio
import importlib.util
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
DB_FILE = BACKEND_DIR / "e2e.db"

os.environ.setdefault(
    "DATABASE_URL", "sqlite+aiosqlite:///" + str(DB_FILE).replace("\\", "/")
)
os.environ.setdefault("KB_AUTO_INGEST", "false")
os.environ.setdefault("ALERTMANAGER_WEBHOOK_TOKEN", "e2e-token")
os.environ.setdefault("JWT_SECRET", "e2e-secret")
os.environ.setdefault("KUBE_IN_CLUSTER", "false")

sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

from app.core.database import Base, engine
from app.models import domain  # noqa: F401  (registers tables on Base)


async def create_schema() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()


def load_seed_module():
    seed_path = BACKEND_DIR.parent / "scripts" / "seed.py"
    spec = importlib.util.spec_from_file_location("e2e_seed", seed_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load seed module from {seed_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> None:
    print(f"[e2e] database: {os.environ['DATABASE_URL']}")
    asyncio.run(create_schema())
    print("[e2e] schema ready")

    seed = load_seed_module()
    asyncio.run(seed.main())
    print("[e2e] seed complete")


if __name__ == "__main__":
    main()
