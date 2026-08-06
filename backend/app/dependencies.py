"""Shared FastAPI dependencies."""

from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, Query, status

from app.config import get_settings


def require_webhook_token(
    x_klarnova_token: str | None = Header(default=None),
    token: str | None = Query(default=None),
) -> None:
    """Validate the shared webhook token (Security doc §3.4, KLR-C4).

    Primary transport is the X-Klarnova-Token header; a `token` query param is
    accepted as a fallback because the AlertmanagerConfig CRD cannot set
    custom headers on webhook receivers.
    """
    settings = get_settings()
    provided = x_klarnova_token or token or ""
    if not provided or not hmac.compare_digest(provided, settings.webhook_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid webhook token"
        )
