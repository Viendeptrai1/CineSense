#!/usr/bin/env python3
"""
Audit English-first core schema quality for training readiness.

Outputs:
- JSON summary to stdout
- Optional JSON file for reproducible reporting
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import func

# Allow running from repository root or scripts/ directory.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl_pipeline.db_postgres import CoreMovie, CoreReview, CoreGenre, get_session


@dataclass
class CoreAuditSummary:
    movies_total: int
    reviews_total: int
    genres_total: int
    movies_with_title: int
    movies_with_overview: int
    movies_with_release_date: int
    movies_with_poster: int
    movies_with_popularity: int
    movies_with_vote_average: int
    movies_with_vote_count: int
    reviews_with_content: int
    reviews_with_rating: int
    reviews_with_external_id: int
    reviews_with_source_url: int
    reviews_with_source_created_at: int
    review_language_distribution: dict[str, int]
    movies_without_reviews: int
    movies_with_1_to_3_reviews: int
    movies_with_4_to_10_reviews: int
    movies_with_gt_10_reviews: int


def build_summary() -> CoreAuditSummary:
    session = get_session()
    try:
        movies_total = session.query(CoreMovie).count()
        reviews_total = session.query(CoreReview).count()
        genres_total = session.query(CoreGenre).count()

        movies_with_title = session.query(CoreMovie).filter(
            CoreMovie.title.is_not(None), CoreMovie.title != ""
        ).count()
        movies_with_overview = session.query(CoreMovie).filter(
            CoreMovie.overview.is_not(None), CoreMovie.overview != ""
        ).count()
        movies_with_release_date = session.query(CoreMovie).filter(
            CoreMovie.release_date.is_not(None)
        ).count()
        movies_with_poster = session.query(CoreMovie).filter(
            CoreMovie.poster_path.is_not(None), CoreMovie.poster_path != ""
        ).count()
        movies_with_popularity = session.query(CoreMovie).filter(
            CoreMovie.popularity.is_not(None)
        ).count()
        movies_with_vote_average = session.query(CoreMovie).filter(
            CoreMovie.vote_average.is_not(None)
        ).count()
        movies_with_vote_count = session.query(CoreMovie).filter(
            CoreMovie.vote_count.is_not(None)
        ).count()

        reviews_with_content = session.query(CoreReview).filter(
            CoreReview.content.is_not(None), CoreReview.content != ""
        ).count()
        reviews_with_rating = session.query(CoreReview).filter(
            CoreReview.rating.is_not(None)
        ).count()
        reviews_with_external_id = session.query(CoreReview).filter(
            CoreReview.external_review_id.is_not(None), CoreReview.external_review_id != ""
        ).count()
        reviews_with_source_url = session.query(CoreReview).filter(
            CoreReview.source_url.is_not(None), CoreReview.source_url != ""
        ).count()
        reviews_with_source_created_at = session.query(CoreReview).filter(
            CoreReview.source_created_at.is_not(None)
        ).count()

        language_rows = session.query(
            CoreReview.language,
            func.count(CoreReview.id),
        ).group_by(CoreReview.language).all()
        review_language_distribution = {lang or "unknown": count for lang, count in language_rows}

        review_counts_subq = (
            session.query(
                CoreMovie.id.label("movie_id"),
                func.count(CoreReview.id).label("review_count"),
            )
            .outerjoin(CoreReview, CoreMovie.id == CoreReview.movie_id)
            .group_by(CoreMovie.id)
            .subquery()
        )

        movies_without_reviews = session.query(review_counts_subq).filter(
            review_counts_subq.c.review_count == 0
        ).count()
        movies_with_1_to_3_reviews = session.query(review_counts_subq).filter(
            review_counts_subq.c.review_count.between(1, 3)
        ).count()
        movies_with_4_to_10_reviews = session.query(review_counts_subq).filter(
            review_counts_subq.c.review_count.between(4, 10)
        ).count()
        movies_with_gt_10_reviews = session.query(review_counts_subq).filter(
            review_counts_subq.c.review_count > 10
        ).count()

        return CoreAuditSummary(
            movies_total=movies_total,
            reviews_total=reviews_total,
            genres_total=genres_total,
            movies_with_title=movies_with_title,
            movies_with_overview=movies_with_overview,
            movies_with_release_date=movies_with_release_date,
            movies_with_poster=movies_with_poster,
            movies_with_popularity=movies_with_popularity,
            movies_with_vote_average=movies_with_vote_average,
            movies_with_vote_count=movies_with_vote_count,
            reviews_with_content=reviews_with_content,
            reviews_with_rating=reviews_with_rating,
            reviews_with_external_id=reviews_with_external_id,
            reviews_with_source_url=reviews_with_source_url,
            reviews_with_source_created_at=reviews_with_source_created_at,
            review_language_distribution=review_language_distribution,
            movies_without_reviews=movies_without_reviews,
            movies_with_1_to_3_reviews=movies_with_1_to_3_reviews,
            movies_with_4_to_10_reviews=movies_with_4_to_10_reviews,
            movies_with_gt_10_reviews=movies_with_gt_10_reviews,
        )
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit core schema data quality for training.")
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional output path for JSON summary.",
    )
    args = parser.parse_args()

    summary = build_summary()
    payload: dict[str, Any] = asdict(summary)
    serialized = json.dumps(payload, indent=2, ensure_ascii=False)
    print(serialized)

    if args.output_json:
        with open(args.output_json, "w", encoding="utf-8") as fp:
            fp.write(serialized + "\n")


if __name__ == "__main__":
    main()
