import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Review
from app.services.classify import TOPIC_KEYWORDS, TOPICS, RuleBasedTopicClassifier
from app.services.processing import enrich, reclassify_all
from app.services.sentiment import (
    NEGATIVE_THRESHOLD,
    POSITIVE_THRESHOLD,
    VaderSentimentAnalyzer,
    label_for,
)

clf = RuleBasedTopicClassifier()
vader = VaderSentimentAnalyzer()


@pytest.mark.parametrize(
    ("text", "topic"),
    [
        ("The bathroom was dirty and there was hair in the shower.", "Cleanliness"),
        ("Spotless room.", "Cleanliness"),
        ("Check-in took 40 minutes.", "Check-in experience"),
        ("Our key card stopped working.", "Check-in experience"),
        ("The receptionist was rude.", "Staff/receptionist behaviour"),
        ("Staff were lovely.", "Staff/receptionist behaviour"),
        ("Very noisy at night.", "Noise"),
        ("Thin walls, we could hear everything.", "Noise"),
        ("The wifi kept dropping.", "Facilities"),
        ("Air conditioning did not work.", "Facilities"),
        ("Great location near the station.", "Location"),
        ("Walking distance to the harbour.", "Location"),
        ("Peeling paint and a worn out mattress.", "Room condition"),
        ("The room was tiny.", "Room condition"),
        ("Overpriced for what you get.", "Value for money"),
        ("Good value.", "Value for money"),
    ],
)
def test_each_topic_detected(text: str, topic: str) -> None:
    assert topic in clf.classify(text)


def test_every_topic_has_keywords_and_is_covered() -> None:
    assert set(TOPIC_KEYWORDS) == set(TOPICS)
    assert len(TOPICS) == 8


def test_multi_label() -> None:
    topics = clf.classify("Dirty room, rude staff, and far too noisy. Not worth the money.")
    assert topics == [
        "Cleanliness",
        "Staff/receptionist behaviour",
        "Noise",
        "Value for money",
    ]


@pytest.mark.parametrize(
    "text",
    [
        "Bought a cleanser at the chemist.",  # 'cleanser' is not 'clean'
        "Lifted my mood.",  # 'lifted' is not 'lift'
        "We sat poolside elsewhere.",  # 'poolside' is not 'pool'
        "Staffordshire terrier photos.",  # 'Staffordshire' is not 'staff'
        "A priceless view of nothing.",  # 'priceless' is not 'price'
    ],
)
def test_word_boundaries_prevent_substring_matches(text: str) -> None:
    assert clf.classify(text) == []


def test_empty_text() -> None:
    assert clf.classify("") == []
    assert clf.classify("   ") == []
    assert vader.analyze("").label == "neutral"
    assert vader.analyze("").score is None


def test_non_english_gets_no_english_topics_and_neutral_sentiment() -> None:
    e = enrich("Zimmer war schmutzig und sehr laut in der Nacht.", language="de")
    assert e.topic_labels == []
    assert e.sentiment_label == "neutral" and e.sentiment_score is None


def test_negation_keeps_topic_but_flips_sentiment() -> None:
    neg = enrich("The room was not clean.")
    pos = enrich("The room was clean.")
    assert "Cleanliness" in neg.topic_labels and "Cleanliness" in pos.topic_labels
    assert neg.sentiment_label == "negative"
    assert pos.sentiment_label == "positive"
    quiet = enrich("It was not noisy at all, no problems.")
    assert "Noise" in quiet.topic_labels
    assert quiet.sentiment_label != "negative"


def test_title_contributes_to_topics() -> None:
    e = enrich("Would not return.", title="Filthy bathroom")
    assert "Cleanliness" in e.topic_labels


def test_sentiment_thresholds() -> None:
    assert label_for(POSITIVE_THRESHOLD) == "positive"
    assert label_for(NEGATIVE_THRESHOLD) == "negative"
    assert label_for(0.0) == "neutral"
    assert label_for(0.049) == "neutral"


def test_sentiment_is_independent_of_rating(db: Session) -> None:
    """A glowing 3/10 and a scathing 9/10 keep their own rating and text sentiment."""
    import json

    from app.services.importer import import_file

    rows = [
        {
            "property_id": "olympic-paddington",
            "review_text": "Wonderful, amazing, perfect stay!",
            "rating": 3,
        },
        {
            "property_id": "olympic-paddington",
            "review_text": "Horrible, dirty and rude. Awful.",
            "rating": 9,
        },
    ]
    import_file(db, "x.json", json.dumps(rows).encode())
    by_rating = {r.rating: r for r in db.scalars(select(Review))}
    assert by_rating[3.0].sentiment_label == "positive"
    assert by_rating[9.0].sentiment_label == "negative"


def test_reclassify_all_updates_rows(db: Session) -> None:
    import json

    from app.services.importer import import_file

    import_file(
        db,
        "x.json",
        json.dumps([{"property_id": "olympic-paddington", "review_text": "Very noisy."}]).encode(),
    )
    r = db.scalars(select(Review)).one()
    r.topic_labels = []
    r.sentiment_label = "positive"
    db.commit()
    assert reclassify_all(db) == 1
    db.refresh(r)
    assert r.topic_labels == ["Noise"]
    assert r.sentiment_label == "negative"
