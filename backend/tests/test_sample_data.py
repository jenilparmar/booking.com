"""Checks the committed synthetic sample dataset and its generator (no DB needed)."""

import csv
import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import ModuleType
from zoneinfo import ZoneInfo

from app.seed import PROPERTY_IDS

DATA_DIR = Path(__file__).resolve().parents[2] / "data"
TZ = ZoneInfo("Australia/Sydney")


def _load_generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("generate_sample", DATA_DIR / "generate_sample.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _csv_rows() -> list[dict[str, str]]:
    with (DATA_DIR / "sample_reviews.csv").open(encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_every_record_is_labelled_synthetic() -> None:
    rows = _csv_rows()
    assert rows
    for r in rows:
        assert r["source"] == "synthetic"
        assert r["is_synthetic"] == "true"
        assert r["source_review_id"].startswith("SYNTH-")
    payload = json.loads((DATA_DIR / "sample_reviews.json").read_text(encoding="utf-8"))
    assert "SYNTHETIC" in payload["notice"]
    assert all(r["source"] == "synthetic" and r["is_synthetic"] for r in payload["reviews"])
    assert len(payload["reviews"]) == len(rows)


def test_dataset_coverage() -> None:
    rows = _csv_rows()
    assert {r["property_id"] for r in rows} == set(PROPERTY_IDS)
    assert any(r["rating"] == "" for r in rows), "expected some missing ratings"
    assert any(r["published_at"] == "" for r in rows), "expected some missing dates"
    assert any(r["review_title"] == "" for r in rows), "expected some missing titles"
    ids = [r["source_review_id"] for r in rows]
    assert len(ids) > len(set(ids)), "expected a few duplicate records"
    ratings = {float(r["rating"]) for r in rows if r["rating"]}
    assert min(ratings) < 5 and max(ratings) >= 9


def test_generator_is_deterministic_and_spans_current_and_previous_week() -> None:
    gen = _load_generator()
    anchor = datetime(2026, 10, 9, 12, 0, tzinfo=TZ)
    a = gen.generate(42, anchor, 8)
    b = gen.generate(42, anchor, 8)
    assert [r.__dict__ for r in a] == [r.__dict__ for r in b]

    this_monday = gen.monday_start(anchor)
    dates = [datetime.fromisoformat(r.published_at) for r in a if r.published_at]
    assert any(this_monday <= d <= anchor for d in dates)
    assert any(this_monday - timedelta(weeks=1) <= d < this_monday for d in dates)
    assert max(dates) <= anchor
    weeks = {gen.monday_start(d) for d in dates}
    assert len(weeks) == 8


def test_generator_covers_all_topics() -> None:
    gen = _load_generator()
    rows = gen.generate(42, datetime(2026, 10, 9, 12, 0, tzinfo=TZ), 8)
    text = " ".join(r.review_text for r in rows)
    for topic, banks in gen.PHRASES.items():
        assert any(p in text for p in banks["neg"]), f"no negative phrase for {topic}"
        assert any(p in text for p in banks["pos"]), f"no positive phrase for {topic}"
