// Mirrors backend/app/api/schemas.py. Keep in sync when the API changes.

export type DataSource = "live" | "imported" | "synthetic";
export type Sentiment = "positive" | "neutral" | "negative";
export type RunStatus = "running" | "success" | "partial" | "failed";

export const TOPICS = [
  "Cleanliness",
  "Check-in experience",
  "Staff/receptionist behaviour",
  "Noise",
  "Facilities",
  "Location",
  "Room condition",
  "Value for money",
] as const;
export type Topic = (typeof TOPICS)[number];

export interface Provenance {
  data_sources: DataSource[];
  contains_synthetic: boolean;
}

export interface ApiErrorBody {
  error: { code: string; message: string; details: unknown };
}

export interface Property {
  id: string;
  name: string;
  source_url: string | null;
  review_count: number;
  last_review_at: string | null;
}

export interface PropertiesResponse extends Provenance {
  items: Property[];
}

export interface Review {
  id: number;
  property_id: string;
  property_name: string;
  source_review_id: string | null;
  review_title: string | null;
  review_text: string;
  rating: number | null;
  published_at: string | null;
  language: string | null;
  sentiment_label: Sentiment;
  sentiment_score: number | null;
  topic_labels: string[];
  data_source: DataSource;
  collected_at: string;
}

export interface ReviewFilters {
  property_ids: string[];
  date_from: string | null;
  date_to: string | null;
  rating_min: number | null;
  rating_max: number | null;
  sentiment: string | null;
  topic: string | null;
  q: string | null;
  data_source: string | null;
  sort: string;
}

export interface ReviewPage extends Provenance {
  items: Review[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  filters: ReviewFilters;
}

export interface Period {
  start: string;
  end: string;
}

export interface PeriodStats {
  reviews: number;
  avg_rating: number | null;
  rated_reviews: number;
  positive: number;
  neutral: number;
  negative: number;
  pct_negative: number | null;
}

export interface TopicShare {
  topic: string;
  count: number;
  negative_reviews: number;
  pct_of_negative: number | null;
}

export interface Summary extends Provenance {
  timezone: string;
  as_of: string;
  current_period: Period;
  previous_period: Period;
  current: PeriodStats;
  previous: PeriodStats;
  avg_rating_change: number | null;
  review_count_change: number;
  pct_negative_change: number | null;
  top_negative_topic: TopicShare | null;
  excluded_undated: number;
}

export interface ComparisonRow {
  property_id: string;
  name: string;
  window: PeriodStats;
  current_week: PeriodStats;
  previous_week: PeriodStats;
  avg_rating_change: number | null;
  top_complaint: TopicShare | null;
}

export interface Comparison extends Provenance {
  timezone: string;
  as_of: string;
  window: Period;
  window_weeks: number;
  current_period: Period;
  previous_period: Period;
  properties: ComparisonRow[];
  excluded_undated: number;
}

export interface TrendPoint {
  week_start: string;
  reviews: number;
  avg_rating: number | null;
  rated_reviews: number;
  positive: number;
  neutral: number;
  negative: number;
}

export interface Trends extends Provenance {
  timezone: string;
  as_of: string;
  weeks: number;
  current_week_partial: boolean;
  overall: TrendPoint[];
  by_property: { property_id: string; name: string; points: TrendPoint[] }[];
  excluded_undated: number;
}

export interface TopicCount {
  topic: string;
  count: number;
  pct_of_negative: number | null;
}

export interface ExampleReview {
  id: number;
  property_id: string;
  review_title: string | null;
  review_text: string;
  rating: number | null;
  published_at: string | null;
  sentiment_score: number | null;
  data_source: DataSource;
}

export interface Topics extends Provenance {
  timezone: string;
  as_of: string;
  window: Period;
  window_weeks: number;
  method: string;
  total_reviews: number;
  negative_reviews: number;
  top_negative_topics: TopicCount[];
  cleanliness_share_of_negative: {
    negative_with_cleanliness: number;
    negative_reviews: number;
    pct: number | null;
    available: boolean;
  };
  worst_topic_by_property: {
    property_id: string;
    name: string;
    topic: string | null;
    count: number;
    negative_reviews: number;
    pct_of_negative: number | null;
  }[];
  rising_topics: {
    topic: string;
    recent_count: number;
    prior_count: number;
    change: number;
    recent_pct_of_negative: number | null;
    prior_pct_of_negative: number | null;
  }[];
  rising_periods: { recent: Period; prior: Period };
  examples: { topic: string; reviews: ExampleReview[] }[];
  excluded_undated: number;
}

export interface Run {
  id: number;
  property_id: string;
  adapter: string;
  started_at: string;
  finished_at: string | null;
  status: RunStatus;
  discovered_count: number;
  inserted_count: number;
  duplicate_count: number;
  error_count: number;
  error_summary: string | null;
}

export interface CollectionHealth extends Provenance {
  adapter: string;
  live_collection_supported: boolean;
  live_collection_note: string;
  properties: {
    property_id: string;
    name: string;
    last_success_at: string | null;
    latest_run: Run | null;
    review_count: number;
    recent_errors: string[];
  }[];
}

export interface ImportResult {
  ok: boolean;
  filename: string;
  file_type: string;
  discovered: number;
  inserted: number;
  duplicates: number;
  invalid: number;
  errors: { row: number; field: string | null; message: string }[];
  errors_truncated: boolean;
  runs: {
    property_id: string;
    run_id: number;
    status: string;
    discovered: number;
    inserted: number;
    duplicates: number;
    invalid: number;
  }[];
  data_sources: DataSource[];
  failure_message: string | null;
}
