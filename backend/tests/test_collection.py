import random
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CollectionRun, Review
from app.services.collection import (
    CollectionUnsupportedError,
    ManualAdapter,
    PartialFetchError,
    PermanentFetchError,
    RateLimiter,
    RetryPolicy,
    TransientFetchError,
    fetch_with_retry,
    get_adapter,
    run_collection,
)
from app.services.importer import import_file
from tests.conftest import FIXTURES

PROP = "olympic-paddington"


def item(n: int, **kw: Any) -> dict[str, Any]:
    return {
        "source_review_id": f"LIVE-{n}",
        "review_text": f"Review number {n}, clean room.",
        "rating": 8,
        "published_at": "2026-10-05T10:00:00+11:00",
        **kw,
    }


class FakeAdapter:
    name = "fake"
    supported = True
    unsupported_reason = ""

    def __init__(self, script: list[Any]) -> None:
        self.script = list(script)
        self.calls = 0

    def fetch(self, property_id: str, source_url: str | None, timeout: float) -> list[dict]:
        self.calls += 1
        step = self.script.pop(0)
        if isinstance(step, BaseException):
            raise step
        return step


class SleepRecorder:
    def __init__(self) -> None:
        self.calls: list[float] = []

    def __call__(self, s: float) -> None:
        self.calls.append(s)


POLICY = RetryPolicy(max_retries=3, backoff_base=1.0, timeout=5)
NO_LIMIT = RateLimiter(0)


def count(db: Session, model: type) -> int:
    return db.scalar(select(func.count()).select_from(model)) or 0


def test_manual_adapter_is_unsupported(db: Session) -> None:
    adapter = get_adapter("manual")
    assert isinstance(adapter, ManualAdapter) and not adapter.supported
    with pytest.raises(CollectionUnsupportedError) as exc:
        run_collection(db, PROP, adapter)
    assert "Terms of Service" in exc.value.reason
    assert count(db, CollectionRun) == 0


def test_unknown_adapter_name() -> None:
    with pytest.raises(CollectionUnsupportedError):
        get_adapter("headless-scraper")


def test_retry_then_success(db: Session) -> None:
    adapter = FakeAdapter(
        [TransientFetchError("timeout"), TransientFetchError("503"), [item(1), item(2)]]
    )
    sleep = SleepRecorder()
    run = run_collection(
        db, PROP, adapter, policy=POLICY, sleep=sleep, rate_limiter=NO_LIMIT, rng=random.Random(1)
    )
    assert adapter.calls == 3
    assert len(sleep.calls) == 2
    assert 0 <= sleep.calls[0] <= 1.0 and 0 <= sleep.calls[1] <= 2.0  # full jitter bounds
    assert run.status == "success"
    assert (run.discovered_count, run.inserted_count, run.duplicate_count) == (2, 2, 0)
    assert run.finished_at is not None and run.started_at <= run.finished_at
    sources = set(db.scalars(select(Review.source)))
    assert sources == {"live"}


def test_retry_exhaustion_marks_failed_and_keeps_existing(db: Session) -> None:
    import_file(db, "valid.csv", (FIXTURES / "valid.csv").read_bytes())
    before = count(db, Review)
    adapter = FakeAdapter([TransientFetchError("timeout")] * 4)
    sleep = SleepRecorder()
    run = run_collection(db, PROP, adapter, policy=POLICY, sleep=sleep, rate_limiter=NO_LIMIT)
    assert adapter.calls == 4  # 1 attempt + 3 retries
    assert len(sleep.calls) == 3
    assert run.status == "failed"
    assert run.error_summary and "gave up after 4 attempts" in run.error_summary
    assert "Traceback" not in run.error_summary
    assert count(db, Review) == before


def test_permanent_error_is_not_retried(db: Session) -> None:
    adapter = FakeAdapter([PermanentFetchError("403 forbidden")])
    run = run_collection(
        db, PROP, adapter, policy=POLICY, sleep=SleepRecorder(), rate_limiter=NO_LIMIT
    )
    assert adapter.calls == 1 and run.status == "failed"


def test_partial_failure_keeps_fetched_items(db: Session) -> None:
    adapter = FakeAdapter([PartialFetchError("connection reset on page 2", [item(1), item(2)])])
    run = run_collection(
        db, PROP, adapter, policy=POLICY, sleep=SleepRecorder(), rate_limiter=NO_LIMIT
    )
    assert run.status == "partial"
    assert run.inserted_count == 2
    assert "page 2" in (run.error_summary or "")


def test_invalid_items_make_run_partial(db: Session) -> None:
    adapter = FakeAdapter([[item(1), item(2, rating=42), item(3, review_text="")]])
    run = run_collection(
        db, PROP, adapter, policy=POLICY, sleep=SleepRecorder(), rate_limiter=NO_LIMIT
    )
    assert run.status == "partial"
    assert (run.discovered_count, run.inserted_count, run.error_count) == (3, 1, 2)


def test_zero_new_reviews_is_success_not_failure(db: Session) -> None:
    run_collection(
        db,
        PROP,
        FakeAdapter([[item(1)]]),
        policy=POLICY,
        sleep=SleepRecorder(),
        rate_limiter=NO_LIMIT,
    )
    run = run_collection(
        db,
        PROP,
        FakeAdapter([[item(1)]]),
        policy=POLICY,
        sleep=SleepRecorder(),
        rate_limiter=NO_LIMIT,
    )
    assert run.status == "success"
    assert (run.inserted_count, run.duplicate_count) == (0, 1)
    empty = run_collection(
        db, PROP, FakeAdapter([[]]), policy=POLICY, sleep=SleepRecorder(), rate_limiter=NO_LIMIT
    )
    assert empty.status == "success" and empty.discovered_count == 0


def test_error_summary_strips_credentials(db: Session) -> None:
    adapter = FakeAdapter(
        [PermanentFetchError("auth failed for https://user:secret@feed.example/x")]
    )
    run = run_collection(
        db, PROP, adapter, policy=POLICY, sleep=SleepRecorder(), rate_limiter=NO_LIMIT
    )
    assert "secret" not in (run.error_summary or "")


def test_unknown_property(db: Session) -> None:
    with pytest.raises(LookupError):
        run_collection(db, "nope", FakeAdapter([[]]), policy=POLICY, sleep=SleepRecorder())


def test_backoff_grows_and_is_capped() -> None:
    p = RetryPolicy(max_retries=10, backoff_base=1.0, backoff_cap=5.0)
    rng = random.Random(0)
    for attempt in range(1, 11):
        assert 0 <= p.delay(attempt, rng) <= min(5.0, 2 ** (attempt - 1))


def test_rate_limiter_spaces_calls() -> None:
    t = [0.0]
    rl = RateLimiter(per_minute=6, clock=lambda: t[0])  # one call per 10s
    assert rl.wait_time() == 0.0
    assert rl.wait_time() == pytest.approx(10.0)
    t[0] = 25.0
    assert rl.wait_time() == pytest.approx(0.0)


def test_rate_limiter_used_between_attempts() -> None:
    t = [0.0]
    rl = RateLimiter(per_minute=60, clock=lambda: t[0])
    sleep = SleepRecorder()
    adapter = FakeAdapter([TransientFetchError("x"), [item(1)]])
    out = fetch_with_retry(
        adapter,
        PROP,
        None,
        RetryPolicy(max_retries=1, backoff_base=0),
        sleep=sleep,
        rate_limiter=rl,
    )
    assert out.items and out.attempts == 2
    assert pytest.approx(1.0) in sleep.calls  # rate-limit wait before 2nd attempt
