# Data collection: permissions, limitations, failure handling

## Findings (checked 2026-10-09)

### robots.txt — `https://www.booking.com/robots.txt`

- The `User-agent: *` group disallows a list of paths including `/hotelfeaturedreviews/`,
  `/sitembk-reviews-https-index.xml`, `/fragment*`, `/asapi/*`, `/book.html` and others.
- Individual hotel and review pages are **not** listed as disallowed for generic crawlers.
- robots.txt is a crawler-courtesy convention; it does not grant permission and does not override
  the site's Terms.

### Terms of Service — `https://www.booking.com/content/terms.en-gb.html`, section A15

> Whether or not you have a commercial purpose, you're not allowed to access, monitor, copy,
> scrape/crawl, download, reproduce or otherwise use anything on our Platform using any robot,
> spider, scraper, other automated means, or automated assistants (...) for any purpose without the
> prior, express written permission of Booking.com.

The Terms also state that Booking.com monitors and blocks automated systems.

## Decision

**Automated collection from Booking.com is prohibited, so it is not implemented.**

- No scraper, headless browser, or HTTP client targets Booking.com.
- No CAPTCHA solving, proxy rotation, fingerprint spoofing, or other anti-bot bypass exists in
  this codebase and none should be added.
- The supported ingestion path is the **importer**: a property owner exports or copies their own
  reviews (e.g. from the Booking.com Extranet/Partner Hub, which they are entitled to access) into
  CSV or JSON and uploads it via the UI or CLI.
- `POST /api/collection/run/{property_id}` returns `501` with error code
  `collection_unsupported`, explaining that live collection is disabled.
- If written permission or an official API/partner feed becomes available, implement a new
  `CollectorAdapter` (see `backend/app/services/collection.py`) and enable it via
  `COLLECTOR_ADAPTER`. The run logging, retry, and dedup machinery already exists.

## Import format

See [API.md](API.md#post-apiimportreviews) for columns. Minimum: `property_id`, `review_text`.
Optional: `source_review_id`, `review_title`, `rating`, `published_at`, `language`, `source`.

## Failure handling

- Every import or collection attempt creates a `CollectionRun` row per property with
  `started_at`, `finished_at`, `status`, and discovered / inserted / duplicate / error counts.
- A run that finds nothing new is `success` with `inserted_count = 0` — distinct from `failed`.
- Invalid rows are reported individually (row number + reason); valid rows are still inserted.
- Failed runs never delete or modify existing reviews; inserts happen in a single transaction.
- `error_summary` contains short human-readable reasons only — no stack traces or secrets.
- Adapters (if any are added) use bounded retries with exponential backoff + jitter, a request
  timeout, and a rate limit, all configured through environment variables.

## Limitations

- Data freshness depends on how often someone exports and imports reviews.
- Without an official feed, `source_review_id` may be missing; dedup then falls back to the
  content hash (see [CLASSIFICATION.md](CLASSIFICATION.md#content-hash)).
