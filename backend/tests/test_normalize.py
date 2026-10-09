from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from app.services.normalize import (
    FieldError,
    content_hash,
    normalize_language,
    normalize_rating,
    normalize_text,
    parse_datetime,
)

SYD = ZoneInfo("Australia/Sydney")
NOW = datetime(2026, 10, 9, 1, 0, tzinfo=UTC)


def test_normalize_text_collapses_whitespace() -> None:
    assert normalize_text("  Very\tnoisy \n\n at\u00a0night  ") == "Very noisy at night"


@pytest.mark.parametrize("v", [None, "", "   ", "\n\t"])
def test_normalize_text_blank_is_none(v: object) -> None:
    assert normalize_text(v) is None


def test_normalize_text_too_long() -> None:
    with pytest.raises(FieldError):
        normalize_text("x" * 20_001)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-10-06T10:00:00+11:00", datetime(2026, 10, 5, 23, 0, tzinfo=UTC)),
        ("2026-10-06T10:00:00Z", datetime(2026, 10, 6, 10, 0, tzinfo=UTC)),
        # Naive -> business timezone (AEDT, UTC+11 in October).
        ("2026-10-06 10:00", datetime(2026, 10, 5, 23, 0, tzinfo=UTC)),
        ("2026-10-06", datetime(2026, 10, 5, 13, 0, tzinfo=UTC)),
        # Day-first for non-ISO numeric dates.
        ("03/04/2026", datetime(2026, 4, 2, 13, 0, tzinfo=UTC)),  # 3 April, AEDT
        ("06/10/2026 21:30", datetime(2026, 10, 6, 10, 30, tzinfo=UTC)),
        ("5 October 2026", datetime(2026, 10, 4, 13, 0, tzinfo=UTC)),
        ("2026/10/01", datetime(2026, 9, 30, 14, 0, tzinfo=UTC)),  # AEST, before DST starts
    ],
)
def test_parse_datetime_formats(raw: str, expected: datetime) -> None:
    got = parse_datetime(raw, tz=SYD, now=NOW)
    assert got == expected
    assert got is not None and got.tzinfo is not None


@pytest.mark.parametrize("raw", ["not a date", "2099-01-01", "1999-12-31", "32/13/2026"])
def test_parse_datetime_rejects_bad(raw: str) -> None:
    with pytest.raises(FieldError):
        parse_datetime(raw, tz=SYD, now=NOW)


def test_parse_datetime_blank_is_none() -> None:
    assert parse_datetime("", tz=SYD, now=NOW) is None
    assert parse_datetime(None, tz=SYD, now=NOW) is None


@pytest.mark.parametrize(
    ("raw", "expected"), [("9", 9.0), (7.5, 7.5), ("8,5", 8.5), (1, 1.0), ("10", 10.0)]
)
def test_rating_valid(raw: object, expected: float) -> None:
    assert normalize_rating(raw) == expected


@pytest.mark.parametrize("raw", [None, "", "  "])
def test_rating_missing_is_none_not_zero(raw: object) -> None:
    assert normalize_rating(raw) is None


@pytest.mark.parametrize("raw", ["0", 0, "11", -3, "abc", "nan", True])
def test_rating_invalid(raw: object) -> None:
    with pytest.raises(FieldError):
        normalize_rating(raw)


def test_rating_scale_conversion_5_to_10() -> None:
    assert normalize_rating(5, scale_min=1, scale_max=5) == 10.0
    assert normalize_rating(1, scale_min=1, scale_max=5) == 1.0
    assert normalize_rating(3, scale_min=1, scale_max=5) == 5.5
    with pytest.raises(FieldError):
        normalize_rating(6, scale_min=1, scale_max=5)


def test_language() -> None:
    assert normalize_language("EN") == "en"
    assert normalize_language("en_AU") == "en-au"
    assert normalize_language("") is None
    with pytest.raises(FieldError):
        normalize_language("english!!")


def test_content_hash_is_stable_and_normalizes() -> None:
    dt = datetime(2026, 10, 1, tzinfo=UTC)
    a = content_hash("p", "Nice  Stay", "Title", dt, 8)
    b = content_hash("p", "nice stay", "title", dt.astimezone(SYD), 8.0)
    assert a == b and len(a) == 64
    assert a != content_hash("p", "nice stay", "title", dt, None)
    assert a != content_hash("q", "nice stay", "title", dt, 8)
    assert content_hash("p", "x", None, None, None) == content_hash("p", "x", "", None, None)
