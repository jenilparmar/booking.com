"""CSV/JSON review importer.

Flow: validate file -> parse rows -> normalize + validate each row (bad rows are reported, good
rows continue) -> enrich (topics, sentiment) -> one transaction of batched
``INSERT ... ON CONFLICT DO NOTHING RETURNING`` -> one CollectionRun per property.

Dedup is enforced by the database's unique indexes, so re-importing the same file, or two imports
running at once, cannot create duplicates. Nothing here relies on session-level state, so it is
safe over Neon's pooled (transaction-mode) endpoint.
"""

import csv
import io
import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import PurePath
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import CollectionRun, Property, Review
from app.services.normalize import (
    MAX_TITLE_LEN,
    FieldError,
    content_hash,
    is_blank,
    normalize_language,
    normalize_rating,
    normalize_text,
    parse_datetime,
)
from app.services.processing import enrich

ALLOWED_EXTENSIONS = {".csv": "csv", ".json": "json"}
REQUIRED_FIELDS = ("property_id", "review_text")
KNOWN_FIELDS = {
    "property_id",
    "source_review_id",
    "review_text",
    "review_title",
    "rating",
    "rating_scale_max",
    "published_at",
    "language",
    "source",
    "is_synthetic",
}
IMPORT_SOURCES = {"import", "synthetic"}
INSERT_BATCH = 500
MAX_REPORTED_ERRORS = 100


class ImportFileError(Exception):
    """Whole-file problem (wrong type, too big, unparseable). Nothing is written."""

    def __init__(self, code: str, message: str, details: Any = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details


@dataclass
class RowError:
    row: int
    field: str | None
    message: str


@dataclass
class RunSummary:
    property_id: str
    run_id: int
    status: str
    discovered: int
    inserted: int
    duplicates: int
    invalid: int


@dataclass
class ImportResult:
    filename: str
    file_type: str
    discovered: int = 0
    inserted: int = 0
    duplicates: int = 0
    invalid: int = 0
    errors: list[RowError] = field(default_factory=list)
    errors_truncated: bool = False
    runs: list[RunSummary] = field(default_factory=list)
    data_sources: list[str] = field(default_factory=list)
    failed: bool = False
    failure_message: str | None = None

    @property
    def ok(self) -> bool:
        return not self.failed

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ok"] = self.ok
        return d


def _truthy(v: Any) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "y", "t"}


def _parse_rows(filename: str, content: bytes) -> tuple[str, list[dict[str, Any]]]:
    settings = get_settings()
    ext = PurePath(filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ImportFileError(
            "unsupported_file_type",
            "Only .csv and .json files are accepted.",
            {"filename": filename},
        )
    if len(content) == 0:
        raise ImportFileError("empty_file", "The uploaded file is empty.")
    if len(content) > settings.import_max_bytes:
        raise ImportFileError(
            "file_too_large",
            f"File exceeds the {settings.import_max_bytes // (1024 * 1024)} MB limit.",
            {"max_bytes": settings.import_max_bytes, "size_bytes": len(content)},
        )
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ImportFileError("invalid_encoding", "File must be UTF-8 encoded.") from exc

    file_type = ALLOWED_EXTENSIONS[ext]
    rows: list[dict[str, Any]]
    if file_type == "csv":
        try:
            reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
            header = reader.fieldnames or []
            header_set = {h.strip() for h in header if h}
            missing = [f for f in REQUIRED_FIELDS if f not in header_set]
            if missing:
                raise ImportFileError(
                    "invalid_structure",
                    "CSV header is missing required columns.",
                    {"missing_columns": missing},
                )
            rows = []
            for raw in reader:
                if None in raw:
                    rows.append({"__error__": "row has more columns than the header"})
                    continue
                rows.append({(k or "").strip(): v for k, v in raw.items()})
        except csv.Error as exc:
            raise ImportFileError("malformed_csv", f"CSV could not be parsed: {exc}") from exc
    else:
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ImportFileError(
                "malformed_json",
                f"JSON could not be parsed (line {exc.lineno}, column {exc.colno}).",
            ) from exc
        if isinstance(data, dict) and isinstance(data.get("reviews"), list):
            data = data["reviews"]
        if not isinstance(data, list):
            raise ImportFileError(
                "invalid_structure",
                'JSON must be an array of review objects or {"reviews": [...]}.',
            )
        rows = [r if isinstance(r, dict) else {"__error__": "item is not an object"} for r in data]

    if not rows:
        raise ImportFileError("no_rows", "The file contains no review rows.")
    if len(rows) > settings.import_max_rows:
        raise ImportFileError(
            "too_many_rows",
            f"File has {len(rows)} rows; the limit is {settings.import_max_rows}.",
        )
    return file_type, rows


def _normalize_row(
    raw: dict[str, Any],
    *,
    known_properties: set[str],
    default_source: str,
    tz: ZoneInfo,
    now: datetime,
) -> dict[str, Any]:
    settings = get_settings()
    if "__error__" in raw:
        raise FieldError("row", raw["__error__"])

    prop = normalize_text(raw.get("property_id"), field="property_id", max_len=64)
    if prop is None:
        raise FieldError("property_id", "required")
    if prop not in known_properties:
        raise FieldError("property_id", f"unknown property {prop!r}")

    text = normalize_text(raw.get("review_text"))
    if text is None:
        raise FieldError("review_text", "required")
    title = normalize_text(raw.get("review_title"), field="review_title", max_len=MAX_TITLE_LEN)

    scale_max = settings.rating_scale_max
    if not is_blank(raw.get("rating_scale_max")):
        try:
            scale_max = float(raw["rating_scale_max"])
        except (TypeError, ValueError) as exc:
            raise FieldError("rating_scale_max", "must be a number") from exc
        if scale_max <= settings.rating_scale_min:
            raise FieldError("rating_scale_max", "must be greater than the scale minimum")
    rating = normalize_rating(
        raw.get("rating"),
        scale_min=settings.rating_scale_min,
        scale_max=scale_max,
        target_min=settings.rating_scale_min,
        target_max=settings.rating_scale_max,
    )
    published = parse_datetime(raw.get("published_at"), tz=tz, now=now)
    language = normalize_language(raw.get("language"))

    source_review_id = normalize_text(
        raw.get("source_review_id"), field="source_review_id", max_len=200
    )

    source = default_source
    raw_source = normalize_text(raw.get("source"), field="source", max_len=16)
    if raw_source is not None:
        raw_source = raw_source.lower()
        if raw_source not in IMPORT_SOURCES:
            raise FieldError("source", "must be 'import' or 'synthetic' for file imports")
        source = raw_source
    if _truthy(raw.get("is_synthetic", "")) or (source_review_id or "").startswith("SYNTH-"):
        source = "synthetic"

    e = enrich(text, title, language)
    return {
        "property_id": prop,
        "source_review_id": source_review_id,
        "review_text": text,
        "review_title": title,
        "rating": rating,
        "published_at": published,
        "language": language,
        "sentiment_label": e.sentiment_label,
        "sentiment_score": e.sentiment_score,
        "topic_labels": e.topic_labels,
        "source": source,
        "content_hash": content_hash(prop, text, title, published, rating),
        "collected_at": now,
        "created_at": now,
        "updated_at": now,
    }


def insert_reviews(db: Session, rows: list[dict[str, Any]]) -> Counter[str]:
    """Batched INSERT ... ON CONFLICT DO NOTHING. Returns inserted counts per property.

    Does not commit; the caller owns the transaction.
    """
    inserted: Counter[str] = Counter()
    for start in range(0, len(rows), INSERT_BATCH):
        chunk = rows[start : start + INSERT_BATCH]
        stmt = (
            pg_insert(Review).values(chunk).on_conflict_do_nothing().returning(Review.property_id)
        )
        for (prop,) in db.execute(stmt):
            inserted[prop] += 1
    return inserted


def normalize_row(
    raw: dict[str, Any], *, known_properties: set[str], default_source: str, now: datetime
) -> dict[str, Any]:
    tz = ZoneInfo(get_settings().business_timezone)
    return _normalize_row(
        raw, known_properties=known_properties, default_source=default_source, tz=tz, now=now
    )


def import_file(
    db: Session,
    filename: str,
    content: bytes,
    *,
    default_source: str = "import",
    now: datetime | None = None,
) -> ImportResult:
    """Import reviews from an uploaded file. Raises ImportFileError for whole-file problems."""
    if default_source not in IMPORT_SOURCES:
        raise ValueError("default_source must be 'import' or 'synthetic'")
    settings = get_settings()
    tz = ZoneInfo(settings.business_timezone)
    now = now or datetime.now(UTC)

    file_type, raw_rows = _parse_rows(filename, content)
    result = ImportResult(filename=PurePath(filename).name, file_type=file_type)
    result.discovered = len(raw_rows)

    known = set(db.scalars(select(Property.id)))
    valid: list[dict[str, Any]] = []
    per_prop_discovered: Counter[str] = Counter()
    per_prop_invalid: Counter[str] = Counter()
    per_prop_errors: defaultdict[str, list[str]] = defaultdict(list)

    for i, raw in enumerate(raw_rows, start=1):
        prop_hint = str(raw.get("property_id") or "").strip()
        if prop_hint in known:
            per_prop_discovered[prop_hint] += 1
        try:
            valid.append(
                _normalize_row(
                    raw, known_properties=known, default_source=default_source, tz=tz, now=now
                )
            )
        except FieldError as fe:
            result.invalid += 1
            if len(result.errors) < MAX_REPORTED_ERRORS:
                result.errors.append(RowError(i, fe.field, fe.message))
            else:
                result.errors_truncated = True
            if prop_hint in known:
                per_prop_invalid[prop_hint] += 1
                if len(per_prop_errors[prop_hint]) < 5:
                    per_prop_errors[prop_hint].append(f"row {i}: {fe.field}: {fe.message}")

    # Open one "running" run per property up front so in-progress imports are visible.
    runs: dict[str, CollectionRun] = {}
    for prop in sorted(per_prop_discovered):
        run = CollectionRun(property_id=prop, adapter="import", started_at=now, status="running")
        db.add(run)
        runs[prop] = run
    db.commit()

    inserted_by_prop: Counter[str] = Counter()
    try:
        inserted_by_prop = insert_reviews(db, valid)
        valid_by_prop = Counter(r["property_id"] for r in valid)
        finished = datetime.now(UTC)
        for prop, run in runs.items():
            run.discovered_count = per_prop_discovered[prop]
            run.inserted_count = inserted_by_prop[prop]
            run.duplicate_count = valid_by_prop[prop] - inserted_by_prop[prop]
            run.error_count = per_prop_invalid[prop]
            run.error_summary = "; ".join(per_prop_errors[prop]) or None
            if run.error_count == 0:
                run.status = "success"
            elif valid_by_prop[prop] > 0:
                run.status = "partial"
            else:
                run.status = "failed"
            run.finished_at = finished
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        finished = datetime.now(UTC)
        for prop, run in runs.items():
            run.status = "failed"
            run.finished_at = finished
            run.discovered_count = per_prop_discovered[prop]
            run.inserted_count = 0
            run.duplicate_count = 0
            run.error_count = per_prop_discovered[prop]
            run.error_summary = "Database write failed; no reviews from this import were saved."
        db.commit()
        result.failed = True
        result.failure_message = "Database write failed; no reviews from this import were saved."
        inserted_by_prop.clear()

    result.inserted = sum(inserted_by_prop.values())
    result.duplicates = 0 if result.failed else len(valid) - result.inserted
    result.data_sources = sorted({r["source"] for r in valid})
    result.runs = [
        RunSummary(
            property_id=p,
            run_id=r.id,
            status=r.status,
            discovered=r.discovered_count,
            inserted=r.inserted_count,
            duplicates=r.duplicate_count,
            invalid=r.error_count,
        )
        for p, r in runs.items()
    ]
    return result
