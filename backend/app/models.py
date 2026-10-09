from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base, UTCDateTime

REVIEW_SOURCES = ("live", "import", "synthetic")
SENTIMENT_LABELS = ("positive", "neutral", "negative")
RUN_STATUSES = ("running", "success", "partial", "failed")


def utcnow() -> datetime:
    return datetime.now(UTC)


class Property(Base):
    __tablename__ = "properties"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow
    )

    reviews: Mapped[list["Review"]] = relationship(back_populates="property")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (
        CheckConstraint("rating IS NULL OR (rating >= 1 AND rating <= 10)", name="ck_rating_range"),
        CheckConstraint(
            "source IN ('live', 'import', 'synthetic')", name="ck_review_source"
        ),
        CheckConstraint(
            "sentiment_label IN ('positive', 'neutral', 'negative')", name="ck_sentiment_label"
        ),
        CheckConstraint(
            "sentiment_score IS NULL OR (sentiment_score >= -1 AND sentiment_score <= 1)",
            name="ck_sentiment_score_range",
        ),
        CheckConstraint("length(review_text) > 0", name="ck_review_text_nonempty"),
        Index(
            "uq_reviews_property_source_review_id",
            "property_id",
            "source_review_id",
            unique=True,
            sqlite_where=text("source_review_id IS NOT NULL"),
            postgresql_where=text("source_review_id IS NOT NULL"),
        ),
        Index("uq_reviews_property_content_hash", "property_id", "content_hash", unique=True),
        Index("ix_reviews_property_published", "property_id", "published_at"),
        Index("ix_reviews_rating", "rating"),
        Index("ix_reviews_sentiment_label", "sentiment_label"),
        Index("ix_reviews_published_at", "published_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    property_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False
    )
    source_review_id: Mapped[str | None] = mapped_column(String(200))
    review_text: Mapped[str] = mapped_column(Text, nullable=False)
    review_title: Mapped[str | None] = mapped_column(String(500))
    rating: Mapped[float | None] = mapped_column(Float)
    published_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    language: Mapped[str | None] = mapped_column(String(16))
    sentiment_label: Mapped[str] = mapped_column(String(16), nullable=False)
    sentiment_score: Mapped[float | None] = mapped_column(Float)
    topic_labels: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(16), nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), default=utcnow, onupdate=utcnow
    )

    property: Mapped[Property] = relationship(back_populates="reviews")


class CollectionRun(Base):
    __tablename__ = "collection_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'success', 'partial', 'failed')", name="ck_run_status"
        ),
        CheckConstraint(
            "discovered_count >= 0 AND inserted_count >= 0 AND duplicate_count >= 0 "
            "AND error_count >= 0",
            name="ck_run_counts_nonnegative",
        ),
        Index("ix_collection_runs_property_started", "property_id", "started_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    property_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("properties.id", ondelete="RESTRICT"), nullable=False
    )
    adapter: Mapped[str] = mapped_column(String(32), nullable=False, default="import")
    started_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    discovered_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    inserted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text)

    def as_dict(self) -> dict[str, Any]:
        return {c.name: getattr(self, c.name) for c in self.__table__.columns}
