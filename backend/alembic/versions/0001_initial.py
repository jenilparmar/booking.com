"""initial schema: properties, reviews, collection_runs

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TSTZ = sa.DateTime(timezone=True)
NOW = sa.text("now()")


def upgrade() -> None:
    op.create_table(
        "properties",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source_url", sa.String(500)),
        sa.Column("created_at", TSTZ, nullable=False, server_default=NOW),
        sa.Column("updated_at", TSTZ, nullable=False, server_default=NOW),
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.Integer, sa.Identity(), primary_key=True),
        sa.Column(
            "property_id",
            sa.String(64),
            sa.ForeignKey("properties.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("source_review_id", sa.String(200)),
        sa.Column("review_text", sa.Text, nullable=False),
        sa.Column("review_title", sa.String(500)),
        sa.Column("rating", sa.Float),
        sa.Column("published_at", TSTZ),
        sa.Column("language", sa.String(16)),
        sa.Column("sentiment_label", sa.String(16), nullable=False),
        sa.Column("sentiment_score", sa.Float),
        sa.Column("topic_labels", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("collected_at", TSTZ, nullable=False, server_default=NOW),
        sa.Column("created_at", TSTZ, nullable=False, server_default=NOW),
        sa.Column("updated_at", TSTZ, nullable=False, server_default=NOW),
        sa.CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 10)", name="ck_rating_range"
        ),
        sa.CheckConstraint("source IN ('live', 'import', 'synthetic')", name="ck_review_source"),
        sa.CheckConstraint(
            "sentiment_label IN ('positive', 'neutral', 'negative')", name="ck_sentiment_label"
        ),
        sa.CheckConstraint(
            "sentiment_score IS NULL OR (sentiment_score >= -1 AND sentiment_score <= 1)",
            name="ck_sentiment_score_range",
        ),
        sa.CheckConstraint("length(review_text) > 0", name="ck_review_text_nonempty"),
        sa.CheckConstraint("jsonb_typeof(topic_labels) = 'array'", name="ck_topic_labels_array"),
    )
    op.create_index(
        "uq_reviews_property_source_review_id",
        "reviews",
        ["property_id", "source_review_id"],
        unique=True,
        postgresql_where=sa.text("source_review_id IS NOT NULL"),
    )
    op.create_index(
        "uq_reviews_property_content_hash", "reviews", ["property_id", "content_hash"], unique=True
    )
    op.create_index("ix_reviews_property_published", "reviews", ["property_id", "published_at"])
    op.create_index("ix_reviews_rating", "reviews", ["rating"])
    op.create_index("ix_reviews_sentiment_label", "reviews", ["sentiment_label"])
    op.create_index("ix_reviews_published_at", "reviews", ["published_at"])
    op.create_index(
        "ix_reviews_topic_labels_gin", "reviews", ["topic_labels"], postgresql_using="gin"
    )

    op.create_table(
        "collection_runs",
        sa.Column("id", sa.Integer, sa.Identity(), primary_key=True),
        sa.Column(
            "property_id",
            sa.String(64),
            sa.ForeignKey("properties.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("adapter", sa.String(32), nullable=False),
        sa.Column("started_at", TSTZ, nullable=False, server_default=NOW),
        sa.Column("finished_at", TSTZ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("discovered_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("inserted_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("duplicate_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error_summary", sa.Text),
        sa.CheckConstraint(
            "status IN ('running', 'success', 'partial', 'failed')", name="ck_run_status"
        ),
        sa.CheckConstraint(
            "discovered_count >= 0 AND inserted_count >= 0 AND duplicate_count >= 0 "
            "AND error_count >= 0",
            name="ck_run_counts_nonnegative",
        ),
    )
    op.create_index(
        "ix_collection_runs_property_started", "collection_runs", ["property_id", "started_at"]
    )


def downgrade() -> None:
    op.drop_table("collection_runs")
    op.drop_table("reviews")
    op.drop_table("properties")
