from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import CollectionRun, Property, Review
from app.seed import PROPERTY_IDS, seed_properties


def make_review(**overrides: object) -> Review:
    data: dict[str, object] = {
        "property_id": "olympic-paddington",
        "source_review_id": None,
        "review_text": "Lovely stay.",
        "rating": 8.0,
        "published_at": datetime(2026, 10, 1, 3, 0, tzinfo=UTC),
        "sentiment_label": "positive",
        "topic_labels": [],
        "source": "synthetic",
        "content_hash": "a" * 64,
    }
    data.update(overrides)
    return Review(**data)


def test_migration_creates_expected_schema(db: Session) -> None:
    insp = inspect(db.get_bind())
    assert {"properties", "reviews", "collection_runs", "alembic_version"} <= set(
        insp.get_table_names()
    )
    index_names = {i["name"] for i in insp.get_indexes("reviews")}
    assert {
        "uq_reviews_property_source_review_id",
        "uq_reviews_property_content_hash",
        "ix_reviews_property_published",
        "ix_reviews_rating",
        "ix_reviews_sentiment_label",
    } <= index_names
    # No reviewer PII columns.
    cols = {c["name"] for c in insp.get_columns("reviews")}
    assert not cols & {"reviewer_name", "reviewer_country", "author", "email"}


def test_seed_is_stable_and_idempotent(db: Session) -> None:
    assert sorted(db.scalars(select(Property.id))) == sorted(PROPERTY_IDS)
    assert seed_properties(db) == 0
    assert len(list(db.scalars(select(Property)))) == 4


@pytest.mark.parametrize("rating", [0, 0.5, 10.5, -1, 11])
def test_rating_check_constraint_rejects_out_of_range(db: Session, rating: float) -> None:
    db.add(make_review(rating=rating))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


@pytest.mark.parametrize("rating", [None, 1, 5.5, 10])
def test_rating_check_constraint_accepts_valid(db: Session, rating: float | None) -> None:
    db.add(make_review(rating=rating))
    db.commit()


def test_source_and_sentiment_check_constraints(db: Session) -> None:
    db.add(make_review(source="scraped"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(make_review(sentiment_label="great", content_hash="b" * 64))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_unique_source_review_id_per_property(db: Session) -> None:
    db.add(make_review(source_review_id="R1", content_hash="1" * 64))
    db.commit()
    db.add(make_review(source_review_id="R1", content_hash="2" * 64))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    # Same source id on a different property is allowed.
    db.add(make_review(property_id="chateau-de-venus", source_review_id="R1", content_hash="3" * 64))
    db.commit()


def test_null_source_review_ids_do_not_collide(db: Session) -> None:
    db.add(make_review(source_review_id=None, content_hash="4" * 64))
    db.add(make_review(source_review_id=None, content_hash="5" * 64))
    db.commit()


def test_unique_content_hash_per_property(db: Session) -> None:
    db.add(make_review(content_hash="c" * 64))
    db.commit()
    db.add(make_review(content_hash="c" * 64, source_review_id="other"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_foreign_key_integrity(db: Session) -> None:
    db.add(make_review(property_id="does-not-exist"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()
    db.add(CollectionRun(property_id="does-not-exist", status="success"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_run_status_constraint(db: Session) -> None:
    db.add(CollectionRun(property_id="olympic-paddington", status="exploded"))
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_datetimes_round_trip_as_aware_utc(db: Session) -> None:
    db.add(make_review(content_hash="d" * 64))
    db.commit()
    db.expire_all()
    r = db.scalars(select(Review)).one()
    assert r.published_at == datetime(2026, 10, 1, 3, 0, tzinfo=UTC)
    assert r.published_at is not None and r.published_at.tzinfo is not None
