import shutil

import pytest
from fastapi.testclient import TestClient

from app.api import config as config_mod
from app.core.database import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.domain import AuditLog
from app.policy import engine as engine_mod

client = TestClient(app)


def _auth(role: str) -> dict:
    token = create_access_token({"sub": role, "role": role.capitalize()})
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def rules_file(tmp_path, monkeypatch):
    dest = tmp_path / "default.yaml"
    shutil.copy(engine_mod.RULES_PATH, dest)
    monkeypatch.setattr(engine_mod, "RULES_PATH", str(dest))
    monkeypatch.setattr(config_mod, "RULES_PATH", str(dest))
    engine_mod.load_rules.cache_clear()
    yield dest
    engine_mod.load_rules.cache_clear()


class _FakeResult:
    def scalar_one_or_none(self):
        return None


class _FakeDB:
    def __init__(self):
        self.added = []

    async def execute(self, *args, **kwargs):
        return _FakeResult()

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        return None


@pytest.fixture()
def override_db():
    fake = _FakeDB()
    app.dependency_overrides[get_db] = lambda: fake
    yield fake
    app.dependency_overrides.pop(get_db, None)


def test_policy_requires_auth():
    assert client.get("/v1/config/policy").status_code == 401


def test_policy_admin_ok(rules_file):
    res = client.get("/v1/config/policy", headers=_auth("admin"))
    assert res.status_code == 200
    body = res.json()
    assert "restart_pod" in body["whitelist"]
    assert body["actions"]["restart_pod"]["sev_3"] == "auto"
    assert body["confidence_threshold"] == 0.75


def test_policy_viewer_forbidden(rules_file):
    assert client.get("/v1/config/policy", headers=_auth("viewer")).status_code == 403


def test_update_policy_engineer_forbidden(rules_file):
    res = client.put(
        "/v1/config/policy/rules",
        json={"action": "restart_pod", "severity": "sev_3", "execution_mode": "require_approval"},
        headers=_auth("engineer"),
    )
    assert res.status_code == 403


def test_update_policy_invalid_action(rules_file):
    res = client.put(
        "/v1/config/policy/rules",
        json={"action": "rm_rf", "severity": "sev_3", "execution_mode": "auto"},
        headers=_auth("admin"),
    )
    assert res.status_code == 400


def test_update_policy_invalid_mode(rules_file):
    res = client.put(
        "/v1/config/policy/rules",
        json={"action": "restart_pod", "severity": "sev_3", "execution_mode": "always"},
        headers=_auth("admin"),
    )
    assert res.status_code == 400


def test_update_policy_persists(rules_file, override_db):
    res = client.put(
        "/v1/config/policy/rules",
        json={"action": "restart_pod", "severity": "sev_3", "execution_mode": "require_approval"},
        headers=_auth("admin"),
    )
    assert res.status_code == 200
    body = res.json()
    assert body["actions"]["restart_pod"]["sev_3"] == "require_approval"
    assert engine_mod.load_rules()["actions"]["restart_pod"]["sev_3"] == "require_approval"
    assert any(isinstance(x, AuditLog) for x in override_db.added)


def test_knowledge_sources_admin_ok():
    res = client.get("/v1/config/knowledge/sources", headers=_auth("admin"))
    assert res.status_code == 200
    body = res.json()
    assert "runbooks" in body["collections"]
    assert any(e["id"] == "runbook-oomkilled" for e in body["collections"]["runbooks"])


def test_knowledge_refresh_viewer_forbidden():
    res = client.post("/v1/config/knowledge/refresh", headers=_auth("viewer"))
    assert res.status_code == 403
