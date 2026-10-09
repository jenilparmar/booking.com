# Topic classification and sentiment

Both are **approximate, rule-based** methods. No accuracy figures are claimed: they have not been
evaluated against a labelled ground-truth set. The UI labels topic results as "approximate,
keyword-based".

Code: `backend/app/services/classify.py`, `sentiment.py`, `processing.py`.

## Topics

Eight topics, **multi-label** (a review can have any number, including none):
Cleanliness, Check-in experience, Staff/receptionist behaviour, Noise, Facilities, Location,
Room condition, Value for money.

### How matching works

- The review title and text are joined (`"<title>. <text>"`) and matched case-insensitively.
- Each keyword is a regex fragment wrapped in word boundaries (`\b...\b`), so `cleanser` does not
  match `clean`, `poolside` does not match `pool`, and `priceless` does not match `price`.
- A topic is assigned when **any** of its keywords matches. Output order is the fixed topic order.
- **Negation:** a topic means "this review talks about X", not "this review complains about X".
  "The room was not clean" and "spotless room" are both tagged Cleanliness. Polarity comes from
  the sentiment step, which handles common negation ("not clean" → negative). Analytics combine
  the two: a "negative topic" is a topic on a review whose text sentiment is negative.
- **Language:** keywords are English. Non-English reviews usually receive no topics.
- Implementations are swappable via the `TopicClassifier` protocol (e.g. a future ML model).

### Keyword lists (`TOPIC_KEYWORDS`)

### Cleanliness

`clean(?:ed|er|est|ing|liness|ly)?`, `unclean`, `dirt(?:y|ier|iest)?`, `filth(?:y)?`, `dust(?:y)?`, `stain(?:s|ed)?`, `mou?ld(?:y)?`, `spotless`, `hygien(?:e|ic)`, `grim(?:e|y)`, `smell(?:s|ed|y)?`, `stink(?:s|y)?`, `housekeeping`, `cockroach(?:es)?`, `bed ?bugs?`, `hairs? (?:in|on) the`, `tidy`, `(?:fresh|clean) (?:sheets|towels|linen)`

### Check-in experience

`check[- ]?in`, `check[- ]?out`, `key ?(?:card|code)s?`, `keys? (?:were|was|did|didn'?t)`, `arrival`, `(?:our|my|the) (?:booking|reservation)`, `reservation`, `queue`, `waited? (?:for )?\d+ ?(?:min|minutes|hours?)`

### Staff/receptionist behaviour

`staff`, `receptionists?`, `reception`, `front desk`, `concierge`, `(?:night )?manager`, `employees?`, `rude(?:ly|ness)?`, `friendly`, `unfriendly`, `helpful`, `unhelpful`, `welcoming`, `polite`, `impolite`, `dismissive`, `customer service`

### Noise

`nois(?:e|y|ier|iest)`, `loud(?:ly)?`, `quiet(?:er)?`, `thin walls?`, `soundproof(?:ing|ed)?`, `construction`, `could hear`, `peaceful`, `part(?:y|ies)`, `music`, `traffic`

### Facilities

`wi-?fi`, `internet`, `lifts?`, `elevators?`, `gym`, `pool`, `parking`, `laundry`, `kitchen(?:ette)?`, `air ?con(?:ditioning|ditioner)?`, `heating`, `breakfast`, `rooftop`, `facilit(?:y|ies)`, `amenit(?:y|ies)`, `tv`, `hot water`

### Location

`location`, `located`, `close to`, `walking distance`, `(?:train|bus|metro|railway) station`, `station`, `public transport`, `neighbou?rhood`, `the area`, `surroundings`, `central(?:ly)?`, `harbou?r`, `beach`, `unsafe`, `near(?:by)? (?:shops|cafes|restaurants|the)`

### Room condition

`(?:room|bathroom) was (?:tired|outdated|old|dated|tiny|small|cramped|modern|spacious)`, `outdated`, `dated`, `run[- ]down`, `worn(?: out)?`, `renovat(?:ed|ion)`, `well maintained`, `poorly maintained`, `mattress`, `comfortable bed`, `uncomfortable bed`, `furniture`, `peeling`, `leak(?:s|ing|y)?`, `broken (?:lamp|window|door|shower|tap|toilet|furniture|chair|bed|blind|curtain)s?`, `damaged`, `spacious`, `cramped`

### Value for money

`value`, `price[dy]?`, `overpriced`, `expensive`, `cheap(?:er)?`, `worth`, `money`, `affordable`, `bargain`, `rip[- ]?off`

### Known limitations

- Keyword rules miss paraphrases ("couldn't sleep a wink" is not tagged Noise) and can misfire on
  incidental mentions ("we went to the beach" tags Location even if the review is about the room).
- Sarcasm, mixed reviews, and per-topic polarity are not modelled.

## Sentiment

- Method: [VADER](https://github.com/cjhutto/vaderSentiment) 3.3.2, a local lexicon + rules model
  for English. No network calls, no paid APIs.
- Score: VADER's `compound` value in [-1, 1], stored as `sentiment_score`. It is a lexicon score,
  **not** a probability or confidence.
- Labels (thresholds recommended by VADER's authors):
  - `positive` if compound ≥ 0.05
  - `negative` if compound ≤ −0.05
  - `neutral` otherwise
- Reviews whose declared `language` is not English are labelled `neutral` with a NULL score rather
  than guessed. Empty text is `neutral` with a NULL score.
- The guest's **star rating is never used** to compute sentiment. Rating and text sentiment are
  stored separately and can disagree (e.g. a 9/10 with a complaint in the text).

## When the rules change

Topics and sentiment are computed at import time and stored. After editing keyword lists or
thresholds, recompute everything:

```powershell
cd backend
uv run python -m app.cli reclassify
```

## Content hash

Used for dedup when a record has no `source_review_id`:

```
sha256( property_id ␟ lower(collapse_ws(review_text)) ␟ lower(collapse_ws(review_title))
        ␟ published_at as UTC "YYYY-MM-DDTHH:MM:SSZ" ␟ rating as "%.2f" )
```

`␟` is the ASCII unit separator (0x1F). Missing values hash as the empty string. The database
enforces `UNIQUE (property_id, content_hash)`, plus a partial unique index on
`(property_id, source_review_id)` where the id is present.
