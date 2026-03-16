"""
Prepare ABSA dataset from core_review (English).

Reads reviews from PostgreSQL, cleans and sentence-splits, filters noise,
and exports unlabeled JSONL for manual labeling. Labeled JSONL format is
documented for later use by absa_model training.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from uuid import UUID

from etl_pipeline.db_postgres import CoreReview, get_session
from etl_pipeline.embedder import is_noisy_review, preprocess_text


def _sentence_split(text: str) -> list[str]:
    """Split text into sentence-like segments (no nltk dependency)."""
    if not (text or "").strip():
        return []
    # Split on sentence-ending punctuation followed by space or end
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _fetch_english_reviews(session, limit: int | None = None):
    """Yield (review_id, movie_id, content) for English reviews."""
    q = (
        session.query(CoreReview)
        .filter(CoreReview.language.in_(["en", "unknown"]))
        .filter(CoreReview.content.isnot(None))
        .order_by(CoreReview.created_at.desc())
    )
    if limit:
        q = q.limit(limit * 3)  # fetch more rows; we'll limit after expanding sentences
    for r in q.all():
        raw = (r.content or "").strip()
        if len(raw) < 20:
            continue
        yield str(r.id), str(r.movie_id), raw


def run(
    output_path: Path,
    limit_reviews: int | None = None,
    by_sentence: bool = True,
) -> int:
    """
    Export unlabeled ABSA samples to JSONL.

    Args:
        output_path: Path to output .jsonl file.
        limit_reviews: If set, process at most this many reviews (for quick export).
        by_sentence: If True, split each review into sentences; else one sample per review.

    Returns:
        Number of lines written.
    """
    session = get_session()
    count = 0
    seen_texts: set[str] = set()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        with open(output_path, "w", encoding="utf-8") as f:
            for review_id, movie_id, raw in _fetch_english_reviews(session, limit=limit_reviews):
                cleaned = preprocess_text(raw)
                if not cleaned or is_noisy_review(raw):
                    continue

                if by_sentence:
                    segments = _sentence_split(cleaned)
                    if not segments:
                        segments = [cleaned]
                else:
                    segments = [cleaned]

                for idx, text in enumerate(segments):
                    if not text or len(text) < 15:
                        continue
                    if is_noisy_review(text):
                        continue
                    key = (movie_id, text[:200])
                    if key in seen_texts:
                        continue
                    seen_texts.add(key)

                    sample_id = f"{review_id}_{idx}" if by_sentence else review_id
                    record = {
                        "id": sample_id,
                        "movie_id": movie_id,
                        "review_id": review_id,
                        "text": text,
                    }
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")
                    count += 1

                    if limit_reviews and count >= limit_reviews:
                        break
                if limit_reviews and count >= limit_reviews:
                    break
    finally:
        session.close()

    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export unlabeled ABSA samples from core_review to JSONL for manual labeling."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("training/data/absa/absa_unlabeled.jsonl"),
        help="Output JSONL path",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Max number of samples to export (default: all)",
    )
    parser.add_argument(
        "--by-review",
        action="store_true",
        help="One sample per review (no sentence split)",
    )
    args = parser.parse_args()

    n = run(
        output_path=args.output,
        limit_reviews=args.limit,
        by_sentence=not args.by_review,
    )
    print(f"Exported {n} samples to {args.output}")
    print(
        "Next: add 'labels' to each line, e.g. "
        '"labels": [{"aspect": "acting", "sentiment": "positive"}]'
    )


if __name__ == "__main__":
    main()
