from datetime import UTC, datetime, timedelta

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login")

CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(data: dict, expires_minutes: int | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(
        minutes=expires_minutes or settings.JWT_EXPIRY
    )
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.JWT_SECRET, algorithm=settings.ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.ALGORITHM])
        username: str | None = payload.get("sub")
        role: str | None = payload.get("role")
        if username is None or role is None:
            raise CREDENTIALS_EXCEPTION
    except JWTError:
        raise CREDENTIALS_EXCEPTION from None
    return {"username": username, "role": role}
