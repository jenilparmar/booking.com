import logging
import time
from collections.abc import Iterator
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, create_engine, event
from sqlalchemy.engine import Dialect, Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import TypeDecorator

from app.config import get_settings

log = logging.getLogger(__name__)


class UTCDateTime(TypeDecorator[datetime]):
    """timestamptz column that only accepts aware datetimes and always returns UTC."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            raise ValueError("naive datetimes are not allowed; attach a timezone")
        return value.astimezone(UTC)

    def process_result_value(self, value: datetime | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)
        return value.astimezone(UTC)


class Base(DeclarativeBase):
    pass


def make_engine(url: str, *, pooled: bool | None = None) -> Engine:
    """Create an engine tuned for Neon.

    Pooled (pgbouncer, transaction mode) endpoints cannot hold server-side prepared statements
    across transactions, so psycopg's auto-prepare is disabled for them. Connections are recycled
    well within Neon's idle timeout and pre-pinged so a suspended compute is reconnected
    transparently; the initial connect is retried to absorb cold starts.
    """
    settings = get_settings()
    if pooled is None:
        pooled = "-pooler." in url
    connect_args: dict[str, Any] = {"connect_timeout": 15}
    if pooled:
        connect_args["prepare_threshold"] = None
    engine = create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_max_overflow,
        pool_recycle=240,
    )
    retries = max(1, settings.db_connect_retries)

    @event.listens_for(engine, "do_connect")
    def _connect_with_retry(
        dialect: Dialect, _rec: Any, cargs: tuple[Any, ...], cparams: dict[str, Any]
    ) -> Any:
        for attempt in range(1, retries + 1):
            try:
                return dialect.loaded_dbapi.connect(*cargs, **cparams)
            except Exception as exc:  # psycopg.OperationalError on cold start / network blip
                if attempt == retries:
                    raise OperationalError("connect", {}, exc) from exc
                delay = 0.5 * 2 ** (attempt - 1)
                log.warning("DB connect failed (attempt %s/%s); retrying", attempt, retries)
                time.sleep(delay)
        raise AssertionError("unreachable")

    return engine


engine = make_engine(get_settings().database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
