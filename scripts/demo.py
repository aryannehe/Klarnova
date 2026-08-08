"""Drive the full Klarnova demo loop against the in-cluster backend.

Flow:
  1. login as admin
  2. wait for the injected CrashLoopBackOff incident to arrive (Alertmanager -> webhook)
  3. print the investigation trace
  4. approve an operator-override rollback of the catalogue deployment
  5. poll until the incident is Resolved
  6. show the bandit policy row that was learned
"""
import asyncio
import os
import sys
import time
from pathlib import Path

BASE = "http://localhost:8000"

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(BACKEND_DIR)

from dotenv import load_dotenv

load_dotenv(BACKEND_DIR / ".env")

try:
    import httpx
except ImportError:
    httpx = None


def client():
    if httpx is None:
        raise SystemExit("httpx not installed in the backend venv")
    return httpx.Client(timeout=30, base_url=BASE)


def login(c: httpx.Client) -> str:
    r = c.post(
        "/v1/auth/login",
        data={"username": "admin", "password": "admin123"},
    )
    r.raise_for_status()
    return r.json()["access_token"]


def wait_for_incident(c: httpx.Client, token: str, timeout: float = 240.0) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = c.get("/v1/incidents", headers=headers)
        r.raise_for_status()
        incidents = r.json()
        crash = [
            inc
            for inc in incidents
            if inc.get("alert_name") == "KubePodCrashLooping"
            and inc.get("namespace") == "sock-shop"
            and inc.get("status") not in ("Resolved", "Escalated")
        ]
        if crash:
            crash.sort(key=lambda i: i.get("detected_at") or "", reverse=True)
            print(f"[demo] incident #{crash[0]['id']} created: {crash[0]['status']}")
            return crash[0]
        print("[demo] waiting for incident...")
        time.sleep(10)
    raise SystemExit("Timed out waiting for the CrashLoopBackOff incident")


def show_trace(c: httpx.Client, token: str, incident_id: int):
    headers = {"Authorization": f"Bearer {token}"}
    r = c.get(f"/v1/incidents/{incident_id}/trace", headers=headers)
    r.raise_for_status()
    data = r.json()
    print(f"[demo] root cause: {data['incident'].get('root_cause', '')[:240]}")
    for run in data["agent_runs"]:
        print(f"  agent={run['agent']:<12} -> {str(run['outputs'])[:150]}")


def approve(c: httpx.Client, token: str, incident_id: int):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "incident_id": str(incident_id),
        "action_type": "rollback_deployment",
        "approved": True,
        "target_resource": "catalogue",
        "namespace": "sock-shop",
    }
    r = c.post("/v1/actions/approve", json=body, headers=headers)
    r.raise_for_status()
    print(f"[demo] approved operator override: rollback_deployment on catalogue -> {r.json()}")


def poll_resolution(c: httpx.Client, token: str, incident_id: int, timeout: float = 90.0) -> dict:
    headers = {"Authorization": f"Bearer {token}"}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = c.get(f"/v1/incidents/{incident_id}", headers=headers)
        r.raise_for_status()
        inc = r.json()
        if inc["status"] in ("Resolved", "Escalated"):
            print(f"[demo] final status: {inc['status']}")
            return inc
        print(f"[demo] status={inc['status']} ...")
        time.sleep(5)
    raise SystemExit("Timed out waiting for resolution")


def show_bandit_policy():
    from app.core.database import SessionLocal
    from app.models.domain import BanditPolicy
    from sqlalchemy import select

    async def _q():
        async with SessionLocal() as session:
            rows = (
                await session.execute(select(BanditPolicy))
            ).scalars().all()
            return [
                {"category": r.incident_category, "action": r.action, "reward": r.reward, "count": r.update_count}
                for r in rows
            ]

    rows = asyncio.run(_q())
    print("[demo] bandit policy rows:")
    for row in rows:
        print(f"  category={row['category']:<24} action={row['action']:<18} reward={row['reward']:.3f} updates={row['count']}")


def main():
    c = client()
    token = login(c)
    print("[demo] logged in as admin (token OK)")
    incident = wait_for_incident(c, token)
    show_trace(c, token, incident["id"])
    approve(c, token, incident["id"])
    final = poll_resolution(c, token, incident["id"])
    if final["status"] == "Resolved":
        show_trace(c, token, incident["id"])
        print("[demo] INCIDENT RESOLVED (see remediation step in trace above)")
    show_bandit_policy()
    c.close()


if __name__ == "__main__":
    main()
