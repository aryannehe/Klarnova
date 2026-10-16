"""HTTP-level authentication and RBAC tests.

The suite previously tested JWT helpers in isolation; these drive the real
``/v1/auth`` endpoints against the database.
"""
from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.domain import User


async def _seed_user(username: str, password: str, role: str) -> None:
    async with SessionLocal() as session:
        session.add(
            User(
                username=username,
                hashed_password=hash_password(password),
                role=role,
            )
        )
        await session.commit()


async def test_login_success_returns_token(api):
    await _seed_user("admin", "admin123", "Admin")
    res = await api.post(
        "/v1/auth/login", data={"username": "admin", "password": "admin123"}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"


async def test_login_wrong_password_unauthorized(api):
    await _seed_user("admin", "admin123", "Admin")
    res = await api.post(
        "/v1/auth/login", data={"username": "admin", "password": "nope"}
    )
    assert res.status_code == 401


async def test_login_unknown_user_unauthorized(api):
    res = await api.post(
        "/v1/auth/login", data={"username": "ghost", "password": "whatever"}
    )
    assert res.status_code == 401


async def test_me_requires_and_decodes_token(api, auth):
    res = await api.get("/v1/auth/me", headers=auth("engineer"))
    assert res.status_code == 200
    assert res.json()["username"] == "engineer"
    assert res.json()["role"] == "Engineer"


async def test_me_without_token_is_unauthorized(api):
    assert (await api.get("/v1/auth/me")).status_code == 401


async def test_protected_endpoint_without_token_is_unauthorized(api):
    assert (await api.get("/v1/incidents")).status_code == 401
