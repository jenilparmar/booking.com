from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_DIR = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(PROJECT_DIR / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = f"sqlite:///{(PROJECT_DIR / 'data' / 'reviews.db').as_posix()}"
    business_timezone: str = "Australia/Sydney"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

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

    @field_validator("database_url")
    @classmethod
    def _use_psycopg3_driver(cls, v: str) -> str:
        v = v.strip().strip("'\"")
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix) :]
        return v

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
