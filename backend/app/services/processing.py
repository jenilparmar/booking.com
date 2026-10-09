from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Review
from app.services.classify import TopicClassifier, default_classifier
from app.services.sentiment import SentimentAnalyzer, default_analyzer


@dataclass(frozen=True)
class Enrichment:
    topic_labels: list[str]
    sentiment_label: str
    sentiment_score: float | None


def enrich(
    text: str,
    title: str | None = None,
    language: str | None = None,
    classifier: TopicClassifier = default_classifier,
    analyzer: SentimentAnalyzer = default_analyzer,
) -> Enrichment:
    full = f"{title}. {text}" if title else text
    s = analyzer.analyze(full, language)
    return Enrichment(classifier.classify(full), s.label, s.score)


def reclassify_all(db: Session, batch_size: int = 500) -> int:
    """Recompute topics and sentiment for every review (e.g. after keyword list changes)."""
    count = 0
    last_id = 0
    while True:
        batch = list(
            db.scalars(
                select(Review).where(Review.id > last_id).order_by(Review.id).limit(batch_size)
            )
        )
        if not batch:
            break
        for r in batch:
            e = enrich(r.review_text, r.review_title, r.language)
            r.topic_labels = e.topic_labels
            r.sentiment_label = e.sentiment_label
            r.sentiment_score = e.sentiment_score
        db.commit()
        count += len(batch)
        last_id = batch[-1].id
    return count
