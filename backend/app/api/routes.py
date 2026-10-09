import math
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, File, Path, Query, UploadFile
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.api.errors import ApiError
from app.api.schemas import (
    SOURCE_TO_DATA_SOURCE,
    CollectionHealthOut,
    ComparisonOut,
    ErrorResponse,
    HealthOut,
    ImportOut,
    PropertiesOut,
    PropertyHealth,
    PropertyOut,
    ReviewFilters,
    ReviewOut,
    ReviewPage,
    RunOut,
    RunsOut,
    SummaryOut,
    TopicsOut,
    TrendsOut,
    to_data_sources,
)
from app.config import get_settings
from app.db import get_db
from app.models import CollectionRun, Property, Review
from app.services import analytics
from app.services.classify import TOPICS
from app.services.collection import CollectionUnsupportedError, get_adapter, run_collection
from app.services.importer import ImportFileError, import_file

router = APIRouter(prefix="/api")

DB = Annotated[Session, Depends(get_db)]
ERRORS: dict[int | str, dict[str, Any]] = {
    422: {"model": ErrorResponse, "description": "Validation error"},
}
DATA_SOURCE_TO_SOURCE = {v: k for k, v in SOURCE_TO_DATA_SOURCE.items()}

TopicName = Literal[
    "Cleanliness",
    "Check-in experience",
    "Staff/receptionist behaviour",
    "Noise",
    "Facilities",
    "Location",
    "Room condition",
    "Value for money",
]
assert set(TopicName.__args__) == set(TOPICS)  # type: ignore[attr-defined]


def _tz() -> ZoneInfo:
    return ZoneInfo(get_settings().business_timezone)


def _provenance(sources: list[str]) -> dict[str, Any]:
    ds = to_data_sources(sources)
    return {"data_sources": ds, "contains_synthetic": "synthetic" in ds}


def property_ids_param(
    db: DB,
    property_ids: Annotated[
        list[str] | None,
        Query(
            description="Filter by property id. Repeat the parameter or pass a "
            "comma-separated list."
        ),
    ] = None,
) -> list[str] | None:
    if not property_ids:
        return None
    ids = sorted({p.strip() for raw in property_ids for p in raw.split(",") if p.strip()})
    if not ids:
        return None
    known = set(db.scalars(select(Property.id)))
    unknown = [p for p in ids if p not in known]
    if unknown:
        raise ApiError(
            422,
            "validation_error",
            "Unknown property id.",
            [{"field": "property_ids", "message": f"unknown: {', '.join(unknown)}"}],
        )
    return ids


PropertyIds = Annotated[list[str] | None, Depends(property_ids_param)]


def as_of_param(
    as_of: Annotated[
        datetime | None,
        Query(
            description="Evaluate analytics as if 'now' were this instant (ISO 8601). "
            "Naive values use the business timezone. Defaults to the current time."
        ),
    ] = None,
) -> datetime:
    if as_of is None:
        return datetime.now(UTC)
    if as_of.tzinfo is None:
        as_of = as_of.replace(tzinfo=_tz())
    return as_of.astimezone(UTC)


AsOf = Annotated[datetime, Depends(as_of_param)]
Weeks = Annotated[int, Query(ge=1, le=52)]


# ---------------------------------------------------------------- health & properties


@router.get("/health", response_model=HealthOut, tags=["meta"])
def health(db: DB) -> dict[str, Any]:
    try:
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": "ok", "version": "0.1.0"}
    except SQLAlchemyError as exc:
        raise ApiError(503, "database_unavailable", "Database is not reachable.") from exc


@router.get("/properties", response_model=PropertiesOut, tags=["properties"])
def list_properties(db: DB) -> dict[str, Any]:
    rows = db.execute(
        select(Property, func.count(Review.id), func.max(Review.published_at))
        .outerjoin(Review, Review.property_id == Property.id)
        .group_by(Property.id)
        .order_by(Property.name)
    ).all()
    items = [
        PropertyOut(
            id=p.id,
            name=p.name,
            source_url=p.source_url,
            review_count=int(n),
            last_review_at=last,
        )
        for p, n, last in rows
    ]
    return {"items": items, **_provenance(analytics.data_sources(db))}


# ---------------------------------------------------------------- reviews


def _review_out(r: Review, names: dict[str, str]) -> ReviewOut:
    return ReviewOut(
        id=r.id,
        property_id=r.property_id,
        property_name=names.get(r.property_id, r.property_id),
        source_review_id=r.source_review_id,
        review_title=r.review_title,
        review_text=r.review_text,
        rating=r.rating,
        published_at=r.published_at,
        language=r.language,
        sentiment_label=r.sentiment_label,  # type: ignore[arg-type]
        sentiment_score=r.sentiment_score,
        topic_labels=list(r.topic_labels or []),
        data_source=SOURCE_TO_DATA_SOURCE[r.source],
        collected_at=r.collected_at,
    )


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/reviews", response_model=ReviewPage, responses=ERRORS, tags=["reviews"])
def list_reviews(
    db: DB,
    property_ids: PropertyIds,
    date_from: Annotated[
        date | None, Query(description="Inclusive, business-timezone calendar date.")
    ] = None,
    date_to: Annotated[
        date | None, Query(description="Inclusive, business-timezone calendar date.")
    ] = None,
    rating_min: Annotated[float | None, Query(ge=1, le=10)] = None,
    rating_max: Annotated[float | None, Query(ge=1, le=10)] = None,
    sentiment: Literal["positive", "neutral", "negative"] | None = None,
    topic: TopicName | None = None,
    q: Annotated[str | None, Query(max_length=200, description="Search title and text.")] = None,
    data_source: Literal["live", "imported", "synthetic"] | None = None,
    sort: Literal["newest", "oldest", "rating"] = "newest",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1)] = 20,
) -> dict[str, Any]:
    settings = get_settings()
    if page_size > settings.api_max_page_size:
        raise ApiError(
            422,
            "validation_error",
            "page_size is too large.",
            [{"field": "page_size", "message": f"maximum is {settings.api_max_page_size}"}],
        )
    if date_from and date_to and date_from > date_to:
        raise ApiError(
            422,
            "validation_error",
            "date_from must be on or before date_to.",
            [{"field": "date_from", "message": "after date_to"}],
        )
    if rating_min is not None and rating_max is not None and rating_min > rating_max:
        raise ApiError(
            422,
            "validation_error",
            "rating_min must be less than or equal to rating_max.",
            [{"field": "rating_min", "message": "greater than rating_max"}],
        )

    tz = _tz()
    conds: list[Any] = []
    if property_ids:
        conds.append(Review.property_id.in_(property_ids))
    if date_from:
        conds.append(Review.published_at >= analytics.local_midnight(date_from, tz))
    if date_to:
        conds.append(
            Review.published_at < analytics.local_midnight(date_to + timedelta(days=1), tz)
        )
    if rating_min is not None:
        conds.append(Review.rating >= rating_min)
    if rating_max is not None:
        conds.append(Review.rating <= rating_max)
    if sentiment:
        conds.append(Review.sentiment_label == sentiment)
    if topic:
        conds.append(Review.topic_labels.contains([topic]))
    q_clean = q.strip() if q else None
    if q_clean:
        pattern = f"%{_escape_like(q_clean)}%"
        conds.append(
            Review.review_text.ilike(pattern, escape="\\")
            | Review.review_title.ilike(pattern, escape="\\")
        )
    if data_source:
        conds.append(Review.source == DATA_SOURCE_TO_SOURCE[data_source])

    order: list[Any]
    if sort == "oldest":
        order = [Review.published_at.asc().nulls_last(), Review.id.asc()]
    elif sort == "rating":
        order = [
            Review.rating.desc().nulls_last(),
            Review.published_at.desc().nulls_last(),
            Review.id.desc(),
        ]
    else:
        order = [Review.published_at.desc().nulls_last(), Review.id.desc()]

    total = int(db.scalar(select(func.count(Review.id)).where(*conds)) or 0)
    rows = db.scalars(
        select(Review)
        .where(*conds)
        .order_by(*order)
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    names = dict(db.execute(select(Property.id, Property.name)).all())
    sources = list(db.scalars(select(Review.source).where(*conds).distinct()))
    return {
        "items": [_review_out(r, names) for r in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total else 0,
        "filters": ReviewFilters(
            property_ids=property_ids or [],
            date_from=date_from.isoformat() if date_from else None,
            date_to=date_to.isoformat() if date_to else None,
            rating_min=rating_min,
            rating_max=rating_max,
            sentiment=sentiment,
            topic=topic,
            q=q_clean,
            data_source=data_source,
            sort=sort,
        ),
        **_provenance(sources),
    }


@router.get(
    "/reviews/{review_id}",
    response_model=ReviewOut,
    responses={404: {"model": ErrorResponse}},
    tags=["reviews"],
)
def get_review(db: DB, review_id: Annotated[int, Path(ge=1)]) -> ReviewOut:
    r = db.get(Review, review_id)
    if r is None:
        raise ApiError(404, "not_found", f"Review {review_id} not found.")
    names = dict(db.execute(select(Property.id, Property.name)).all())
    return _review_out(r, names)


# ---------------------------------------------------------------- analytics


def _with_provenance(payload: dict[str, Any], as_of: datetime) -> dict[str, Any]:
    payload = dict(payload)
    payload.update(_provenance(payload.pop("data_sources", [])))
    payload["as_of"] = as_of
    return payload


@router.get("/analytics/summary", response_model=SummaryOut, responses=ERRORS, tags=["analytics"])
def analytics_summary(db: DB, property_ids: PropertyIds, as_of: AsOf) -> dict[str, Any]:
    return _with_provenance(analytics.summary(db, as_of, property_ids), as_of)


@router.get(
    "/analytics/properties", response_model=ComparisonOut, responses=ERRORS, tags=["analytics"]
)
def analytics_properties(
    db: DB, property_ids: PropertyIds, as_of: AsOf, weeks: Weeks = 4
) -> dict[str, Any]:
    return _with_provenance(analytics.property_comparison(db, as_of, property_ids, weeks), as_of)


@router.get("/analytics/trends", response_model=TrendsOut, responses=ERRORS, tags=["analytics"])
def analytics_trends(
    db: DB, property_ids: PropertyIds, as_of: AsOf, weeks: Weeks = 12
) -> dict[str, Any]:
    return _with_provenance(analytics.trends(db, as_of, property_ids, weeks), as_of)


@router.get("/analytics/topics", response_model=TopicsOut, responses=ERRORS, tags=["analytics"])
def analytics_topics(
    db: DB, property_ids: PropertyIds, as_of: AsOf, weeks: Weeks = 4
) -> dict[str, Any]:
    payload = analytics.topic_insights(db, as_of, property_ids, weeks)
    for group in payload["examples"]:
        for ex in group["reviews"]:
            ex["data_source"] = SOURCE_TO_DATA_SOURCE[ex.pop("source")]
    return _with_provenance(payload, as_of)


# ---------------------------------------------------------------- collection


@router.get("/collection/runs", response_model=RunsOut, responses=ERRORS, tags=["collection"])
def collection_runs(
    db: DB,
    property_ids: PropertyIds,
    status: Literal["running", "success", "partial", "failed"] | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    stmt = select(CollectionRun)
    if property_ids:
        stmt = stmt.where(CollectionRun.property_id.in_(property_ids))
    if status:
        stmt = stmt.where(CollectionRun.status == status)
    stmt = stmt.order_by(CollectionRun.started_at.desc(), CollectionRun.id.desc()).limit(limit)
    return {"items": [RunOut.model_validate(r) for r in db.scalars(stmt)]}


@router.get("/collection/health", response_model=CollectionHealthOut, tags=["collection"])
def collection_health(db: DB) -> dict[str, Any]:
    adapter = get_adapter()
    props = db.scalars(select(Property).order_by(Property.name)).all()
    counts = dict(
        db.execute(
            select(Review.property_id, func.count(Review.id)).group_by(Review.property_id)
        ).all()
    )
    last_success = dict(
        db.execute(
            select(CollectionRun.property_id, func.max(CollectionRun.finished_at))
            .where(CollectionRun.status.in_(["success", "partial"]))
            .group_by(CollectionRun.property_id)
        ).all()
    )
    out = []
    for p in props:
        latest = db.scalars(
            select(CollectionRun)
            .where(CollectionRun.property_id == p.id)
            .order_by(CollectionRun.started_at.desc(), CollectionRun.id.desc())
            .limit(1)
        ).first()
        errs = db.scalars(
            select(CollectionRun.error_summary)
            .where(CollectionRun.property_id == p.id, CollectionRun.error_summary.is_not(None))
            .order_by(CollectionRun.started_at.desc())
            .limit(3)
        ).all()
        out.append(
            PropertyHealth(
                property_id=p.id,
                name=p.name,
                last_success_at=last_success.get(p.id),
                latest_run=RunOut.model_validate(latest) if latest else None,
                review_count=int(counts.get(p.id, 0)),
                recent_errors=[e for e in errs if e],
            )
        )
    return {
        "adapter": adapter.name,
        "live_collection_supported": adapter.supported,
        "live_collection_note": adapter.unsupported_reason if not adapter.supported else "",
        "properties": out,
        **_provenance(analytics.data_sources(db)),
    }


@router.post(
    "/collection/run/{property_id}",
    response_model=RunOut,
    responses={404: {"model": ErrorResponse}, 501: {"model": ErrorResponse}},
    tags=["collection"],
)
def collection_run(db: DB, property_id: Annotated[str, Path(max_length=64)]) -> RunOut:
    if db.get(Property, property_id) is None:
        raise ApiError(404, "not_found", f"Property {property_id!r} not found.")
    try:
        run = run_collection(db, property_id)
    except CollectionUnsupportedError as exc:
        raise ApiError(501, "collection_unsupported", exc.reason, {"adapter": exc.adapter}) from exc
    return RunOut.model_validate(run)


# ---------------------------------------------------------------- import


_FILE_ERROR_STATUS = {"unsupported_file_type": 415, "file_too_large": 413}
_ALLOWED_CONTENT_TYPES = {
    "text/csv",
    "application/csv",
    "application/vnd.ms-excel",  # browsers on Windows label .csv this way
    "application/json",
    "text/json",
    "text/plain",
    "application/octet-stream",
    "",
}


@router.post(
    "/import/reviews",
    response_model=ImportOut,
    responses={
        400: {"model": ErrorResponse},
        413: {"model": ErrorResponse},
        415: {"model": ErrorResponse},
    },
    tags=["import"],
)
async def import_reviews(
    db: DB,
    file: Annotated[UploadFile, File(description="CSV or JSON file of reviews")],
) -> dict[str, Any]:
    settings = get_settings()
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in _ALLOWED_CONTENT_TYPES:
        raise ApiError(
            415,
            "unsupported_media_type",
            "Upload a CSV or JSON file.",
            {"content_type": content_type},
        )
    content = await file.read(settings.import_max_bytes + 1)
    try:
        result = import_file(db, file.filename or "", content)
    except ImportFileError as exc:
        raise ApiError(
            _FILE_ERROR_STATUS.get(exc.code, 400), exc.code, exc.message, exc.details
        ) from exc
    payload = result.as_dict()
    payload["data_sources"] = to_data_sources(payload["data_sources"])
    return payload
