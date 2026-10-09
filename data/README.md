# Sample data — SYNTHETIC

`sample_reviews.csv` and `sample_reviews.json` are **fabricated** reviews produced by
`generate_sample.py` for demos and tests. They are **not** real Booking.com reviews and must not be
presented as such.

Every record is labelled three ways: `source = synthetic`, `is_synthetic = true`, and a
`source_review_id` starting with `SYNTH-`. When imported, rows keep `source = synthetic` and the
dashboard shows a "Synthetic data" badge.

The dataset covers all four properties over 8 weeks (including the current and previous week
relative to the generator anchor), all eight topics, mixed ratings and sentiment, some missing
ratings, dates, and titles, a few non-English reviews, a few rating/text disagreements, and five
exact duplicate rows to exercise dedup.

Regenerate (deterministic for a given seed + anchor):

```powershell
cd backend
uv run python ../data/generate_sample.py                       # anchor = now in Australia/Sydney
uv run python ../data/generate_sample.py --anchor 2026-10-09T12:00:00+11:00 --seed 42 --weeks 8
```

The committed files were generated with `--anchor 2026-10-09T12:00:00+11:00 --seed 42 --weeks 8`.
Regenerate with a newer anchor if "this week" on the dashboard looks empty.

Test fixtures used by the backend test suite live separately in `backend/tests/fixtures/`.
