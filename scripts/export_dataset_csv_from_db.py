#!/usr/bin/env python3
"""
Export `cinesense_movies.csv` + `cinesense_reviews.csv` directly from Postgres core schema.

Use case: bạn muốn lấy full dữ liệu để chạy notebook mà không mất thời gian crawl/Call API từng movie.

Output CSV columns are aligned with what `Notebook_Report/02_Data_Preprocessing_EDA.ipynb` expects:
- cinesense_movies.csv: tmdb_id,title,overview,genres,release_date,poster_path,vote_average,vote_count,popularity
- cinesense_reviews.csv: review_id,tmdb_id,author,author_name,content,rating,avatar_path,created_at,url,source
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from uuid import UUID

# Allow running from anywhere: ensure repo root is in PYTHONPATH
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl_pipeline.db_postgres import CoreMovie, CoreReview, get_session


def _iso_or_empty(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def export_csv(out_dir: Path, only_english: bool) -> tuple[int, int]:
    out_dir.mkdir(parents=True, exist_ok=True)
    movies_path = out_dir / "cinesense_movies.csv"
    reviews_path = out_dir / "cinesense_reviews.csv"

    movies_headers = [
        "tmdb_id",
        "title",
        "overview",
        "genres",
        "release_date",
        "poster_path",
        "vote_average",
        "vote_count",
        "popularity",
    ]
    reviews_headers = [
        "review_id",
        "tmdb_id",
        "author",
        "author_name",
        "content",
        "rating",
        "avatar_path",
        "created_at",
        "url",
        "source",
    ]

    session = get_session()
    try:
        # 1) Load movies + genres
        movies = session.query(CoreMovie).all()
        movie_by_id = {m.id: m for m in movies}
        # genres: accessed from relationship; can trigger N+1 if not eager-loaded,
        # but dataset is small enough for thesis-scale. Keep it simple.

        # 2) Load reviews (optionally English/unknown only)
        q = session.query(CoreReview)
        if only_english:
            q = q.filter(CoreReview.language.in_(["en", "unknown", None]))

        reviews = q.all()

        # 3) Group reviews by movie uuid (CoreReview.movie_id)
        revs_by_movie_id: dict[UUID, list[CoreReview]] = defaultdict(list)
        for r in reviews:
            revs_by_movie_id[r.movie_id].append(r)

        # 4) Write movies CSV
        with open(movies_path, "w", encoding="utf-8", newline="") as f_movies:
            w_movies = csv.DictWriter(f_movies, fieldnames=movies_headers)
            w_movies.writeheader()
            exported_movies = 0

            for m in movies:
                genres_str = ""
                try:
                    genres_str = ", ".join(sorted({g.name for g in (m.genres or []) if g and g.name}))
                except Exception:
                    genres_str = ""

                w_movies.writerow(
                    {
                        "tmdb_id": m.tmdb_id,
                        "title": m.title or "",
                        "overview": m.overview or "",
                        "genres": genres_str,
                        "release_date": m.release_date.isoformat() if m.release_date else "",
                        "poster_path": m.poster_path or "",
                        "vote_average": m.vote_average if m.vote_average is not None else "",
                        "vote_count": m.vote_count if m.vote_count is not None else "",
                        "popularity": m.popularity if m.popularity is not None else "",
                    }
                )
                exported_movies += 1

        # 5) Write reviews CSV
        with open(reviews_path, "w", encoding="utf-8", newline="") as f_reviews:
            w_reviews = csv.DictWriter(f_reviews, fieldnames=reviews_headers)
            w_reviews.writeheader()
            exported_reviews = 0

            for movie_id, rev_list in revs_by_movie_id.items():
                movie = movie_by_id.get(movie_id)
                if not movie:
                    continue
                tmdb_id = movie.tmdb_id

                for r in rev_list:
                    review_id = r.external_review_id or str(r.id)
                    created_at = r.source_created_at or r.created_at
                    w_reviews.writerow(
                        {
                            "review_id": review_id,
                            "tmdb_id": tmdb_id,
                            "author": r.author_username or "",
                            "author_name": r.author_name or "",
                            "content": r.content or "",
                            "rating": r.rating if r.rating is not None else "",
                            "avatar_path": r.author_avatar_url or "",
                            "created_at": _iso_or_empty(created_at),
                            "url": r.source_url or "",
                            "source": r.source or "",
                        }
                    )
                    exported_reviews += 1

        return exported_movies, exported_reviews

    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Export CineSense CSV from Postgres core schema.")
    parser.add_argument("--out-dir", default="Notebook_Report", help="Output directory")
    parser.add_argument(
        "--only-english",
        action="store_true",
        help="Export only English/unknown reviews (recommended for thesis baseline).",
    )
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    movies_n, reviews_n = export_csv(out_dir=out_dir, only_english=args.only_english)
    print(f"Export done: movies={movies_n}, reviews={reviews_n}")
    print(f"- {out_dir / 'cinesense_movies.csv'}")
    print(f"- {out_dir / 'cinesense_reviews.csv'}")


if __name__ == "__main__":
    main()

