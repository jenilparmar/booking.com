"""Text sentiment baseline using VADER (local lexicon, no network).

Labels come from VADER's compound score in [-1, 1] with the thresholds recommended by its
authors: compound >= 0.05 -> positive, <= -0.05 -> negative, otherwise neutral. The compound value
is stored as ``sentiment_score``; it is a lexicon score, not a probability or confidence.

VADER is English-only. Reviews whose declared language is not English are labelled neutral with
a NULL score rather than guessed. The source star rating is never used here; it is stored
separately so the two can disagree.
"""

from dataclasses import dataclass
from typing import Protocol

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

POSITIVE_THRESHOLD = 0.05
NEGATIVE_THRESHOLD = -0.05


@dataclass(frozen=True)
class SentimentResult:
    label: str
    score: float | None


class SentimentAnalyzer(Protocol):
    name: str

    def analyze(self, text: str, language: str | None = None) -> SentimentResult: ...


def label_for(compound: float) -> str:
    if compound >= POSITIVE_THRESHOLD:
        return "positive"
    if compound <= NEGATIVE_THRESHOLD:
        return "negative"
    return "neutral"


class VaderSentimentAnalyzer:
    name = "vader-3.3.2"

    def __init__(self) -> None:
        self._vader = SentimentIntensityAnalyzer()

    def analyze(self, text: str, language: str | None = None) -> SentimentResult:
        if not text or not text.strip():
            return SentimentResult("neutral", None)
        if language and not language.lower().startswith("en"):
            return SentimentResult("neutral", None)
        compound = float(self._vader.polarity_scores(text)["compound"])
        return SentimentResult(label_for(compound), round(compound, 4))


default_analyzer = VaderSentimentAnalyzer()
