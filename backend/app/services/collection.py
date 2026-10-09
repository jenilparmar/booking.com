"""Collection adapters, retry/backoff, and CollectionRun lifecycle.

Booking.com's Terms prohibit automated access (docs/COLLECTION.md), so the only adapter shipped
is ``ManualAdapter``, which reports itself as unsupported. The machinery below (retries, rate
limiting, run logging, dedup on insert) is ready for an adapter backed by an official feed or
written permission. Do not add scraping, CAPTCHA solving, or anti-bot evasion.
"""

import logging
import random
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, ClassVar, Protocol

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.models import CollectionRun, Property
from app.services.importer import insert_reviews, normalize_row
from app.services.normalize import FieldError

log = logging.getLogger(__name__)


class CollectionUnsupportedError(Exception):
    def __init__(self, adapter: str, reason: str) -> None:
        super().__init__(reason)
        self.adapter = adapter
        self.reason = reason


class TransientFetchError(Exception):
    """Retryable failure (timeout, 5xx, connection reset)."""


class PermanentFetchError(Exception):
    """Non-retryable failure (bad credentials, 4xx, forbidden)."""


class PartialFetchError(Exception):
    """Some items were fetched before the source failed. Items are kept."""

    def __init__(self, message: str, items: Sequence[dict[str, Any]]) -> None:
        super().__init__(message)
        self.items = list(items)


class CollectorAdapter(Protocol):
    name: str
    supported: bool
    unsupported_reason: str

    def fetch(
        self, property_id: str, source_url: str | None, timeout: float
    ) -> list[dict[str, Any]]:
        """Return raw review dicts using the importer's field names."""
        ...


class ManualAdapter:
    name = "manual"
    supported = False
    unsupported_reason = (
        "Live collection is disabled: Booking.com's Terms of Service prohibit automated access. "
        "Export reviews and upload them via POST /api/import/reviews instead."
    )

    def fetch(
        self, property_id: str, source_url: str | None, timeout: float
    ) -> list[dict[str, Any]]:
        raise CollectionUnsupportedError(self.name, self.unsupported_reason)


ADAPTERS: dict[str, Callable[[], CollectorAdapter]] = {"manual": ManualAdapter}


def get_adapter(name: str | None = None) -> CollectorAdapter:
    key = (name or get_settings().collector_adapter).lower()
    factory = ADAPTERS.get(key)
    if factory is None:
        raise CollectionUnsupportedError(key, f"Unknown collector adapter {key!r}.")
    return factory()


@dataclass
class RetryPolicy:
    max_retries: int = 3
    backoff_base: float = 1.0
    backoff_cap: float = 30.0
    timeout: float = 15.0

    @classmethod
    def from_settings(cls, s: Settings) -> "RetryPolicy":
        return cls(
            max_retries=s.collector_max_retries,
            backoff_base=s.collector_backoff_base_seconds,
            timeout=s.collector_timeout_seconds,
        )

    def delay(self, attempt: int, rng: random.Random) -> float:
        """Full-jitter exponential backoff: uniform(0, min(cap, base * 2**(attempt-1)))."""
        return rng.uniform(0, min(self.backoff_cap, self.backoff_base * 2 ** (attempt - 1)))


class RateLimiter:
    """Process-wide minimum spacing between adapter calls."""

    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.interval = 60.0 / per_minute if per_minute > 0 else 0.0
        self._clock = clock
        self._last: float | None = None

    def wait_time(self) -> float:
        with self._lock:
            now = self._clock()
            if self._last is None or self.interval == 0:
                self._last = now
                return 0.0
            wait = max(0.0, self._last + self.interval - now)
            self._last = now + wait
            return wait


@dataclass
class FetchOutcome:
    items: list[dict[str, Any]] = field(default_factory=list)
    attempts: int = 0
    error: str | None = None
    partial: bool = False


def fetch_with_retry(
    adapter: CollectorAdapter,
    property_id: str,
    source_url: str | None,
    policy: RetryPolicy,
    *,
    sleep: Callable[[float], None] = time.sleep,
    rate_limiter: RateLimiter | None = None,
    rng: random.Random | None = None,
) -> FetchOutcome:
    rng = rng or random.Random()
    out = FetchOutcome()
    total_attempts = policy.max_retries + 1
    for attempt in range(1, total_attempts + 1):
        out.attempts = attempt
        if rate_limiter:
            wait = rate_limiter.wait_time()
            if wait:
                sleep(wait)
        try:
            out.items = list(adapter.fetch(property_id, source_url, policy.timeout))
            out.error = None
            return out
        except PartialFetchError as exc:
            out.items = exc.items
            out.partial = True
            out.error = _safe_message(exc)
            return out
        except PermanentFetchError as exc:
            out.error = _safe_message(exc)
            return out
        except (TransientFetchError, TimeoutError, ConnectionError) as exc:
            out.error = _safe_message(exc)
            if attempt < total_attempts:
                d = policy.delay(attempt, rng)
                log.info(
                    "collector %s attempt %s failed; retrying in %.2fs", adapter.name, attempt, d
                )
                sleep(d)
    out.error = f"gave up after {out.attempts} attempts: {out.error}"
    return out


def _safe_message(exc: BaseException) -> str:
    """Short single-line message: no tracebacks, truncated, credentials stripped from URLs."""
    import re

    msg = str(exc).splitlines()[0] if str(exc) else exc.__class__.__name__
    msg = re.sub(r"://[^/@\s]+@", "://***@", msg)
    return msg[:300]


def run_collection(
    db: Session,
    property_id: str,
    adapter: CollectorAdapter | None = None,
    *,
    policy: RetryPolicy | None = None,
    sleep: Callable[[float], None] = time.sleep,
    rate_limiter: RateLimiter | None = None,
    rng: random.Random | None = None,
    now: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> CollectionRun:
    """Run one collection for a property and record a CollectionRun.

    Status: ``success`` when the fetch completed (even with zero new reviews), ``partial`` when
    the fetch was cut short or some items were invalid, ``failed`` when nothing could be fetched.
    A failed run never deletes or modifies existing reviews.
    """
    settings = get_settings()
    adapter = adapter or get_adapter()
    if not adapter.supported:
        raise CollectionUnsupportedError(adapter.name, adapter.unsupported_reason)
    prop = db.get(Property, property_id)
    if prop is None:
        raise LookupError(property_id)
    policy = policy or RetryPolicy.from_settings(settings)
    if rate_limiter is None:
        rate_limiter = RateLimiter(settings.collector_rate_limit_per_minute)

    run = CollectionRun(
        property_id=property_id, adapter=adapter.name, started_at=now(), status="running"
    )
    db.add(run)
    db.commit()

    outcome = fetch_with_retry(
        adapter,
        property_id,
        prop.source_url,
        policy,
        sleep=sleep,
        rate_limiter=rate_limiter,
        rng=rng,
    )
    run.discovered_count = len(outcome.items)
    errors: list[str] = []
    if outcome.error:
        errors.append(outcome.error)

    valid: list[dict[str, Any]] = []
    known = {property_id}
    ts = now()
    for i, raw in enumerate(outcome.items, start=1):
        raw = {**raw, "property_id": property_id}
        try:
            valid.append(
                normalize_row(raw, known_properties=known, default_source="import", now=ts)
            )
        except FieldError as fe:
            run.error_count += 1
            if len(errors) < 6:
                errors.append(f"item {i}: {fe.field}: {fe.message}")
    for row in valid:
        row["source"] = "live"

    try:
        inserted = insert_reviews(db, valid)[property_id] if valid else 0
        run.inserted_count = inserted
        run.duplicate_count = len(valid) - inserted
        if outcome.error and not outcome.items:
            run.status = "failed"
            run.error_count = max(run.error_count, 1)
        elif outcome.partial or run.error_count:
            run.status = "partial"
        else:
            run.status = "success"
        run.error_summary = "; ".join(errors) or None
        run.finished_at = now()
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        run.status = "failed"
        run.inserted_count = 0
        run.duplicate_count = 0
        run.error_count = max(run.error_count, 1)
        run.error_summary = "Database write failed; no reviews from this run were saved."
        run.finished_at = now()
        db.commit()
    return run


def latest_runs(db: Session, limit: int = 50) -> list[CollectionRun]:
    return list(
        db.scalars(select(CollectionRun).order_by(CollectionRun.started_at.desc()).limit(limit))
    )
