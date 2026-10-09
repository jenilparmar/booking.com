# API reference

Base URL (local): `http://127.0.0.1:8000`. Interactive OpenAPI docs: `/docs` (Swagger) and
`/redoc`; schema at `/openapi.json`.

The examples below are real responses captured from the local server with the synthetic sample
dataset loaded (long arrays trimmed with `…`).

## Conventions

- **Errors** always use one envelope; no stack traces, SQL, or configuration are ever returned:

  ```json
  {"error": {"code": "validation_error", "message": "One or more request parameters are invalid.",
             "details": [{"field": "sentiment", "location": "query",
                          "message": "Input should be 'positive', 'neutral' or 'negative'",
                          "type": "literal_error"}]}}
  ```

  | Status | `code` examples |
  | ------ | --------------- |
  | 400 | `malformed_csv`, `malformed_json`, `invalid_structure`, `empty_file`, `no_rows`, `too_many_rows`, `invalid_encoding` |
  | 404 | `not_found` |
  | 413 | `file_too_large` |
  | 415 | `unsupported_file_type`, `unsupported_media_type` |
  | 422 | `validation_error` |
  | 500 | `internal_error` (generic message only) |
  | 501 | `collection_unsupported` |
  | 503 | `database_unavailable` |

- **Provenance:** list and analytics responses include `data_sources` (any of `live`,
  `imported`, `synthetic`) and `contains_synthetic`. Each review carries its own `data_source`.
- **Time:** timestamps are ISO 8601 UTC. Week logic uses the business timezone
  (`Australia/Sydney` by default) and is reported as `timezone` in analytics responses.
  Analytics accept `as_of` (ISO 8601; naive = business timezone) to evaluate "now" at a fixed
  instant, which is useful for reproducible reports.
- **Missing data:** ratings and dates can be `null`. Averages report their denominator
  (`rated_reviews`); undated reviews are excluded from time-based figures and counted in
  `excluded_undated`.
- **Property filter:** `property_ids` can be repeated (`?property_ids=a&property_ids=b`) or
  comma-separated (`?property_ids=a,b`). Unknown ids return 422.

## Endpoints

### `GET /api/health`

```json
{"status": "ok", "database": "ok", "version": "0.1.0"}
```

### `GET /api/properties`

```json
{"data_sources": ["synthetic"], "contains_synthetic": true,
 "items": [{"id": "venus-surry-hills", "name": "Central Sydney",
            "source_url": "https://www.booking.com/hotel/au/venus-surry-hills.html",
            "review_count": 67, "last_review_at": "2026-10-08T10:46:18Z"}, …]}
```

### `GET /api/reviews`

| Param | Type | Notes |
| ----- | ---- | ----- |
| `property_ids` | string (repeatable / CSV) | |
| `date_from`, `date_to` | `YYYY-MM-DD` | Inclusive calendar dates in the business timezone |
| `rating_min`, `rating_max` | 1–10 | Excludes reviews with no rating |
| `sentiment` | `positive` \| `neutral` \| `negative` | Text sentiment |
| `topic` | one of the 8 topics | JSONB containment (`@>`), GIN-indexed |
| `q` | string ≤ 200 | Case-insensitive substring of title or text; `%`/`_` are literal |
| `data_source` | `live` \| `imported` \| `synthetic` | |
| `sort` | `newest` (default) \| `oldest` \| `rating` | Undated / unrated rows sort last |
| `page` | ≥ 1 | |
| `page_size` | 1–100 (`API_MAX_PAGE_SIZE`) | Default 20 |

All filters combine with AND and run in SQL. `filters` echoes the applied filters so pagination
links can preserve them.

`GET /api/reviews?property_ids=venus-surry-hills&sentiment=negative&topic=Noise&page_size=2`

```json
{"data_sources": ["synthetic"], "contains_synthetic": true,
 "items": [{"id": 263, "property_id": "venus-surry-hills", "property_name": "Central Sydney",
            "source_review_id": "SYNTH-venus-surry-hills-00257", "review_title": "Poor experience",
            "review_text": "Stayed one night before a flight. Very noisy at night with traffic and music from the street. Walking distance to restaurants and the harbour.",
            "rating": 2.5, "published_at": "2026-10-03T20:47:44Z", "language": "en",
            "sentiment_label": "negative", "sentiment_score": -0.624,
            "topic_labels": ["Noise", "Location"], "data_source": "synthetic",
            "collected_at": "2026-10-09T06:09:21.577042Z"}, …],
 "total": 6, "page": 1, "page_size": 2, "total_pages": 3,
 "filters": {"property_ids": ["venus-surry-hills"], "date_from": null, "date_to": null,
             "rating_min": null, "rating_max": null, "sentiment": "negative", "topic": "Noise",
             "q": null, "data_source": null, "sort": "newest"}}
```

### `GET /api/reviews/{id}`

Returns one review (same shape as list items) or `404 not_found`:

```json
{"error": {"code": "not_found", "message": "Review 999999 not found.", "details": null}}
```

### `GET /api/analytics/summary`

Params: `property_ids`, `as_of`. KPI cards for week-to-date vs. the same span of the previous
week.

`GET /api/analytics/summary?as_of=2026-10-09T12:00:00%2B11:00`

```json
{"data_sources": ["synthetic"], "contains_synthetic": true, "timezone": "Australia/Sydney",
 "as_of": "2026-10-09T01:00:00Z",
 "current_period": {"start": "2026-10-04T13:00:00Z", "end": "2026-10-09T01:00:00Z"},
 "previous_period": {"start": "2026-09-27T14:00:00Z", "end": "2026-10-02T02:00:00Z"},
 "current": {"reviews": 26, "avg_rating": 8.02, "rated_reviews": 23, "positive": 21,
             "neutral": 1, "negative": 4, "pct_negative": 15.4},
 "previous": {"reviews": 21, "avg_rating": 6.72, "rated_reviews": 20, "positive": 16,
              "neutral": 1, "negative": 4, "pct_negative": 19.0},
 "avg_rating_change": 1.3, "review_count_change": 5, "pct_negative_change": -3.6,
 "top_negative_topic": {"topic": "Facilities", "count": 2, "negative_reviews": 4,
                        "pct_of_negative": 50.0},
 "excluded_undated": 2}
```

### `GET /api/analytics/properties`

Params: `property_ids`, `as_of`, `weeks` (1–52, default 4). `window` stats cover the last
`weeks` calendar weeks (current partial week included); `current_week` / `previous_week` drive
the week-over-week change; `top_complaint` is the most frequent topic among negative reviews in
the window.

```json
{"…": "…", "window": {"start": "2026-09-13T14:00:00Z", "end": "2026-10-09T01:00:00Z"},
 "window_weeks": 4,
 "properties": [{"property_id": "venus-surry-hills", "name": "Central Sydney",
   "window": {"reviews": 27, "avg_rating": 6.38, "rated_reviews": 26, "positive": 19,
              "neutral": 4, "negative": 4, "pct_negative": 14.8},
   "current_week": {"reviews": 6, "avg_rating": 7.83, "…": "…"},
   "previous_week": {"reviews": 2, "avg_rating": 3.75, "…": "…"},
   "avg_rating_change": 4.08,
   "top_complaint": {"topic": "Noise", "count": 3, "negative_reviews": 4, "pct_of_negative": 75.0}}],
 "excluded_undated": 1}
```

### `GET /api/analytics/trends`

Params: `property_ids`, `as_of`, `weeks` (default 12). Weekly buckets keyed by the local Monday;
empty weeks have `reviews: 0` and `avg_rating: null`. The last bucket is the partial current week.

```json
{"…": "…", "weeks": 2, "current_week_partial": true,
 "overall": [{"week_start": "2026-09-28", "reviews": 5, "avg_rating": 4.6, "rated_reviews": 5,
              "positive": 3, "neutral": 0, "negative": 2},
             {"week_start": "2026-10-05", "reviews": 6, "avg_rating": 7.83, "rated_reviews": 6,
              "positive": 5, "neutral": 0, "negative": 1}],
 "by_property": [{"property_id": "venus-surry-hills", "name": "Central Sydney", "points": […]}]}
```

### `GET /api/analytics/topics`

Params: `property_ids`, `as_of`, `weeks` (default 4).

- `top_negative_topics`: topic counts among negative reviews; `pct_of_negative` uses
  `negative_reviews` as the denominator (a review can have several topics, so shares can sum to
  more than 100%).
- `cleanliness_share_of_negative.pct` = negative reviews mentioning Cleanliness ÷ all negative
  reviews × 100. It is `null` with `available: false` when there are no negative reviews.
- `rising_topics`: negative mentions in the last 14 days vs the 14 days before; listed when the
  recent count is higher and at least 2. This is descriptive, not a significance test.
- `examples`: up to 2 supporting reviews for each of the top 3 topics (most negative VADER score
  first).

```json
{"…": "…", "method": "approximate keyword-based topics; VADER text sentiment",
 "total_reviews": 27, "negative_reviews": 4,
 "top_negative_topics": [{"topic": "Noise", "count": 3, "pct_of_negative": 75.0}, …],
 "cleanliness_share_of_negative": {"negative_with_cleanliness": 1, "negative_reviews": 4,
                                   "pct": 25.0, "available": true},
 "worst_topic_by_property": [{"property_id": "venus-surry-hills", "name": "Central Sydney",
                              "topic": "Noise", "count": 3, "negative_reviews": 4,
                              "pct_of_negative": 75.0}],
 "rising_topics": [{"topic": "Noise", "recent_count": 3, "prior_count": 0, "change": 3,
                    "recent_pct_of_negative": 75.0, "prior_pct_of_negative": null}, …],
 "examples": [{"topic": "Noise", "reviews": [{"id": 234, "review_title": "Disappointing",
               "rating": 2.0, "sentiment_score": -0.7096, "data_source": "synthetic", "…": "…"}]}]}
```

### `GET /api/collection/runs`

Params: `property_ids`, `status`, `limit` (1–200, default 50). Newest first.

```json
{"items": [{"id": 8, "property_id": "venus-surry-hills", "adapter": "import",
            "started_at": "2026-10-09T06:09:32.674713Z", "finished_at": "2026-10-09T06:10:00.117861Z",
            "status": "success", "discovered_count": 68, "inserted_count": 0,
            "duplicate_count": 68, "error_count": 0, "error_summary": null}]}
```

### `GET /api/collection/health`

Per-property last successful run, latest run, review count, and recent error summaries, plus
whether live collection is supported.

```json
{"data_sources": ["synthetic"], "contains_synthetic": true, "adapter": "manual",
 "live_collection_supported": false,
 "live_collection_note": "Live collection is disabled: Booking.com's Terms of Service prohibit automated access. Export reviews and upload them via POST /api/import/reviews instead.",
 "properties": [{"property_id": "venus-surry-hills", "name": "Central Sydney",
                 "last_success_at": "2026-10-09T06:10:00.117861Z",
                 "latest_run": {"id": 8, "status": "success", "…": "…"},
                 "review_count": 67, "recent_errors": []}, …]}
```

### `POST /api/collection/run/{property_id}`

Live collection is not permitted (see [COLLECTION.md](COLLECTION.md)):

```json
{"error": {"code": "collection_unsupported",
           "message": "Live collection is disabled: Booking.com's Terms of Service prohibit automated access. Export reviews and upload them via POST /api/import/reviews instead.",
           "details": {"adapter": "manual"}}}
```

Status `501`. Unknown property → `404`.

### `POST /api/import/reviews`

`multipart/form-data` with a `file` field (`.csv` or `.json`, UTF-8, ≤ `IMPORT_MAX_BYTES`,
default 5 MB, ≤ `IMPORT_MAX_ROWS` rows).

Columns / keys:

| Field | Required | Notes |
| ----- | -------- | ----- |
| `property_id` | yes | One of the seeded property ids |
| `review_text` | yes | Whitespace is collapsed |
| `source_review_id` | no | Primary dedup key when present |
| `review_title` | no | |
| `rating` | no | 1–10 (or 1–`rating_scale_max`, converted to 1–10) |
| `rating_scale_max` | no | e.g. `5` for 5-star sources |
| `published_at` | no | ISO 8601 or common formats; naive = business timezone; day-first for `dd/mm/yyyy` |
| `language` | no | e.g. `en`, `de` |
| `source` | no | `import` (default) or `synthetic` |
| `is_synthetic` | no | `true` forces `source = synthetic` (as does a `SYNTH-` id prefix) |

JSON may be an array of objects or `{"reviews": [...]}`.

`curl -F "file=@backend/tests/fixtures/bad_rows.csv;type=text/csv" http://127.0.0.1:8000/api/import/reviews`

```json
{"ok": true, "filename": "bad_rows.csv", "file_type": "csv", "discovered": 8, "inserted": 1,
 "duplicates": 0, "invalid": 7,
 "errors": [{"row": 1, "field": "rating", "message": "rating 11 outside 1-10"},
            {"row": 2, "field": "rating", "message": "rating 0 outside 1-10"},
            {"row": 3, "field": "rating", "message": "rating is not a number: 'abc'"},
            {"row": 4, "field": "published_at", "message": "unrecognised date format: 'not a date'"},
            {"row": 5, "field": "published_at", "message": "date is in the future"},
            {"row": 6, "field": "property_id", "message": "unknown property 'unknown-hotel'"},
            {"row": 7, "field": "review_text", "message": "required"}],
 "errors_truncated": false,
 "runs": [{"property_id": "olympic-paddington", "run_id": 9, "status": "partial",
           "discovered": 7, "inserted": 1, "duplicates": 0, "invalid": 6}],
 "data_sources": ["imported"], "failure_message": null}
```

Row numbers are 1-based data rows (header excluded). Valid rows are inserted even when others
fail. Re-uploading the same file inserts nothing and reports every row as a duplicate.
