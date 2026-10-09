# Review Insights

Weekly guest-review analytics for four Sydney properties: ratings, review volume, sentiment,
complaint topics and data-feed health.

- **Backend:** FastAPI + SQLAlchemy 2 + Alembic (Python 3.12, managed with `uv`)
- **Database:** Neon serverless Postgres
- **Frontend:** Next.js 16 (App Router) + Tailwind + Recharts + SWR

> The bundled dataset in `data/` is **synthetic** and is labelled as such everywhere in the app.
> Booking.com's Terms prohibit automated access, so reviews are loaded by **file import**, not
> scraping. See [docs/COLLECTION.md](docs/COLLECTION.md).

![Overview](docs/screenshots/overview.png)

---

## Prerequisites

| Tool | Version | Install |
| --- | --- | --- |
| Python | 3.12+ | <https://www.python.org/downloads/> |
| uv | latest | `pip install uv` or <https://docs.astral.sh/uv/> |
| Node.js | 22+ (with npm) | <https://nodejs.org/> |
| Neon account | free tier is enough | <https://neon.tech> |

---

## 1. Create the Neon databases

1. Create a project at <https://console.neon.tech>.
2. Click **Connect** and copy two connection strings for the default database (`neondb`):
   - **Pooled**: the host contains `-pooler`. This is used by the running app.
   - **Direct**: the same host without `-pooler`. This is used for migrations.
3. Create a second database for tests (for example `booking_test`) under **Databases → New
   database**, or create a Neon branch. Copy its connection string.

Keep `?sslmode=require` on every URL.

## 2. Configure environment

```powershell
Copy-Item .env.example .env      # macOS/Linux: cp .env.example .env
```

Edit `.env` and fill in:

```dotenv
DATABASE_URL=postgresql://USER:PASSWORD@ep-xxxx-pooler.REGION.aws.neon.tech/neondb?sslmode=require
DIRECT_DATABASE_URL=postgresql://USER:PASSWORD@ep-xxxx.REGION.aws.neon.tech/neondb?sslmode=require
TEST_DATABASE_URL=postgresql://USER:PASSWORD@ep-xxxx-pooler.REGION.aws.neon.tech/booking_test?sslmode=require
```

The other settings (timezone, CORS, import limits) have working defaults. `.env` is gitignored,
so **never commit it**. The test suite refuses to run if `TEST_DATABASE_URL` points at the main
database.

## 3. Install, migrate and load sample data

Windows (PowerShell):

```powershell
./scripts/tasks.ps1 setup           # uv sync + npm install + migrations + seed 4 properties
./scripts/tasks.ps1 import-sample   # import data/sample_reviews.csv (labelled synthetic)
```

macOS / Linux:

```bash
make setup
make import-sample
```

If PowerShell blocks the script, run it with
`powershell -ExecutionPolicy Bypass -File .\scripts\tasks.ps1 setup`.

## 4. Start the app

Use two terminals:

```powershell
./scripts/tasks.ps1 backend     # terminal 1 → API on http://127.0.0.1:8000
./scripts/tasks.ps1 frontend    # terminal 2 → UI  on http://localhost:3000
```

On macOS/Linux, use `make backend` and `make frontend`.

| URL | What |
| --- | --- |
| <http://localhost:3000> | Dashboard |
| <http://127.0.0.1:8000/docs> | Interactive API docs (OpenAPI) |
| <http://127.0.0.1:8000/api/health> | Health check |

The frontend proxies `/api/*` to the backend (`BACKEND_URL`, default `http://127.0.0.1:8000`), so
no CORS setup is needed in development.

---

## Importing your own reviews

You can import from the UI: go to **Data & import**, choose a `.csv` or `.json` file (max 5 MB),
and click **Import reviews**.

Or from the CLI:

```powershell
cd backend
uv run python -m app.cli import path\to\reviews.csv
```

Required columns are `property_id` and `review_text`. Optional columns: `source_review_id`,
`review_title`, `rating`, `rating_scale_max`, `published_at`, `language`, `source`.

Valid property ids are `olympic-paddington`, `venus-potts-point-sydney`, `venus-surry-hills` and
`chateau-de-venus`.

Re-importing the same file is safe, because duplicates are skipped. The response reports
inserted, duplicate and invalid counts.

## Tests and checks

```powershell
./scripts/tasks.ps1 test     # pytest (uses TEST_DATABASE_URL) + vitest
./scripts/tasks.ps1 lint     # ruff, ruff format --check, mypy, eslint, tsc
./scripts/tasks.ps1 build    # next build
./scripts/tasks.ps1 check    # lint + test + build
```

## Other commands

```powershell
./scripts/tasks.ps1 migrate                       # apply migrations only
./scripts/tasks.ps1 generate-sample               # regenerate the synthetic dataset
cd backend; uv run python -m app.cli reclassify   # re-run topic + sentiment on all reviews
```

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Dashboard shows "Could not reach the API" | Start the backend (`tasks.ps1 backend`) and check it on port 8000 |
| First request is slow or times out once | Neon was waking from idle. Retry; the engine reconnects automatically |
| `TEST_DATABASE_URL is not set` or `...points at the main database; refusing to run` | Set `TEST_DATABASE_URL` to a separate database or Neon branch |
| Port 3000 or 8000 already in use | Stop the other process, or run `uv run uvicorn app.main:app --port 8001` and set `BACKEND_URL` in `frontend/.env.local` |

## Documentation

- [docs/WALKTHROUGH.md](docs/WALKTHROUGH.md): full project walkthrough (start here)
- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md): layers, decisions, assumptions
- [docs/COLLECTION.md](docs/COLLECTION.md): robots.txt/ToS findings and the import path
- [docs/CLASSIFICATION.md](docs/CLASSIFICATION.md): topic keywords and sentiment thresholds
- [docs/API.md](docs/API.md): endpoints with example requests and responses
- [data/README.md](data/README.md): about the synthetic sample data
