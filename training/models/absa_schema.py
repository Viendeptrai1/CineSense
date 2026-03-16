"""
Aspect-Based Sentiment Analysis schema for movie reviews.

Shared constants and label mappings for training and inference.
"""

from __future__ import annotations

ASPECTS = [
    "script",
    "acting",
    "visuals",
    "music",
    "pacing",
    "direction",
    "overall",
]

SENTIMENTS = [
    "negative",
    "neutral",
    "positive",
]

# Number of output labels: each (aspect, sentiment) is one dimension in multi-label setup
NUM_LABELS = len(ASPECTS) * len(SENTIMENTS)

# Index ordering: label_idx = aspect_idx * len(SENTIMENTS) + sentiment_idx
def get_label_index(aspect: str, sentiment: str) -> int:
    a = ASPECTS.index(aspect) if aspect in ASPECTS else -1
    s = SENTIMENTS.index(sentiment) if sentiment in SENTIMENTS else -1
    if a < 0 or s < 0:
        raise ValueError(f"Unknown aspect={aspect!r} or sentiment={sentiment!r}")
    return a * len(SENTIMENTS) + s


def index_to_aspect_sentiment(idx: int) -> tuple[str, str]:
    if idx < 0 or idx >= NUM_LABELS:
        raise ValueError(f"Label index out of range: {idx}")
    a = idx // len(SENTIMENTS)
    s = idx % len(SENTIMENTS)
    return ASPECTS[a], SENTIMENTS[s]


def build_label_map() -> list[dict]:
    """List of {aspect, sentiment} for each index (for schema.json export)."""
    return [
        {"index": i, "aspect": ASPECTS[i // len(SENTIMENTS)], "sentiment": SENTIMENTS[i % len(SENTIMENTS)]}
        for i in range(NUM_LABELS)
    ]
