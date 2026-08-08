"""
Application configuration for SentinelScan Cloud's backend.

Values are read from environment variables (or a local .env file during
development), never hard-coded, per the deployment architecture in
Section 16 of the approved architecture (secrets management; environment
separation between staging and production).
"""
from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Application ---
    app_name: str = "SentinelScan Cloud"
    environment: str = "development"  # development | staging | production
    debug: bool = False

    # --- Database (Section 7: PostgreSQL) ---
    # Async URL is used by the application (asyncpg driver); Alembic uses
    # the sync URL (psycopg2 driver) since Alembic's migration runner is
    # synchronous. Both point at the same database.
    database_url: str = "postgresql+asyncpg://sentinelscan_cloud:sentinelscan_cloud@localhost:5432/sentinelscan_cloud_dev"
    database_url_sync: str = "postgresql+psycopg2://sentinelscan_cloud:sentinelscan_cloud@localhost:5432/sentinelscan_cloud_dev"

    # --- Auth (Section 7: OAuth2/JWT) ---
    jwt_secret_key: str = "CHANGE-ME-IN-PRODUCTION-VIA-ENV-VAR"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # --- Object storage (Section 7: S3-compatible) ---
    object_storage_endpoint: str | None = None
    object_storage_bucket: str = "sentinelscan-cloud-reports"

    # --- Threat Intelligence (Stage 8) ---
    nvd_enabled: bool = True
    epss_enabled: bool = True
    kev_enabled: bool = True
    mitre_attack_enabled: bool = True
    threat_intel_http_timeout_seconds: float = 15.0
    threat_intel_cache_ttl_seconds: float = 300.0
    threat_intel_max_retries: int = 3

    # --- Background jobs (Section 7: task queue backed by Redis or equivalent) ---
    job_queue_broker_url: str = "redis://localhost:6379/0"


@lru_cache
def get_settings() -> Settings:
    """Cached settings accessor -- the app should always go through this,
    never instantiate Settings() directly, so configuration is read once
    per process."""
    return Settings()
