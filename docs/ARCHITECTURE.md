# Architecture

Review Insights is a **modular monolith**: one FastAPI process, one Postgres database (Neon), and
one Next.js frontend. There are no microservices, message brokers, Redis, or paid APIs.

```
booking.com/
├── backend/           FastAPI app, SQLAlchemy 2.x models, Alembic migrations, pytest suite
│   ├── app/
│   │   ├── api/         HTTP layer: routers, request/response schemas, error envelope
│   │   ├── services/    Domain logic: normalization, import, collection, classification, analytics
│   │   ├── models.py    Persistence layer (SQLAlchemy ORM)
│   │   ├── seed.py      Stable property seed
│   │   └── cli.py       CLI entry points (migrate, import, reclassify)
│   ├── alembic/       Migrations (reproducible from an empty database)
│   └── tests/         Unit + API tests; fixtures live in tests/fixtures
├── frontend/          Next.js (App Router) + TypeScript + Tailwind + Recharts, Vitest/RTL
├── data/              Synthetic sample dataset + deterministic generator
├── docs/              Architecture, collection policy, classification, API reference, screenshots
└── scripts/           PowerShell task runner (Makefile mirrors it for POSIX shells)
```

## Layers

| Layer       | Responsibility                                                                    |
| ----------- | --------------------------------------------------------------------------------- |
| Collection  | `CollectorAdapter` interface; CSV/JSON importer is the supported path.            |
| Processing  | Normalize text/dates/ratings, content hash, topic classification, sentiment.      |
| Persistence | SQLAlchemy models, DB-level constraints and dedup, Alembic migrations.            |
| Analytics   | SQL aggregations: weekly KPIs, property comparison, trends, topic insights.       |
| API         | FastAPI routers, Pydantic schemas, consistent error envelope, OpenAPI at `/docs`. |
| UI          | Next.js pages calling the API through a typed client (no duplicated backend logic). |

Dependencies point inward: API → services → models. Services never import from the API layer, so
the CLI and tests call them directly.

## Key decisions

- **Neon Postgres.** The API uses the **pooled** connection string (`DATABASE_URL`, pgbouncer in
  transaction mode). Because of that: psycopg auto-prepared statements are disabled on pooled
  hosts, no session-level state (`SET`, advisory locks, temp tables) is relied on, the SQLAlchemy
  pool is small (`DB_POOL_SIZE=5`), connections are pre-pinged and recycled every 4 minutes, and
  the initial connect is retried with backoff to absorb compute cold starts. Alembic runs over the
  **direct** connection string (`DIRECT_DATABASE_URL`).
- **Tests use a separate database** (`TEST_DATABASE_URL`). The suite refuses to run if it resolves
  to the main database. Each session migrates down to empty and back up to head (proving
  migrations are reproducible); each test runs inside a transaction that is rolled back.
- **Dedup in the database.** Partial unique index on
  `(property_id, source_review_id) WHERE source_review_id IS NOT NULL` plus unique
  `(property_id, content_hash)`. Imports use `INSERT ... ON CONFLICT DO NOTHING RETURNING id`, so
  repeated or concurrent imports are idempotent.
- **Postgres types.** `timestamptz` for every timestamp (application only accepts tz-aware
  datetimes and returns UTC); `topic_labels` is `JSONB` with a GIN index for `@>` topic filters.
- **Aggregations in SQL.** Analytics never loads the full review table into Python.
- **Rule-based NLP.** Topics use documented keyword/regex rules; sentiment uses VADER (local, no
  network). Both are approximations and are labelled as such in the UI
  ([CLASSIFICATION.md](CLASSIFICATION.md)).
- **Provenance is explicit.** `Review.source` is `live`, `import`, or `synthetic`; API responses
  include a `data_source` indicator and the UI shows a badge whenever synthetic data is visible.
- **No reviewer PII.** Reviewer names, countries, and avatars are not stored.
- **Frontend talks to FastAPI only.** `NEXT_PUBLIC_API_BASE_URL` selects the API; when empty, the
  browser calls same-origin `/api/*` and `next.config.ts` rewrites it to `BACKEND_URL` (dev
  convenience to avoid CORS). No Next.js route handlers re-implement backend logic.

## Assumptions

- **Business timezone:** `Australia/Sydney` (`BUSINESS_TIMEZONE`). A week starts Monday 00:00
  local time; DST is handled by `zoneinfo`. Timestamps are stored in UTC.
- **"This week"** is Monday 00:00 local → now. **"Previous week"** is the same elapsed span one
  week earlier (e.g. Mon 00:00 → Wed 14:00 vs the prior Mon 00:00 → Wed 14:00), so partial weeks
  are compared fairly.
- **Rating scale:** Booking.com scores are 1–10 and are stored on that scale. Imports may declare
  another scale (e.g. 1–5) and are normalized linearly to 1–10.
- **Missing values are NULL, never 0.** Missing ratings are excluded from averages; reviews with no
  `published_at` are excluded from time-based analytics and the exclusion count is reported.
- **Properties** are fixed and seeded with stable IDs (`backend/app/seed.py`). The display names
  and IDs come from the task brief; the `source_url` values are derived from those IDs.
- **Data provenance:** Booking.com's Terms prohibit automated access
  ([COLLECTION.md](COLLECTION.md)), so live collection is disabled. Data enters via manual export
  + import. The bundled sample dataset is synthetic and labelled on every record.
