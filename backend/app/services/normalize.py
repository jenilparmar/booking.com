"""Field normalizers shared by the importer and any future collector adapters.

Missing values always normalize to ``None`` (stored as NULL), never to 0 or "".
"""

import hashlib
import re
from datetime import UTC, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from dateutil import parser as date_parser


class FieldError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


_WS = re.compile(r"\s+")
_ISO_DATE_ONLY = re.compile(r"^\d{4}-\d{2}-\d{2}$")

MAX_TEXT_LEN = 20_000
MAX_TITLE_LEN = 500


def is_blank(value: Any) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def normalize_text(
    value: Any, *, field: str = "review_text", max_len: int = MAX_TEXT_LEN
) -> str | None:
    """Collapse runs of whitespace (incl. newlines/tabs/nbsp) to single spaces and strip."""
    if is_blank(value):
        return None
    if not isinstance(value, str):
        value = str(value)
    text = _WS.sub(" ", value.replace("\u00a0", " ")).strip()
    if not text:
        return None
    if len(text) > max_len:
        raise FieldError(field, f"longer than {max_len} characters")
    return text


def parse_datetime(
    value: Any, *, tz: ZoneInfo, now: datetime | None = None, field: str = "published_at"
) -> datetime | None:
    """Parse ISO 8601 or common human formats into an aware UTC datetime.

    * Values with an offset/``Z`` keep that offset.
    * Naive values are interpreted in the business timezone ``tz``.
    * Non-ISO numeric dates are read day-first (``03/04/2026`` = 3 April), matching AU usage.
    * Dates more than one day in the future are rejected.
    """
    if is_blank(value):
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        raw = str(value).strip()
        try:
            if _ISO_DATE_ONLY.match(raw) or "T" in raw or raw[:4].isdigit():
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            else:
                raise ValueError
        except ValueError:
            year_first = raw[:4].isdigit()
            try:
                dt = date_parser.parse(raw, dayfirst=not year_first, yearfirst=year_first)
            except (ValueError, OverflowError) as exc:
                raise FieldError(field, f"unrecognised date format: {raw[:40]!r}") from exc
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=tz)
    dt = dt.astimezone(UTC)
    now = now or datetime.now(UTC)
    if dt > now + timedelta(days=1):
        raise FieldError(field, "date is in the future")
    if dt.year < 2000:
        raise FieldError(field, "date is before 2000")
    return dt


def normalize_rating(
    value: Any,
    *,
    scale_min: float = 1.0,
    scale_max: float = 10.0,
    target_min: float = 1.0,
    target_max: float = 10.0,
    field: str = "rating",
) -> float | None:
    """Validate a rating on [scale_min, scale_max] and map it linearly onto the 1-10 scale."""
    if is_blank(value):
        return None
    if isinstance(value, bool):
        raise FieldError(field, "rating must be a number")
    try:
        r = float(str(value).strip().replace(",", ".")) if isinstance(value, str) else float(value)
    except (TypeError, ValueError) as exc:
        raise FieldError(field, f"rating is not a number: {str(value)[:20]!r}") from exc
    if r != r or r in (float("inf"), float("-inf")):
        raise FieldError(field, "rating is not a finite number")
    if not scale_min <= r <= scale_max:
        raise FieldError(field, f"rating {r:g} outside {scale_min:g}-{scale_max:g}")
    if (scale_min, scale_max) != (target_min, target_max):
        r = target_min + (r - scale_min) * (target_max - target_min) / (scale_max - scale_min)
    return round(r, 2)


def normalize_language(value: Any) -> str | None:
    if is_blank(value):
        return None
    lang = str(value).strip().lower().replace("_", "-")
    if not re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})?", lang):
        raise FieldError("language", f"invalid language code: {lang[:16]!r}")
    return lang


def content_hash(
    property_id: str,
    review_text: str,
    review_title: str | None,
    published_at: datetime | None,
    rating: float | None,
) -> str:
    """sha256 over normalized fields, used for dedup when no source_review_id exists.

    Inputs: property id, lower-cased whitespace-collapsed text and title, published_at as UTC ISO
    seconds, rating with two decimals. Missing values hash as the empty string. Fields are
    joined with the ASCII unit separator (0x1F) so field boundaries cannot collide.
    """
    parts = [
        property_id,
        _WS.sub(" ", review_text).strip().lower(),
        _WS.sub(" ", review_title or "").strip().lower(),
        published_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ") if published_at else "",
        f"{rating:.2f}" if rating is not None else "",
    ]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
