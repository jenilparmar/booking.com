from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


def normalize_db_url(v: str | None) -> str | None:
    if v is None:
        return None
    v = v.strip().strip("'\"")
    if not v:
        return None
    for prefix in ("postgres://", "postgresql://"):
        if v.startswith(prefix):
            return "postgresql+psycopg://" + v[len(prefix) :]
    return v


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Neon pooled connection string (pgbouncer) for the running app.
    database_url: str = "postgresql+psycopg://localhost:5432/reviews"
    # Neon non-pooled connection string for Alembic. Falls back to database_url.
    direct_database_url: str | None = None
    # Throwaway database used by pytest. Must differ from database_url.
    test_database_url: str | None = None

    db_pool_size: int = 5
    db_max_overflow: int = 5
    db_connect_retries: int = 3

    business_timezone: str = "Australia/Sydney"
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    rating_scale_min: float = 1.0
    rating_scale_max: float = 10.0

    import_max_bytes: int = 5 * 1024 * 1024
    import_max_rows: int = 50_000

    collector_adapter: str = "manual"
    collector_timeout_seconds: float = 15.0
    collector_max_retries: int = 3
    collector_backoff_base_seconds: float = 1.0
    collector_rate_limit_per_minute: int = 10

    api_max_page_size: int = 100

    @field_validator("database_url", "direct_database_url", "test_database_url", mode="before")
    @classmethod
    def _normalize_urls(cls, v: str | None) -> str | None:
        return normalize_db_url(v)

    @property
    def migration_database_url(self) -> str:
        return self.direct_database_url or self.database_url

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
