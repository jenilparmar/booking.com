"""Analytics over reviews. Every aggregate is computed in Postgres; Python only shapes results.

Week handling
-------------
Weeks start Monday 00:00 in the business timezone (``BUSINESS_TIMEZONE``, default
Australia/Sydney). Two techniques are used, both DST-safe:

* KPI/comparison periods: boundaries are computed in Python with ``zoneinfo`` and passed as bound
  UTC parameters. "This week" is [Monday 00:00 local, now). "Previous week" is the same
  wall-clock span one week earlier: [previous Monday 00:00, now - 7 days in local wall time).
* Weekly trend buckets: ``date_trunc('week', published_at AT TIME ZONE :tz)`` in SQL, which
  yields the local Monday for each review.

Reviews with no ``published_at`` are excluded from all time-based figures and counted in
``excluded_undated``. Missing ratings are excluded from averages (never treated as 0); rating
averages report how many rated reviews they are based on.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import (
    ColumnElement,
    Select,
    and_,
    case,
    func,
    literal,
    select,
    true,
)
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Property, Review
from app.services.classify import TOPICS

CLEANLINESS = "Cleanliness"
RISING_MIN_RECENT = 2


@dataclass(frozen=True)
class Period:
    start: datetime
    end: datetime

    def as_dict(self) -> dict[str, str]:
        return {"start": self.start.isoformat(), "end": self.end.isoformat()}


def _tz() -> ZoneInfo:
    return ZoneInfo(get_settings().business_timezone)


def local_midnight(d: date, tz: ZoneInfo) -> datetime:
    return datetime.combine(d, time(0, 0), tzinfo=tz)


def week_periods(now: datetime, tz: ZoneInfo | None = None) -> tuple[Period, Period]:
    """(current week-to-date, previous week equivalent span), as aware UTC datetimes."""
    tz = tz or _tz()
    local_now = now.astimezone(tz)
    monday = local_now.date() - timedelta(days=local_now.weekday())
    cur_start = local_midnight(monday, tz)
    prev_start = local_midnight(monday - timedelta(days=7), tz)
    # Same wall-clock offset into the previous week (re-localized so DST shifts are respected).
    prev_end_wall = (local_now.replace(tzinfo=None) - timedelta(days=7)).replace(tzinfo=tz)
    return (
        Period(cur_start.astimezone(UTC), now.astimezone(UTC)),
        Period(prev_start.astimezone(UTC), prev_end_wall.astimezone(UTC)),
    )


def window_start(now: datetime, weeks: int, tz: ZoneInfo | None = None) -> datetime:
    """Monday 00:00 local, ``weeks - 1`` weeks before the current week's Monday."""
    tz = tz or _tz()
    local_now = now.astimezone(tz)
    monday = local_now.date() - timedelta(days=local_now.weekday())
    return local_midnight(monday - timedelta(weeks=weeks - 1), tz).astimezone(UTC)


def _scope(property_ids: list[str] | None) -> list[ColumnElement[bool]]:
    return [Review.property_id.in_(property_ids)] if property_ids else []


def _in(period: Period) -> ColumnElement[bool]:
    return and_(Review.published_at >= period.start, Review.published_at < period.end)


def _pct(num: int, den: int) -> float | None:
    return round(num * 100.0 / den, 1) if den else None


def _round(v: Any, nd: int = 2) -> float | None:
    return None if v is None else round(float(v), nd)


def _delta(a: float | None, b: float | None) -> float | None:
    return None if a is None or b is None else round(a - b, 2)


def _topics_table() -> Any:
    return func.jsonb_array_elements_text(Review.topic_labels).table_valued("value").alias("t")


def _period_stats(db: Session, conds: list[ColumnElement[bool]]) -> dict[str, Any]:
    row = db.execute(
        select(
            func.count(Review.id),
            func.avg(Review.rating),
            func.count(Review.rating),
            func.count(Review.id).filter(Review.sentiment_label == "positive"),
            func.count(Review.id).filter(Review.sentiment_label == "neutral"),
            func.count(Review.id).filter(Review.sentiment_label == "negative"),
        ).where(*conds)
    ).one()
    total, avg, rated, pos, neu, neg = row
    return {
        "reviews": int(total),
        "avg_rating": _round(avg),
        "rated_reviews": int(rated),
        "positive": int(pos),
        "neutral": int(neu),
        "negative": int(neg),
        "pct_negative": _pct(int(neg), int(total)),
    }


def _negative_topic_counts(
    db: Session, conds: list[ColumnElement[bool]], group_by_property: bool = False
) -> list[tuple[Any, ...]]:
    t = _topics_table()
    cols: list[Any] = [t.c.value, func.count()]
    group: list[Any] = [t.c.value]
    if group_by_property:
        cols.insert(0, Review.property_id)
        group.insert(0, Review.property_id)
    stmt = (
        select(*cols)
        .select_from(Review)
        .join(t, true())
        .where(Review.sentiment_label == "negative", *conds)
        .group_by(*group)
    )
    return [tuple(r) for r in db.execute(stmt)]


def _top_topic(counts: dict[str, int]) -> tuple[str, int] | None:
    if not counts:
        return None
    order = {t: i for i, t in enumerate(TOPICS)}
    topic = min(counts, key=lambda k: (-counts[k], order.get(k, 99), k))
    return topic, counts[topic]


def data_sources(db: Session, property_ids: list[str] | None = None) -> list[str]:
    return sorted(db.scalars(select(Review.source).where(*_scope(property_ids)).distinct()))


def excluded_undated(db: Session, property_ids: list[str] | None = None) -> int:
    return int(
        db.scalar(
            select(func.count(Review.id)).where(
                Review.published_at.is_(None), *_scope(property_ids)
            )
        )
        or 0
    )


def summary(
    db: Session, now: datetime | None = None, property_ids: list[str] | None = None
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    tz = _tz()
    cur, prev = week_periods(now, tz)
    scope = _scope(property_ids)
    c = _period_stats(db, [_in(cur), *scope])
    p = _period_stats(db, [_in(prev), *scope])
    neg_counts = dict(
        (str(topic), int(n)) for topic, n in _negative_topic_counts(db, [_in(cur), *scope])
    )
    top = _top_topic(neg_counts)
    return {
        "timezone": tz.key,
        "current_period": cur.as_dict(),
        "previous_period": prev.as_dict(),
        "current": c,
        "previous": p,
        "avg_rating_change": _delta(c["avg_rating"], p["avg_rating"]),
        "review_count_change": c["reviews"] - p["reviews"],
        "pct_negative_change": _delta(c["pct_negative"], p["pct_negative"]),
        "top_negative_topic": (
            {
                "topic": top[0],
                "count": top[1],
                "negative_reviews": c["negative"],
                "pct_of_negative": _pct(top[1], c["negative"]),
            }
            if top
            else None
        ),
        "excluded_undated": excluded_undated(db, property_ids),
        "data_sources": data_sources(db, property_ids),
    }


def property_comparison(
    db: Session,
    now: datetime | None = None,
    property_ids: list[str] | None = None,
    weeks: int = 4,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    tz = _tz()
    cur, prev = week_periods(now, tz)
    window = Period(window_start(now, weeks, tz), now.astimezone(UTC))
    scope = _scope(property_ids)

    def grouped(period: Period) -> dict[str, dict[str, Any]]:
        stmt = (
            select(
                Review.property_id,
                func.count(Review.id),
                func.avg(Review.rating),
                func.count(Review.rating),
                func.count(Review.id).filter(Review.sentiment_label == "positive"),
                func.count(Review.id).filter(Review.sentiment_label == "neutral"),
                func.count(Review.id).filter(Review.sentiment_label == "negative"),
            )
            .where(_in(period), *scope)
            .group_by(Review.property_id)
        )
        out = {}
        for pid, total, avg, rated, pos, neu, neg in db.execute(stmt):
            out[pid] = {
                "reviews": int(total),
                "avg_rating": _round(avg),
                "rated_reviews": int(rated),
                "positive": int(pos),
                "neutral": int(neu),
                "negative": int(neg),
                "pct_negative": _pct(int(neg), int(total)),
            }
        return out

    empty = {
        "reviews": 0,
        "avg_rating": None,
        "rated_reviews": 0,
        "positive": 0,
        "neutral": 0,
        "negative": 0,
        "pct_negative": None,
    }
    w_stats, c_stats, p_stats = grouped(window), grouped(cur), grouped(prev)
    complaints: dict[str, dict[str, int]] = defaultdict(dict)
    for pid, topic, n in _negative_topic_counts(db, [_in(window), *scope], group_by_property=True):
        complaints[pid][topic] = int(n)

    props = db.scalars(
        select(Property).where(Property.id.in_(property_ids)) if property_ids else select(Property)
    ).all()
    rows = []
    for prop in sorted(props, key=lambda p: p.name):
        w = w_stats.get(prop.id, empty)
        c = c_stats.get(prop.id, empty)
        p = p_stats.get(prop.id, empty)
        top = _top_topic(complaints.get(prop.id, {}))
        rows.append(
            {
                "property_id": prop.id,
                "name": prop.name,
                "window": w,
                "current_week": c,
                "previous_week": p,
                "avg_rating_change": _delta(c["avg_rating"], p["avg_rating"]),
                "top_complaint": (
                    {
                        "topic": top[0],
                        "count": top[1],
                        "negative_reviews": w["negative"],
                        "pct_of_negative": _pct(top[1], w["negative"]),
                    }
                    if top
                    else None
                ),
            }
        )
    return {
        "timezone": tz.key,
        "window": window.as_dict(),
        "window_weeks": weeks,
        "current_period": cur.as_dict(),
        "previous_period": prev.as_dict(),
        "properties": rows,
        "excluded_undated": excluded_undated(db, property_ids),
        "data_sources": data_sources(db, property_ids),
    }


def trends(
    db: Session,
    now: datetime | None = None,
    property_ids: list[str] | None = None,
    weeks: int = 12,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    tz = _tz()
    start = window_start(now, weeks, tz)
    scope = _scope(property_ids)
    week_col = func.date_trunc("week", func.timezone(literal(tz.key), Review.published_at)).label(
        "week"
    )

    def bucket_stmt(by_property: bool) -> Select[Any]:
        cols: list[Any] = [
            week_col,
            func.count(Review.id),
            func.avg(Review.rating),
            func.count(Review.rating),
            func.count(Review.id).filter(Review.sentiment_label == "positive"),
            func.count(Review.id).filter(Review.sentiment_label == "neutral"),
            func.count(Review.id).filter(Review.sentiment_label == "negative"),
        ]
        group: list[Any] = [week_col]
        if by_property:
            cols.insert(0, Review.property_id)
            group.insert(0, Review.property_id)
        return (
            select(*cols)
            .where(Review.published_at >= start, Review.published_at < now, *scope)
            .group_by(*group)
        )

    local_start = start.astimezone(tz).date()
    week_keys = [local_start + timedelta(weeks=i) for i in range(weeks)]

    def point(wk: date, vals: tuple[Any, ...] | None) -> dict[str, Any]:
        total, avg, rated, pos, neu, neg = vals or (0, None, 0, 0, 0, 0)
        return {
            "week_start": wk.isoformat(),
            "reviews": int(total),
            "avg_rating": _round(avg),
            "rated_reviews": int(rated),
            "positive": int(pos),
            "neutral": int(neu),
            "negative": int(neg),
        }

    overall: dict[date, tuple[Any, ...]] = {}
    for wk, *vals in db.execute(bucket_stmt(False)):
        overall[wk.date()] = tuple(vals)
    per_prop: dict[str, dict[date, tuple[Any, ...]]] = defaultdict(dict)
    for pid, wk, *vals in db.execute(bucket_stmt(True)):
        per_prop[pid][wk.date()] = tuple(vals)

    props = db.scalars(
        select(Property).where(Property.id.in_(property_ids)) if property_ids else select(Property)
    ).all()
    return {
        "timezone": tz.key,
        "weeks": weeks,
        "current_week_partial": True,
        "overall": [point(wk, overall.get(wk)) for wk in week_keys],
        "by_property": [
            {
                "property_id": p.id,
                "name": p.name,
                "points": [point(wk, per_prop[p.id].get(wk)) for wk in week_keys],
            }
            for p in sorted(props, key=lambda p: p.name)
        ],
        "excluded_undated": excluded_undated(db, property_ids),
        "data_sources": data_sources(db, property_ids),
    }


def topic_insights(
    db: Session,
    now: datetime | None = None,
    property_ids: list[str] | None = None,
    weeks: int = 4,
    examples_per_topic: int = 2,
) -> dict[str, Any]:
    now = now or datetime.now(UTC)
    tz = _tz()
    window = Period(window_start(now, weeks, tz), now.astimezone(UTC))
    scope = _scope(property_ids)
    in_window = [_in(window), *scope]

    total_neg = int(
        db.scalar(
            select(func.count(Review.id)).where(Review.sentiment_label == "negative", *in_window)
        )
        or 0
    )
    total_reviews = int(db.scalar(select(func.count(Review.id)).where(*in_window)) or 0)
    counts = {str(t): int(n) for t, n in _negative_topic_counts(db, in_window)}
    order = {t: i for i, t in enumerate(TOPICS)}
    top_topics = [
        {"topic": t, "count": n, "pct_of_negative": _pct(n, total_neg)}
        for t, n in sorted(counts.items(), key=lambda kv: (-kv[1], order.get(kv[0], 99)))
    ]

    clean_n = counts.get(CLEANLINESS, 0)
    cleanliness = {
        "negative_with_cleanliness": clean_n,
        "negative_reviews": total_neg,
        "pct": _pct(clean_n, total_neg),
        "available": total_neg > 0,
    }

    per_prop: dict[str, dict[str, int]] = defaultdict(dict)
    for pid, topic, n in _negative_topic_counts(db, in_window, group_by_property=True):
        per_prop[pid][topic] = int(n)
    neg_by_prop = dict(
        db.execute(
            select(Review.property_id, func.count(Review.id))
            .where(Review.sentiment_label == "negative", *in_window)
            .group_by(Review.property_id)
        ).all()
    )
    props = db.scalars(
        select(Property).where(Property.id.in_(property_ids)) if property_ids else select(Property)
    ).all()
    worst = []
    for p in sorted(props, key=lambda p: p.name):
        top = _top_topic(per_prop.get(p.id, {}))
        n_neg = int(neg_by_prop.get(p.id, 0))
        worst.append(
            {
                "property_id": p.id,
                "name": p.name,
                "topic": top[0] if top else None,
                "count": top[1] if top else 0,
                "negative_reviews": n_neg,
                "pct_of_negative": _pct(top[1], n_neg) if top else None,
            }
        )

    # Rising: negative mentions in the most recent 14 days vs the 14 days before.
    recent = Period(now.astimezone(UTC) - timedelta(days=14), now.astimezone(UTC))
    prior = Period(recent.start - timedelta(days=14), recent.start)
    t = _topics_table()
    rising_stmt = (
        select(
            t.c.value,
            func.count().filter(_in(recent)),
            func.count().filter(_in(prior)),
        )
        .select_from(Review)
        .join(t, true())
        .where(
            Review.sentiment_label == "negative",
            Review.published_at >= prior.start,
            Review.published_at < recent.end,
            *scope,
        )
        .group_by(t.c.value)
    )
    neg_recent, neg_prior = db.execute(
        select(
            func.count(Review.id).filter(_in(recent)),
            func.count(Review.id).filter(_in(prior)),
        ).where(Review.sentiment_label == "negative", *scope)
    ).one()
    rising = []
    for topic, r_n, p_n in db.execute(rising_stmt):
        r_n, p_n = int(r_n), int(p_n)
        if r_n > p_n and r_n >= RISING_MIN_RECENT:
            rising.append(
                {
                    "topic": topic,
                    "recent_count": r_n,
                    "prior_count": p_n,
                    "change": r_n - p_n,
                    "recent_pct_of_negative": _pct(r_n, int(neg_recent)),
                    "prior_pct_of_negative": _pct(p_n, int(neg_prior)),
                }
            )
    rising.sort(key=lambda r: (-r["change"], order.get(r["topic"], 99)))

    # Representative examples: most negative-scoring, then most recent, per top topic.
    example_topics = [str(x["topic"]) for x in top_topics[:3]]
    examples: dict[str, list[dict[str, Any]]] = {topic: [] for topic in example_topics}
    if example_topics:
        t2 = _topics_table()
        rn = (
            func.row_number()
            .over(
                partition_by=t2.c.value,
                order_by=(
                    case((Review.sentiment_score.is_(None), 1), else_=0),
                    Review.sentiment_score.asc(),
                    Review.published_at.desc(),
                    Review.id.desc(),
                ),
            )
            .label("rn")
        )
        ranked = (
            select(t2.c.value.label("topic"), Review.id.label("review_id"), rn)
            .select_from(Review)
            .join(t2, true())
            .where(Review.sentiment_label == "negative", t2.c.value.in_(example_topics), *in_window)
            .subquery()
        )
        stmt = (
            select(ranked.c.topic, Review)
            .join(Review, Review.id == ranked.c.review_id)
            .where(ranked.c.rn <= examples_per_topic)
            .order_by(ranked.c.topic, ranked.c.rn)
        )
        for topic, r in db.execute(stmt):
            examples[topic].append(
                {
                    "id": r.id,
                    "property_id": r.property_id,
                    "review_title": r.review_title,
                    "review_text": r.review_text,
                    "rating": r.rating,
                    "published_at": r.published_at.isoformat() if r.published_at else None,
                    "sentiment_score": r.sentiment_score,
                    "source": r.source,
                }
            )

    return {
        "timezone": tz.key,
        "window": window.as_dict(),
        "window_weeks": weeks,
        "method": "approximate keyword-based topics; VADER text sentiment",
        "total_reviews": total_reviews,
        "negative_reviews": total_neg,
        "top_negative_topics": top_topics,
        "cleanliness_share_of_negative": cleanliness,
        "worst_topic_by_property": worst,
        "rising_topics": rising,
        "rising_periods": {"recent": recent.as_dict(), "prior": prior.as_dict()},
        "examples": [{"topic": k, "reviews": v} for k, v in examples.items()],
        "excluded_undated": excluded_undated(db, property_ids),
        "data_sources": data_sources(db, property_ids),
    }
