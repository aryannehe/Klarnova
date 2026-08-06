"""Application settings. Loaded from environment / .env via pydantic-settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Klarnova"
    env: str = "development"
    log_level: str = "INFO"

    # --- Database ---
    database_url: str = "postgresql+asyncpg://klarnova:klarnova@localhost:5433/klarnova"
    redis_url: str = "redis://localhost:6379/0"

    # --- Webhook (KLR-C4) ---
    webhook_token: str = "klarnova-dev-token"

    # --- Observability endpoints (discovery/fallback, KLR-C3) ---
    prometheus_url: str | None = None
    alertmanager_url: str | None = None

    # --- Monitoring agent (KLR-C5) ---
    monitoring_enabled: bool = True
    monitoring_poll_interval_seconds: int = 30
    monitoring_namespace: str | None = None

    # --- CORS ---
    cors_origins: list[str] = ["http://localhost:3000"]

    @property
    def is_incluster(self) -> bool:
        return self.env == "incluster"


@lru_cache
def get_settings() -> Settings:
    return Settings()
