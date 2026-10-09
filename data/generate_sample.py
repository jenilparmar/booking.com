"""Deterministic generator for the SYNTHETIC sample review dataset.

Every record produced here is fabricated for demo/testing purposes. None of it is a real
Booking.com review. Records are labelled three ways:
  * source = "synthetic"
  * is_synthetic = true
  * source_review_id starts with "SYNTH-"

Usage (from repo root or backend/):
  python data/generate_sample.py                     # anchor = now (Australia/Sydney)
  python data/generate_sample.py --anchor 2026-10-09T12:00:00+11:00 --weeks 8 --seed 42

Output for a given (seed, anchor, weeks) is byte-for-byte identical. Re-run with a newer anchor
to keep "this week" and "last week" populated.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("Australia/Sydney")
OUT_DIR = Path(__file__).resolve().parent

PROPERTIES = [
    "olympic-paddington",
    "venus-potts-point-sydney",
    "venus-surry-hills",
    "chateau-de-venus",
]

# Phrase banks per topic. Wording is generic and invented for this dataset.
PHRASES: dict[str, dict[str, list[str]]] = {
    "Cleanliness": {
        "pos": [
            "The room was spotless and the bathroom was very clean.",
            "Housekeeping kept everything clean and tidy.",
            "Fresh sheets and a really clean shower.",
        ],
        "neg": [
            "The bathroom was dirty and there was hair in the shower.",
            "Found dust under the bed and stained towels.",
            "The carpet was filthy and the room smelled of mould.",
        ],
    },
    "Check-in experience": {
        "pos": [
            "Check-in was quick and easy.",
            "Smooth check in, keys were ready when we arrived.",
            "Early check-in was arranged without fuss.",
        ],
        "neg": [
            "Check-in took over 40 minutes because of a long queue.",
            "Our booking could not be found at check in.",
            "Late check-in instructions were confusing and the key code did not work.",
        ],
    },
    "Staff/receptionist behaviour": {
        "pos": [
            "The receptionist was friendly and helpful.",
            "Staff went out of their way to help us.",
            "Lovely front desk team, very welcoming.",
        ],
        "neg": [
            "The receptionist was rude and dismissive.",
            "Staff were unhelpful when we reported a problem.",
            "The night manager was unfriendly and ignored our request.",
        ],
    },
    "Noise": {
        "pos": [
            "The room was quiet and we slept well.",
            "Very peaceful at night despite the central location.",
        ],
        "neg": [
            "Very noisy at night with traffic and music from the street.",
            "Thin walls, we could hear the neighbours all night.",
            "Loud construction noise started at 7am.",
        ],
    },
    "Facilities": {
        "pos": [
            "The kitchen and laundry facilities were handy.",
            "Good wifi and a nice rooftop area.",
            "The gym and lift worked well.",
        ],
        "neg": [
            "The wifi kept dropping and the lift was out of order.",
            "No parking available and the laundry machines were broken.",
            "The air conditioning did not work.",
        ],
    },
    "Location": {
        "pos": [
            "Great location, close to the train station and cafes.",
            "Walking distance to restaurants and the harbour.",
            "Convenient location near shops and public transport.",
        ],
        "neg": [
            "The area felt unsafe at night.",
            "Location was further from the station than expected.",
        ],
    },
    "Room condition": {
        "pos": [
            "The room was modern and well maintained.",
            "Comfortable bed and a recently renovated room.",
        ],
        "neg": [
            "The room was tired and outdated, with a broken lamp.",
            "Peeling paint, a leaking tap and a worn out mattress.",
            "The room was tiny and the furniture was damaged.",
        ],
    },
    "Value for money": {
        "pos": [
            "Good value for money for Sydney.",
            "Reasonable price for what you get.",
        ],
        "neg": [
            "Overpriced for what you get.",
            "Not worth the money, far too expensive.",
        ],
    },
}

NEUTRAL_FILLERS = [
    "We stayed two nights for a work trip.",
    "Stayed one night before a flight.",
    "Booked for a weekend in the city.",
    "Came for a concert nearby.",
]

TITLES = {
    "positive": ["Great stay", "Would stay again", "Lovely hotel", "Very comfortable"],
    "neutral": ["Okay stay", "Average", "Mixed experience", "Fine for a night"],
    "negative": ["Disappointing", "Would not return", "Not as expected", "Poor experience"],
}

NON_ENGLISH = [
    ("de", "Zimmer war sauber, aber sehr laut in der Nacht."),
    ("fr", "Personnel très aimable, chambre un peu petite."),
    ("es", "Buena ubicación pero el baño estaba sucio."),
]

# Per-property weights for which topics show up negatively. Gives each property a distinct
# "problem profile" so comparisons are interesting. Purely invented.
NEG_PROFILE = {
    "olympic-paddington": {"Room condition": 3, "Facilities": 2, "Noise": 1},
    "venus-potts-point-sydney": {"Cleanliness": 3, "Staff/receptionist behaviour": 2},
    "venus-surry-hills": {"Noise": 3, "Check-in experience": 2, "Cleanliness": 1},
    "chateau-de-venus": {"Value for money": 2, "Facilities": 2, "Location": 1},
}
NEG_BASE_RATE = {
    "olympic-paddington": 0.30,
    "venus-potts-point-sydney": 0.35,
    "venus-surry-hills": 0.30,
    "chateau-de-venus": 0.22,
}


@dataclass
class Row:
    source_review_id: str
    property_id: str
    review_title: str | None
    review_text: str
    rating: float | None
    published_at: str | None
    language: str
    source: str = "synthetic"
    is_synthetic: bool = True


def monday_start(dt: datetime) -> datetime:
    local = dt.astimezone(TZ)
    d = (local - timedelta(days=local.weekday())).date()
    return datetime(d.year, d.month, d.day, tzinfo=TZ)


def pick_topics(rng: random.Random, prop: str, negative: bool) -> list[str]:
    topics = list(PHRASES)
    n = rng.choice([1, 1, 2, 2, 3])
    if negative:
        weights = [NEG_PROFILE[prop].get(t, 0) + 1 for t in topics]
    else:
        weights = [1] * len(topics)
    chosen: list[str] = []
    while len(chosen) < n:
        t = rng.choices(topics, weights=weights)[0]
        if t not in chosen:
            chosen.append(t)
    return chosen


def make_row(
    rng: random.Random, idx: int, prop: str, published: datetime, week_index: int, weeks: int
) -> Row:
    neg_rate = NEG_BASE_RATE[prop]
    # Rising-problem story: Surry Hills noise complaints grow in the last two weeks.
    if prop == "venus-surry-hills" and week_index >= weeks - 2:
        neg_rate += 0.15
    roll = rng.random()
    sentiment = "negative" if roll < neg_rate else ("neutral" if roll < neg_rate + 0.15 else "positive")

    topics = pick_topics(rng, prop, sentiment == "negative")
    if prop == "venus-surry-hills" and sentiment == "negative" and week_index >= weeks - 2:
        if "Noise" not in topics:
            topics[0] = "Noise"

    parts: list[str] = []
    if rng.random() < 0.4:
        parts.append(rng.choice(NEUTRAL_FILLERS))
    for i, t in enumerate(topics):
        if sentiment == "positive":
            pol = "pos"
        elif sentiment == "negative":
            pol = "neg" if i == 0 or rng.random() < 0.6 else "pos"
        else:
            pol = "pos" if i % 2 == 0 else "neg"
        parts.append(rng.choice(PHRASES[t][pol]))
    text = " ".join(parts)
    language = "en"
    if rng.random() < 0.03:
        language, text = rng.choice(NON_ENGLISH)

    base = {"positive": (8.0, 10.0), "neutral": (5.5, 7.5), "negative": (2.0, 5.5)}[sentiment]
    rating: float | None = round(rng.uniform(*base) * 2) / 2
    # A few rating/text disagreements (e.g. guest complains but still scores 9).
    if rng.random() < 0.04:
        rating = 9.0 if sentiment == "negative" else 4.0
    if rng.random() < 0.06:
        rating = None

    title: str | None = rng.choice(TITLES[sentiment])
    if rng.random() < 0.25:
        title = None

    published_str: str | None = published.isoformat(timespec="seconds")
    if rng.random() < 0.03:
        published_str = None

    return Row(
        source_review_id=f"SYNTH-{prop}-{idx:05d}",
        property_id=prop,
        review_title=title,
        review_text=text,
        rating=rating,
        published_at=published_str,
        language=language,
    )


def generate(seed: int, anchor: datetime, weeks: int) -> list[Row]:
    rng = random.Random(seed)
    start = monday_start(anchor) - timedelta(weeks=weeks - 1)
    rows: list[Row] = []
    counter = 0
    for w in range(weeks):
        week_start = start + timedelta(weeks=w)
        week_end = min(week_start + timedelta(days=7), anchor)
        span = (week_end - week_start).total_seconds()
        if span <= 0:
            continue
        for prop in PROPERTIES:
            n = rng.randint(6, 12)
            if week_end < week_start + timedelta(days=7):
                n = max(2, round(n * span / (7 * 86400)))
            for _ in range(n):
                counter += 1
                offset = timedelta(seconds=rng.uniform(0, span))
                published = (week_start + offset).astimezone(TZ).replace(microsecond=0)
                rows.append(make_row(rng, counter, prop, published, w, weeks))

    rows.sort(key=lambda r: (r.published_at or "", r.source_review_id))
    # A few exact duplicates to exercise dedup on import.
    dupes = [rows[i] for i in rng.sample(range(len(rows)), k=min(5, len(rows)))]
    rows.extend(Row(**asdict(d)) for d in dupes)
    return rows


def write(rows: list[Row], anchor: datetime, seed: int, weeks: int) -> None:
    fields = list(Row.__dataclass_fields__)
    csv_path = OUT_DIR / "sample_reviews.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            d = asdict(r)
            d["is_synthetic"] = "true"
            w.writerow({k: ("" if v is None else v) for k, v in d.items()})

    json_path = OUT_DIR / "sample_reviews.json"
    payload = {
        "notice": (
            "SYNTHETIC DATA. Generated by data/generate_sample.py for demo and testing. "
            "These are not real Booking.com reviews."
        ),
        "generator": {"seed": seed, "anchor": anchor.isoformat(), "weeks": weeks},
        "reviews": [asdict(r) for r in rows],
    }
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {len(rows)} synthetic rows to {csv_path.name} and {json_path.name}")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--weeks", type=int, default=8)
    p.add_argument("--anchor", help="ISO datetime with offset; default now in Australia/Sydney")
    a = p.parse_args()
    anchor = (
        datetime.fromisoformat(a.anchor).astimezone(TZ)
        if a.anchor
        else datetime.now(TZ).replace(microsecond=0)
    )
    rows = generate(a.seed, anchor, a.weeks)
    write(rows, anchor, a.seed, a.weeks)


if __name__ == "__main__":
    main()
