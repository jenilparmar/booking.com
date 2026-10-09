"""Rule-based topic classification. Keyword lists are documented in docs/CLASSIFICATION.md.

Topics are *approximate*: a review is tagged with a topic when it mentions it, regardless of
whether the mention is positive or negative ("not clean" and "spotless" are both Cleanliness).
Polarity comes from the separate sentiment step.
"""

import re
from typing import Protocol

TOPICS: tuple[str, ...] = (
    "Cleanliness",
    "Check-in experience",
    "Staff/receptionist behaviour",
    "Noise",
    "Facilities",
    "Location",
    "Room condition",
    "Value for money",
)

# Regex fragments, matched case-insensitively with word boundaries on both sides.
TOPIC_KEYWORDS: dict[str, list[str]] = {
    "Cleanliness": [
        r"clean(?:ed|er|est|ing|liness|ly)?",
        r"unclean",
        r"dirt(?:y|ier|iest)?",
        r"filth(?:y)?",
        r"dust(?:y)?",
        r"stain(?:s|ed)?",
        r"mou?ld(?:y)?",
        r"spotless",
        r"hygien(?:e|ic)",
        r"grim(?:e|y)",
        r"smell(?:s|ed|y)?",
        r"stink(?:s|y)?",
        r"housekeeping",
        r"cockroach(?:es)?",
        r"bed ?bugs?",
        r"hairs? (?:in|on) the",
        r"tidy",
        r"(?:fresh|clean) (?:sheets|towels|linen)",
    ],
    "Check-in experience": [
        r"check[- ]?in",
        r"check[- ]?out",
        r"key ?(?:card|code)s?",
        r"keys? (?:were|was|did|didn'?t)",
        r"arrival",
        r"(?:our|my|the) (?:booking|reservation)",
        r"reservation",
        r"queue",
        r"waited? (?:for )?\d+ ?(?:min|minutes|hours?)",
    ],
    "Staff/receptionist behaviour": [
        r"staff",
        r"receptionists?",
        r"reception",
        r"front desk",
        r"concierge",
        r"(?:night )?manager",
        r"employees?",
        r"rude(?:ly|ness)?",
        r"friendly",
        r"unfriendly",
        r"helpful",
        r"unhelpful",
        r"welcoming",
        r"polite",
        r"impolite",
        r"dismissive",
        r"customer service",
    ],
    "Noise": [
        r"nois(?:e|y|ier|iest)",
        r"loud(?:ly)?",
        r"quiet(?:er)?",
        r"thin walls?",
        r"soundproof(?:ing|ed)?",
        r"construction",
        r"could hear",
        r"peaceful",
        r"part(?:y|ies)",
        r"music",
        r"traffic",
    ],
    "Facilities": [
        r"wi-?fi",
        r"internet",
        r"lifts?",
        r"elevators?",
        r"gym",
        r"pool",
        r"parking",
        r"laundry",
        r"kitchen(?:ette)?",
        r"air ?con(?:ditioning|ditioner)?",
        r"heating",
        r"breakfast",
        r"rooftop",
        r"facilit(?:y|ies)",
        r"amenit(?:y|ies)",
        r"tv",
        r"hot water",
    ],
    "Location": [
        r"location",
        r"located",
        r"close to",
        r"walking distance",
        r"(?:train|bus|metro|railway) station",
        r"station",
        r"public transport",
        r"neighbou?rhood",
        r"the area",
        r"surroundings",
        r"central(?:ly)?",
        r"harbou?r",
        r"beach",
        r"unsafe",
        r"near(?:by)? (?:shops|cafes|restaurants|the)",
    ],
    "Room condition": [
        r"(?:room|bathroom) was (?:tired|outdated|old|dated|tiny|small|cramped|modern|spacious)",
        r"outdated",
        r"dated",
        r"run[- ]down",
        r"worn(?: out)?",
        r"renovat(?:ed|ion)",
        r"well maintained",
        r"poorly maintained",
        r"mattress",
        r"comfortable bed",
        r"uncomfortable bed",
        r"furniture",
        r"peeling",
        r"leak(?:s|ing|y)?",
        r"broken (?:lamp|window|door|shower|tap|toilet|furniture|chair|bed|blind|curtain)s?",
        r"damaged",
        r"spacious",
        r"cramped",
    ],
    "Value for money": [
        r"value",
        r"price[dy]?",
        r"overpriced",
        r"expensive",
        r"cheap(?:er)?",
        r"worth",
        r"money",
        r"affordable",
        r"bargain",
        r"rip[- ]?off",
    ],
}


class TopicClassifier(Protocol):
    name: str

    def classify(self, text: str) -> list[str]: ...


class RuleBasedTopicClassifier:
    """Deterministic multi-label classifier using word-boundary keyword regexes."""

    name = "rules-v1"

    def __init__(self, keywords: dict[str, list[str]] | None = None) -> None:
        kw = keywords or TOPIC_KEYWORDS
        self._patterns = {
            topic: re.compile(r"\b(?:" + "|".join(parts) + r")\b", re.IGNORECASE)
            for topic, parts in kw.items()
        }

    def classify(self, text: str) -> list[str]:
        if not text or not text.strip():
            return []
        return [t for t in TOPICS if t in self._patterns and self._patterns[t].search(text)]


default_classifier = RuleBasedTopicClassifier()
