import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.approval import router as approval_router
from .api.auth import router as auth_router
from .api.config import router as config_router
from .api.incidents import router as incidents_router
from .api.kubernetes import router as k8s_router
from .api.webhooks import router as webhooks_router
from .config import settings

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    ingest_task: asyncio.Task | None = None

    async def _ingest_once() -> None:
        try:
            from .rag.ingest import run_ingest

            count = await asyncio.to_thread(run_ingest)
            logger.info("knowledge base ingest: %d document(s) added", count)
        except Exception as exc:
            logger.warning("knowledge base ingest failed (non-fatal): %s", exc)

    try:
        from .bandit.learning import seed_bandit_from_db

        await seed_bandit_from_db()
    except Exception as exc:
        logger.warning("bandit seed failed (non-fatal): %s", exc)

    async def periodic_refresh() -> None:
        while True:
            await _ingest_once()
            await asyncio.sleep(settings.KB_REFRESH_INTERVAL)

    if settings.KB_AUTO_INGEST:
        if settings.KB_REFRESH_INTERVAL > 0:
            ingest_task = asyncio.create_task(periodic_refresh())
        else:
            await _ingest_once()

    yield

    if ingest_task is not None:
        ingest_task.cancel()

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(k8s_router, prefix=f"{settings.API_V1_STR}/kubernetes", tags=["kubernetes"])
app.include_router(webhooks_router, prefix=f"{settings.API_V1_STR}/webhooks", tags=["webhooks"])
app.include_router(approval_router, prefix=f"{settings.API_V1_STR}/actions", tags=["actions"])
app.include_router(incidents_router, prefix=f"{settings.API_V1_STR}/incidents", tags=["incidents"])
app.include_router(auth_router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(config_router, prefix=f"{settings.API_V1_STR}/config", tags=["config"])

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/ready")
async def readiness_check():
    return {"status": "ready"}
