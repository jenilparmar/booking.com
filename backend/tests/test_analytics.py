import hashlib
import itertools
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy.orm import Session

from app.models import Review
from app.services import analytics
from app.services.importer import import_file
from tests.conftest import FIXTURES

SYD = ZoneInfo("Australia/Sydney")
# Wednesday 7 Oct 2026 14:00 AEDT. DST started Sunday 4 Oct 2026 (02:00 AEST -> 03:00 AEDT),
# so the previous week (28 Sep - 4 Oct) straddles the change.
NOW = datetime(2026, 10, 7, 14, 0, tzinfo=SYD)
P1, P2 = "olympic-paddington", "venus-surry-hills"
_seq = itertools.count()


def local(s: str) -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=SYD)


def add(
    db: Session,
    when: datetime | None,
    *,
    prop: str = P1,
    rating: float | None = 8.0,
    sentiment: str = "positive",
    topics: list[str] | None = None,
    score: float | None = None,
    text: str = "review",
) -> Review:
    n = next(_seq)
    r = Review(
        property_id=prop,
        source_review_id=f"T-{n}",
        review_text=f"{text} {n}",
        rating=rating,
        published_at=when,
        sentiment_label=sentiment,
        sentiment_score=score,
        topic_labels=topics or [],
        source="synthetic",
        content_hash=hashlib.sha256(str(n).encode()).hexdigest(),
    )
    db.add(r)
    db.flush()
    return r


# ---------------------------------------------------------------- week boundaries / DST


def test_week_periods_across_dst() -> None:
    cur, prev = analytics.week_periods(NOW, SYD)
    assert cur.start == datetime(2026, 10, 4, 13, 0, tzinfo=UTC)  # Mon 5 Oct 00:00 AEDT (+11)
    assert cur.end == NOW.astimezone(UTC)
    assert prev.start == datetime(2026, 9, 27, 14, 0, tzinfo=UTC)  # Mon 28 Sep 00:00 AEST (+10)
    assert prev.end == datetime(2026, 9, 30, 4, 0, tzinfo=UTC)  # Wed 30 Sep 14:00 AEST
    # Same wall-clock span; absolute length differs by the DST hour only when the span crosses it.
    assert (cur.end - cur.start).total_seconds() / 3600 == 62
    assert (prev.end - prev.start).total_seconds() / 3600 == 62


def test_week_periods_when_previous_span_crosses_dst() -> None:
    now = datetime(2026, 10, 11, 12, 0, tzinfo=SYD)  # Sunday after DST week
    cur, prev = analytics.week_periods(now, SYD)
    assert cur.start == datetime(2026, 10, 4, 13, 0, tzinfo=UTC)
    # Previous: Mon 28 Sep 00:00 AEST -> Sun 4 Oct 12:00 AEDT. 156 wall hours, 155 real hours.
    assert prev.end == datetime(2026, 10, 4, 1, 0, tzinfo=UTC)
    assert (prev.end - prev.start).total_seconds() / 3600 == 155


def test_week_boundary_monday_midnight_local(db: Session) -> None:
    add(db, local("2026-10-04T23:59:59"), rating=2)  # Sunday night -> previous week
    add(db, local("2026-10-05T00:00:00"), rating=10)  # Monday 00:00 -> this week
    s = analytics.summary(db, NOW)
    assert s["current"]["reviews"] == 1 and s["current"]["avg_rating"] == 10
    # Sunday 23:59 is after the previous-week Wednesday 14:00 cutoff, so it is not in "previous".
    assert s["previous"]["reviews"] == 0


def test_previous_week_equivalent_elapsed_cutoff(db: Session) -> None:
    add(db, local("2026-09-30T13:59:00"), rating=6)  # inside prev span
    add(db, local("2026-09-30T14:01:00"), rating=1)  # after prev cutoff
    s = analytics.summary(db, NOW)
    assert s["previous"]["reviews"] == 1 and s["previous"]["avg_rating"] == 6


def test_future_reviews_after_now_excluded(db: Session) -> None:
    add(db, local("2026-10-07T15:00:00"))
    assert analytics.summary(db, NOW)["current"]["reviews"] == 0


# ---------------------------------------------------------------- KPIs


def test_summary_kpis(db: Session) -> None:
    add(db, local("2026-10-05T10:00"), rating=9, sentiment="positive", topics=["Location"])
    add(db, local("2026-10-06T10:00"), rating=None, sentiment="negative", topics=["Noise"])
    add(
        db,
        local("2026-10-06T11:00"),
        rating=3,
        sentiment="negative",
        topics=["Noise", "Cleanliness"],
    )
    add(db, local("2026-10-07T09:00"), rating=6, sentiment="neutral")
    add(db, local("2026-09-29T09:00"), rating=8, sentiment="positive")
    add(db, local("2026-09-29T10:00"), rating=7, sentiment="negative", topics=["Cleanliness"])

    s = analytics.summary(db, NOW)
    cur = s["current"]
    assert cur["reviews"] == 4
    assert cur["rated_reviews"] == 3
    assert cur["avg_rating"] == 6.0  # (9+3+6)/3; the missing rating is not counted as 0
    assert cur["negative"] == 2 and cur["pct_negative"] == 50.0
    assert s["previous"]["avg_rating"] == 7.5
    assert s["avg_rating_change"] == -1.5
    assert s["review_count_change"] == 2
    assert s["top_negative_topic"] == {
        "topic": "Noise",
        "count": 2,
        "negative_reviews": 2,
        "pct_of_negative": 100.0,
    }
    assert s["timezone"] == "Australia/Sydney"
    assert s["data_sources"] == ["synthetic"]


def test_missing_ratings_only_gives_null_average(db: Session) -> None:
    add(db, local("2026-10-06T10:00"), rating=None)
    s = analytics.summary(db, NOW)
    assert s["current"]["reviews"] == 1
    assert s["current"]["avg_rating"] is None and s["current"]["rated_reviews"] == 0
    assert s["avg_rating_change"] is None


def test_missing_dates_excluded_and_reported(db: Session) -> None:
    add(db, None, rating=1, sentiment="negative", topics=["Noise"])
    add(db, local("2026-10-06T10:00"), rating=9)
    s = analytics.summary(db, NOW)
    assert s["current"]["reviews"] == 1
    assert s["excluded_undated"] == 1
    assert s["top_negative_topic"] is None


def test_empty_dataset(db: Session) -> None:
    s = analytics.summary(db, NOW)
    assert s["current"] == {
        "reviews": 0,
        "avg_rating": None,
        "rated_reviews": 0,
        "positive": 0,
        "neutral": 0,
        "negative": 0,
        "pct_negative": None,
    }
    assert s["avg_rating_change"] is None and s["top_negative_topic"] is None
    assert s["data_sources"] == []
    t = analytics.topic_insights(db, NOW)
    assert t["negative_reviews"] == 0 and t["top_negative_topics"] == []
    assert t["cleanliness_share_of_negative"]["pct"] is None
    tr = analytics.trends(db, NOW, weeks=4)
    assert len(tr["overall"]) == 4 and all(p["reviews"] == 0 for p in tr["overall"])
    c = analytics.property_comparison(db, NOW)
    assert len(c["properties"]) == 4
    assert all(p["window"]["avg_rating"] is None for p in c["properties"])


def test_duplicates_not_double_counted(db: Session) -> None:
    content = (FIXTURES / "valid.csv").read_bytes()
    import_file(db, "valid.csv", content, now=datetime(2026, 10, 8, tzinfo=UTC))
    before = analytics.summary(db, NOW)
    import_file(db, "valid.csv", content, now=datetime(2026, 10, 8, tzinfo=UTC))
    after = analytics.summary(db, NOW)
    assert before == after
    assert before["current"]["reviews"] == 2  # FX-1 and FX-2 fall in this week


def test_property_filter(db: Session) -> None:
    add(db, local("2026-10-06T10:00"), prop=P1, rating=10)
    add(db, local("2026-10-06T10:00"), prop=P2, rating=2)
    assert analytics.summary(db, NOW, [P2])["current"]["avg_rating"] == 2
    assert analytics.summary(db, NOW, [P1, P2])["current"]["avg_rating"] == 6


# ---------------------------------------------------------------- comparison


def test_property_comparison(db: Session) -> None:
    add(db, local("2026-10-06T10:00"), prop=P1, rating=9)
    add(db, local("2026-09-29T10:00"), prop=P1, rating=7)
    add(db, local("2026-10-06T10:00"), prop=P2, rating=3, sentiment="negative", topics=["Noise"])
    add(
        db,
        local("2026-09-22T10:00"),
        prop=P2,
        rating=4,
        sentiment="negative",
        topics=["Noise", "Check-in experience"],
    )
    add(
        db,
        local("2026-09-23T10:00"),
        prop=P2,
        rating=5,
        sentiment="negative",
        topics=["Check-in experience"],
    )
    add(
        db,
        local("2026-08-01T10:00"),
        prop=P2,
        rating=1,
        sentiment="negative",
        topics=["Facilities"],
    )  # outside window

    c = analytics.property_comparison(db, NOW, weeks=4)
    by = {p["property_id"]: p for p in c["properties"]}
    assert by[P1]["current_week"]["avg_rating"] == 9
    assert by[P1]["previous_week"]["avg_rating"] == 7
    assert by[P1]["avg_rating_change"] == 2
    assert by[P1]["top_complaint"] is None
    p2 = by[P2]
    assert p2["window"]["reviews"] == 3 and p2["window"]["negative"] == 3
    assert p2["window"]["pct_negative"] == 100.0
    # Tie (2 Noise vs 2 Check-in) broken by fixed topic order: Check-in comes before Noise.
    assert p2["top_complaint"]["topic"] == "Check-in experience"
    assert p2["top_complaint"]["count"] == 2
    assert p2["previous_week"]["avg_rating"] is None and p2["avg_rating_change"] is None


# ---------------------------------------------------------------- trends


def test_trends_bucket_by_local_monday(db: Session) -> None:
    # Monday 00:30 AEDT is Sunday 13:30 UTC; must land in the local Monday bucket.
    add(db, local("2026-10-05T00:30"), rating=8, sentiment="positive")
    add(db, local("2026-10-04T23:30"), rating=4, sentiment="negative")
    add(db, local("2026-09-21T12:00"), prop=P2, rating=6, sentiment="neutral")
    tr = analytics.trends(db, NOW, weeks=3)
    weeks = [p["week_start"] for p in tr["overall"]]
    assert weeks == ["2026-09-21", "2026-09-28", "2026-10-05"]
    by_week = {p["week_start"]: p for p in tr["overall"]}
    assert by_week["2026-10-05"]["reviews"] == 1 and by_week["2026-10-05"]["positive"] == 1
    assert by_week["2026-09-28"]["reviews"] == 1 and by_week["2026-09-28"]["negative"] == 1
    assert by_week["2026-09-21"]["avg_rating"] == 6
    p2 = next(s for s in tr["by_property"] if s["property_id"] == P2)
    assert [p["reviews"] for p in p2["points"]] == [1, 0, 0]
    assert p2["points"][1]["avg_rating"] is None  # empty week is null, not 0


# ---------------------------------------------------------------- insights


def test_cleanliness_share_and_top_topics(db: Session) -> None:
    add(db, local("2026-10-06T10:00"), sentiment="negative", topics=["Cleanliness", "Noise"])
    add(db, local("2026-10-01T10:00"), sentiment="negative", topics=["Noise"])
    add(db, local("2026-09-25T10:00"), sentiment="negative", topics=["Cleanliness"])
    add(db, local("2026-09-24T10:00"), sentiment="negative", topics=[])
    add(db, local("2026-10-06T10:00"), sentiment="positive", topics=["Cleanliness"])  # not negative

    t = analytics.topic_insights(db, NOW, weeks=4)
    assert t["negative_reviews"] == 4
    c = t["cleanliness_share_of_negative"]
    assert c == {
        "negative_with_cleanliness": 2,
        "negative_reviews": 4,
        "pct": 50.0,
        "available": True,
    }
    assert [x["topic"] for x in t["top_negative_topics"]] == ["Cleanliness", "Noise"]
    assert t["top_negative_topics"][0]["pct_of_negative"] == 50.0


def test_zero_negatives_makes_cleanliness_unavailable(db: Session) -> None:
    add(db, local("2026-10-06T10:00"), sentiment="positive", topics=["Cleanliness"])
    c = analytics.topic_insights(db, NOW)["cleanliness_share_of_negative"]
    assert c["pct"] is None and c["available"] is False and c["negative_reviews"] == 0


def test_worst_topic_per_property(db: Session) -> None:
    add(db, local("2026-10-06T10:00"), prop=P2, sentiment="negative", topics=["Noise"])
    add(
        db, local("2026-10-05T10:00"), prop=P2, sentiment="negative", topics=["Noise", "Facilities"]
    )
    t = analytics.topic_insights(db, NOW)
    by = {w["property_id"]: w for w in t["worst_topic_by_property"]}
    assert (
        by[P2]["topic"] == "Noise" and by[P2]["count"] == 2 and by[P2]["pct_of_negative"] == 100.0
    )
    assert by[P1]["topic"] is None and by[P1]["negative_reviews"] == 0


def test_rising_topics(db: Session) -> None:
    # Recent 14 days: Noise x3, Location x1. Prior 14 days: Noise x1, Location x2.
    for d in ("2026-10-06T10:00", "2026-10-01T10:00", "2026-09-26T10:00"):
        add(db, local(d), sentiment="negative", topics=["Noise"])
    add(db, local("2026-10-02T10:00"), sentiment="negative", topics=["Location"])
    add(db, local("2026-09-20T10:00"), sentiment="negative", topics=["Noise"])
    add(db, local("2026-09-19T10:00"), sentiment="negative", topics=["Location"])
    add(db, local("2026-09-18T10:00"), sentiment="negative", topics=["Location"])
    t = analytics.topic_insights(db, NOW)
    assert [r["topic"] for r in t["rising_topics"]] == ["Noise"]
    r = t["rising_topics"][0]
    assert (r["recent_count"], r["prior_count"], r["change"]) == (3, 1, 2)
    assert r["recent_pct_of_negative"] == 75.0


def test_examples_are_most_negative_first(db: Session) -> None:
    add(
        db,
        local("2026-10-06T10:00"),
        sentiment="negative",
        topics=["Noise"],
        score=-0.2,
        text="mild",
    )
    add(
        db,
        local("2026-10-05T10:00"),
        sentiment="negative",
        topics=["Noise"],
        score=-0.9,
        text="worst",
    )
    add(
        db,
        local("2026-10-04T10:00"),
        sentiment="negative",
        topics=["Noise"],
        score=-0.5,
        text="mid",
    )
    t = analytics.topic_insights(db, NOW, examples_per_topic=2)
    ex = next(e for e in t["examples"] if e["topic"] == "Noise")["reviews"]
    assert [e["review_text"].split()[0] for e in ex] == ["worst", "mid"]


@pytest.mark.parametrize("weeks", [1, 4, 12])
def test_window_start_is_local_monday(weeks: int) -> None:
    ws = analytics.window_start(NOW, weeks, SYD).astimezone(SYD)
    assert ws.weekday() == 0 and (ws.hour, ws.minute) == (0, 0)
