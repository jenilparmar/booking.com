import json
import threading
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings
from app.models import CollectionRun, Review
from app.services.importer import ImportFileError, import_file
from tests.conftest import FIXTURES

NOW = datetime(2026, 10, 9, 1, 0, tzinfo=UTC)


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def review_count(db: Session) -> int:
    return db.scalar(select(func.count()).select_from(Review)) or 0


def test_import_csv_inserts_normalized_rows(db: Session) -> None:
    res = import_file(db, "valid.csv", fixture_bytes("valid.csv"), now=NOW)
    assert res.ok
    assert (res.discovered, res.inserted, res.duplicates, res.invalid) == (5, 5, 0, 0)
    assert review_count(db) == 5

    r2 = db.scalars(select(Review).where(Review.source_review_id == "FX-2")).one()
    assert r2.review_text == "Very noisy at night, thin walls."
    assert r2.review_title is None
    assert r2.published_at == datetime(2026, 10, 6, 10, 30, tzinfo=UTC)
    assert "Noise" in r2.topic_labels
    assert r2.source == "import"

    r3 = db.scalars(select(Review).where(Review.source_review_id == "FX-3")).one()
    assert r3.rating is None  # missing, not 0

    r5 = db.scalars(select(Review).where(Review.source_review_id == "FX-5")).one()
    assert r5.published_at is None

    no_id = db.scalars(select(Review).where(Review.property_id == "chateau-de-venus")).one()
    assert no_id.source_review_id is None and len(no_id.content_hash) == 64


def test_import_json_with_scale_conversion(db: Session) -> None:
    res = import_file(db, "valid.json", fixture_bytes("valid.json"), now=NOW)
    assert (res.inserted, res.invalid) == (2, 0)
    r = db.scalars(select(Review).where(Review.property_id == "chateau-de-venus")).one()
    assert r.rating == pytest.approx(8.88, abs=0.01)  # 4.5 on 1-5 -> 1-10


def test_import_is_idempotent(db: Session) -> None:
    first = import_file(db, "valid.csv", fixture_bytes("valid.csv"), now=NOW)
    snapshot = sorted(
        (r.property_id, r.source_review_id, r.content_hash) for r in db.scalars(select(Review))
    )
    second = import_file(db, "valid.csv", fixture_bytes("valid.csv"), now=NOW)
    assert first.inserted == 5
    assert (second.inserted, second.duplicates) == (0, 5)
    assert (
        sorted(
            (r.property_id, r.source_review_id, r.content_hash) for r in db.scalars(select(Review))
        )
        == snapshot
    )
    # A run that finds nothing new is still a success.
    assert all(r.status == "success" and r.inserted == 0 for r in second.runs)


def test_duplicates_within_file_and_by_content_hash(db: Session) -> None:
    rows = [
        {"property_id": "olympic-paddington", "source_review_id": "D-1", "review_text": "Nice"},
        {"property_id": "olympic-paddington", "source_review_id": "D-1", "review_text": "Nice"},
        {"property_id": "olympic-paddington", "review_text": "Same text no id"},
        {"property_id": "olympic-paddington", "review_text": "  same   TEXT no id "},
    ]
    res = import_file(db, "d.json", json.dumps(rows).encode(), now=NOW)
    assert (res.discovered, res.inserted, res.duplicates) == (4, 2, 2)


def test_bad_rows_reported_without_aborting_valid_rows(db: Session) -> None:
    res = import_file(db, "bad_rows.csv", fixture_bytes("bad_rows.csv"), now=NOW)
    assert res.ok
    assert (res.discovered, res.inserted, res.invalid) == (8, 1, 7)
    by_row = {e.row: e for e in res.errors}
    assert by_row[1].field == "rating" and "outside" in by_row[1].message
    assert by_row[2].field == "rating"
    assert by_row[3].field == "rating"
    assert by_row[4].field == "published_at"
    assert by_row[5].field == "published_at" and "future" in by_row[5].message
    assert by_row[6].field == "property_id"
    assert by_row[7].field == "review_text"
    run = db.scalars(select(CollectionRun)).one()
    assert run.property_id == "olympic-paddington"
    assert run.status == "partial"
    assert (run.discovered_count, run.inserted_count, run.error_count) == (7, 1, 6)
    assert run.error_summary and "Traceback" not in run.error_summary


def test_synthetic_labelling(db: Session) -> None:
    rows = [
        {"property_id": "olympic-paddington", "source_review_id": "SYNTH-x-1", "review_text": "a"},
        {"property_id": "olympic-paddington", "review_text": "b", "is_synthetic": True},
        {"property_id": "olympic-paddington", "review_text": "c", "source": "synthetic"},
        {"property_id": "olympic-paddington", "review_text": "d"},
    ]
    res = import_file(db, "s.json", json.dumps(rows).encode(), now=NOW)
    sources = {r.review_text: r.source for r in db.scalars(select(Review))}
    assert sources == {"a": "synthetic", "b": "synthetic", "c": "synthetic", "d": "import"}
    assert res.data_sources == ["import", "synthetic"]


def test_live_source_cannot_be_claimed_by_import(db: Session) -> None:
    rows = [{"property_id": "olympic-paddington", "review_text": "x", "source": "live"}]
    res = import_file(db, "l.json", json.dumps(rows).encode(), now=NOW)
    assert res.invalid == 1 and res.errors[0].field == "source"


@pytest.mark.parametrize(
    ("name", "content", "code"),
    [
        ("reviews.txt", b"anything", "unsupported_file_type"),
        ("reviews.xlsx", b"PK..", "unsupported_file_type"),
        ("reviews.csv", b"", "empty_file"),
        ("reviews.csv", b"foo,bar\n1,2\n", "invalid_structure"),
        ("reviews.csv", b'property_id,review_text\n"unterminated,x\n', "malformed_csv"),
        ("reviews.json", b"{not json", "malformed_json"),
        ("reviews.json", b'{"items": []}', "invalid_structure"),
        ("reviews.json", b"[]", "no_rows"),
        ("reviews.csv", b"\xff\xfe\x00bad", "invalid_encoding"),
    ],
)
def test_whole_file_errors(db: Session, name: str, content: bytes, code: str) -> None:
    with pytest.raises(ImportFileError) as exc:
        import_file(db, name, content, now=NOW)
    assert exc.value.code == code
    assert review_count(db) == 0
    assert db.scalar(select(func.count()).select_from(CollectionRun)) == 0


def test_oversize_file_rejected(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "import_max_bytes", 50)
    with pytest.raises(ImportFileError) as exc:
        import_file(db, "valid.csv", fixture_bytes("valid.csv"), now=NOW)
    assert exc.value.code == "file_too_large"


def test_too_many_rows_rejected(db: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(get_settings(), "import_max_rows", 2)
    with pytest.raises(ImportFileError) as exc:
        import_file(db, "valid.csv", fixture_bytes("valid.csv"), now=NOW)
    assert exc.value.code == "too_many_rows"


def test_ragged_csv_row_is_row_error(db: Session) -> None:
    content = b"property_id,review_text\nolympic-paddington,ok\nolympic-paddington,too,many\n"
    res = import_file(db, "r.csv", content, now=NOW)
    assert (res.inserted, res.invalid) == (1, 1)


def test_concurrent_imports_do_not_duplicate(session_factory: sessionmaker[Session]) -> None:
    content = fixture_bytes("valid.csv")
    results: list[int] = []
    errors: list[BaseException] = []
    barrier = threading.Barrier(3)

    def worker() -> None:
        try:
            with session_factory() as s:
                barrier.wait()
                results.append(import_file(s, "valid.csv", content, now=NOW).inserted)
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=120)
    assert not errors, errors
    assert len(results) == 3 and sum(results) == 5
    with session_factory() as s:
        assert review_count(s) == 5


def test_failed_db_write_keeps_existing_reviews(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    import_file(db, "valid.csv", fixture_bytes("valid.csv"), now=NOW)
    before = review_count(db)

    from sqlalchemy.exc import OperationalError

    real_execute = db.execute

    def failing_execute(stmt, *a, **kw):  # type: ignore[no-untyped-def]
        if getattr(stmt, "is_insert", False):
            raise OperationalError("insert", {}, Exception("simulated outage"))
        return real_execute(stmt, *a, **kw)

    monkeypatch.setattr(db, "execute", failing_execute)
    res = import_file(db, "valid.json", fixture_bytes("valid.json"), now=NOW)
    monkeypatch.undo()
    assert res.failed and res.inserted == 0
    assert review_count(db) == before
    failed_runs = db.scalars(select(CollectionRun).where(CollectionRun.status == "failed")).all()
    assert failed_runs and all("simulated" not in (r.error_summary or "") for r in failed_runs)
