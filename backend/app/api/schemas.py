from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DataSource = Literal["live", "imported", "synthetic"]
SOURCE_TO_DATA_SOURCE: dict[str, DataSource] = {
    "live": "live",
    "import": "imported",
    "synthetic": "synthetic",
}


def to_data_sources(sources: list[str]) -> list[DataSource]:
    return sorted({SOURCE_TO_DATA_SOURCE[s] for s in sources if s in SOURCE_TO_DATA_SOURCE})


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: object | None = None


class ErrorResponse(BaseModel):
    error: ErrorDetail


class Provenance(BaseModel):
    data_sources: list[DataSource] = Field(
        description="Origins of the data behind this response: live, imported, synthetic."
    )
    contains_synthetic: bool


class HealthOut(BaseModel):
    status: Literal["ok", "degraded"]
    database: Literal["ok", "unavailable"]
    version: str


class PropertyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    source_url: str | None
    review_count: int
    last_review_at: datetime | None


class PropertiesOut(Provenance):
    items: list[PropertyOut]


class ReviewOut(BaseModel):
    id: int
    property_id: str
    property_name: str
    source_review_id: str | None
    review_title: str | None
    review_text: str
    rating: float | None
    published_at: datetime | None
    language: str | None
    sentiment_label: Literal["positive", "neutral", "negative"]
    sentiment_score: float | None
    topic_labels: list[str]
    data_source: DataSource
    collected_at: datetime


class ReviewFilters(BaseModel):
    property_ids: list[str]
    date_from: str | None
    date_to: str | None
    rating_min: float | None
    rating_max: float | None
    sentiment: str | None
    topic: str | None
    q: str | None
    data_source: str | None
    sort: str


class ReviewPage(Provenance):
    items: list[ReviewOut]
    total: int
    page: int
    page_size: int
    total_pages: int
    filters: ReviewFilters


# ---------------------------------------------------------------- analytics


class PeriodOut(BaseModel):
    start: datetime
    end: datetime


class PeriodStats(BaseModel):
    reviews: int
    avg_rating: float | None = Field(description="Mean of non-null ratings (1-10).")
    rated_reviews: int = Field(description="Denominator for avg_rating.")
    positive: int
    neutral: int
    negative: int
    pct_negative: float | None = Field(description="negative / reviews * 100; null if no reviews.")


class TopicShare(BaseModel):
    topic: str
    count: int
    negative_reviews: int
    pct_of_negative: float | None


class SummaryOut(Provenance):
    timezone: str
    as_of: datetime
    current_period: PeriodOut
    previous_period: PeriodOut
    current: PeriodStats
    previous: PeriodStats
    avg_rating_change: float | None
    review_count_change: int
    pct_negative_change: float | None
    top_negative_topic: TopicShare | None
    excluded_undated: int = Field(description="Reviews without a published date (excluded).")


class PropertyComparisonRow(BaseModel):
    property_id: str
    name: str
    window: PeriodStats
    current_week: PeriodStats
    previous_week: PeriodStats
    avg_rating_change: float | None
    top_complaint: TopicShare | None


class ComparisonOut(Provenance):
    timezone: str
    as_of: datetime
    window: PeriodOut
    window_weeks: int
    current_period: PeriodOut
    previous_period: PeriodOut
    properties: list[PropertyComparisonRow]
    excluded_undated: int


class TrendPoint(BaseModel):
    week_start: str
    reviews: int
    avg_rating: float | None
    rated_reviews: int
    positive: int
    neutral: int
    negative: int


class PropertyTrend(BaseModel):
    property_id: str
    name: str
    points: list[TrendPoint]


class TrendsOut(Provenance):
    timezone: str
    as_of: datetime
    weeks: int
    current_week_partial: bool
    overall: list[TrendPoint]
    by_property: list[PropertyTrend]
    excluded_undated: int


class TopicCount(BaseModel):
    topic: str
    count: int
    pct_of_negative: float | None


class CleanlinessShare(BaseModel):
    negative_with_cleanliness: int
    negative_reviews: int = Field(description="Sample size (denominator).")
    pct: float | None = Field(description="Null when there are no negative reviews.")
    available: bool


class WorstTopic(BaseModel):
    property_id: str
    name: str
    topic: str | None
    count: int
    negative_reviews: int
    pct_of_negative: float | None


class RisingTopic(BaseModel):
    topic: str
    recent_count: int
    prior_count: int
    change: int
    recent_pct_of_negative: float | None
    prior_pct_of_negative: float | None


class ExampleReview(BaseModel):
    id: int
    property_id: str
    review_title: str | None
    review_text: str
    rating: float | None
    published_at: datetime | None
    sentiment_score: float | None
    data_source: DataSource


class TopicExamples(BaseModel):
    topic: str
    reviews: list[ExampleReview]


class RisingPeriods(BaseModel):
    recent: PeriodOut
    prior: PeriodOut


class TopicsOut(Provenance):
    timezone: str
    as_of: datetime
    window: PeriodOut
    window_weeks: int
    method: str
    total_reviews: int
    negative_reviews: int
    top_negative_topics: list[TopicCount]
    cleanliness_share_of_negative: CleanlinessShare
    worst_topic_by_property: list[WorstTopic]
    rising_topics: list[RisingTopic]
    rising_periods: RisingPeriods
    examples: list[TopicExamples]
    excluded_undated: int


# ---------------------------------------------------------------- collection / import


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    property_id: str
    adapter: str
    started_at: datetime
    finished_at: datetime | None
    status: Literal["running", "success", "partial", "failed"]
    discovered_count: int
    inserted_count: int
    duplicate_count: int
    error_count: int
    error_summary: str | None


class RunsOut(BaseModel):
    items: list[RunOut]


class PropertyHealth(BaseModel):
    property_id: str
    name: str
    last_success_at: datetime | None
    latest_run: RunOut | None
    review_count: int
    recent_errors: list[str]


class CollectionHealthOut(Provenance):
    adapter: str
    live_collection_supported: bool
    live_collection_note: str
    properties: list[PropertyHealth]


class RowErrorOut(BaseModel):
    row: int
    field: str | None
    message: str


class RunSummaryOut(BaseModel):
    property_id: str
    run_id: int
    status: str
    discovered: int
    inserted: int
    duplicates: int
    invalid: int


class ImportOut(BaseModel):
    ok: bool
    filename: str
    file_type: str
    discovered: int
    inserted: int
    duplicates: int
    invalid: int
    errors: list[RowErrorOut]
    errors_truncated: bool
    runs: list[RunSummaryOut]
    data_sources: list[DataSource]
    failure_message: str | None
