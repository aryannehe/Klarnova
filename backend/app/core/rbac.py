from fastapi import Depends, HTTPException, status

from app.core.security import get_current_user

ROLES = ("admin", "engineer", "viewer")


def require_roles(*allowed: str):
    allowed = set(r.lower() for r in allowed)

    def dependency(current_user: dict = Depends(get_current_user)) -> dict:
        role = (current_user.get("role") or "viewer").lower()
        if role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return current_user

    return dependency
