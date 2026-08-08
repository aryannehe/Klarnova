import pytest
from fastapi import HTTPException
from jose import jwt

from app.config import settings
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)


def test_password_hash_roundtrip():
    hashed = hash_password("s3cret")
    assert hashed != "s3cret"
    assert verify_password("s3cret", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_token_roundtrip():
    token = create_access_token({"sub": "admin", "role": "Admin"})
    payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
    assert payload["sub"] == "admin"
    assert payload["role"] == "Admin"
    assert "exp" in payload


@pytest.mark.asyncio
async def test_get_current_user():
    token = create_access_token({"sub": "eng", "role": "Engineer"})
    user = await get_current_user(token=token)
    assert user == {"username": "eng", "role": "Engineer"}


@pytest.mark.asyncio
async def test_get_current_user_rejects_garbage():
    with pytest.raises(HTTPException):
        await get_current_user(token="not-a-jwt")
