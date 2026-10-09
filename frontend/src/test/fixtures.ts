import type { ImportResult, PeriodStats, Review, ReviewPage, Summary } from "@/lib/types";

export const emptyStats: PeriodStats = {
  reviews: 0,
  avg_rating: null,
  rated_reviews: 0,
  positive: 0,
  neutral: 0,
  negative: 0,
  pct_negative: null,
};

const period = { start: "2026-10-04T13:00:00Z", end: "2026-10-09T06:00:00Z" };

export function summary(overrides: Partial<Summary> = {}): Summary {
  return {
    data_sources: ["synthetic"],
    contains_synthetic: true,
    timezone: "Australia/Sydney",
    as_of: period.end,
    current_period: period,
    previous_period: { start: "2026-09-27T14:00:00Z", end: "2026-10-02T06:00:00Z" },
    current: { reviews: 26, avg_rating: 8, rated_reviews: 23, positive: 20, neutral: 2, negative: 4, pct_negative: 15.4 },
    previous: { reviews: 23, avg_rating: 6.9, rated_reviews: 22, positive: 15, neutral: 4, negative: 4, pct_negative: 17.4 },
    avg_rating_change: 1.1,
    review_count_change: 3,
    pct_negative_change: -2,
    top_negative_topic: { topic: "Facilities", count: 2, negative_reviews: 4, pct_of_negative: 50 },
    excluded_undated: 0,
    ...overrides,
  };
}

export function review(id: number, overrides: Partial<Review> = {}): Review {
  return {
    id,
    property_id: "venus-surry-hills",
    property_name: "Central Sydney",
    source_review_id: `SYNTH-${id}`,
    review_title: `Title ${id}`,
    review_text: `Review text ${id}`,
    rating: 7,
    published_at: "2026-10-04T01:00:00Z",
    language: "en",
    sentiment_label: "positive",
    sentiment_score: 0.5,
    topic_labels: ["Location"],
    data_source: "synthetic",
    collected_at: "2026-10-09T06:00:00Z",
    ...overrides,
  };
}

export function reviewPage(items: Review[], overrides: Partial<ReviewPage> = {}): ReviewPage {
  return {
    data_sources: ["synthetic"],
    contains_synthetic: true,
    items,
    total: items.length,
    page: 1,
    page_size: 20,
    total_pages: Math.max(1, Math.ceil(items.length / 20)),
    filters: {
      property_ids: [],
      date_from: null,
      date_to: null,
      rating_min: null,
      rating_max: null,
      sentiment: null,
      topic: null,
      q: null,
      data_source: null,
      sort: "newest",
    },
    ...overrides,
  };
}

export const importResult: ImportResult = {
  ok: true,
  filename: "reviews.csv",
  file_type: "csv",
  discovered: 5,
  inserted: 4,
  duplicates: 1,
  invalid: 0,
  errors: [],
  errors_truncated: false,
  runs: [{ property_id: "venus-surry-hills", run_id: 1, status: "success", discovered: 5, inserted: 4, duplicates: 1, invalid: 0 }],
  data_sources: ["imported"],
  failure_message: null,
};
