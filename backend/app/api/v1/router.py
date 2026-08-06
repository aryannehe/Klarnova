"""API v1 router."""

from fastapi import APIRouter

from app.api.v1.endpoints import health, incidents, webhooks

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(incidents.router, prefix="/incidents", tags=["incidents"])
api_router.include_router(webhooks.router, prefix="/webhooks", tags=["webhooks"])
