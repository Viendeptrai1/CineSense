#!/usr/bin/env python3
"""
Export `cinesense_movies.csv` + `cinesense_reviews.csv` from running API.

This lets you skip TMDB crawling when you already have data in Postgres.

Expected API endpoints (FastAPI):
- GET  /movies?page=1&page_size=20
- GET  /movies/{movie_id}
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Any, Iterable, Optional

import httpx


def _genres_to_str(genres: Any) -> str:
    """
    Convert API genres payload to comma-separated string expected by notebooks.
    API returns: List[{"id": int, "name": str}]
    """
    if genres is None:
        return ""
    if isinstance(genres, str):
        return genres
    if isinstance(genres, list):
        names: list[str] = []
        for g in genres:
            if isinstance(g, dict) and "name" in g:
                if g["name"]:
                    names.append(str(g["name"]))
            elif isinstance(g, str) and g.strip():
                names.append(g.strip())
        return ", ".join(names)
    return ""


def _first_n(it: Iterable[Any], n: Optional[int]) -> list[Any]:
    if n is None:
        return list(it)
    out: list[Any] = []
    for x in it:
        out.append(x)
        if len(out) >= n:
            break
    return out


def export_csv(
    base_url: str,
    out_dir: Path,
    page_size: int,
    max_movies: Optional[int],
    max_reviews_per_movie: Optional[int],
    timeout_s: float,
) -> None:
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

    exported_movies = 0
    exported_reviews = 0

    page = 1
    with httpx.Client(timeout=timeout_s) as client, \
        open(movies_path, "w", encoding="utf-8", newline="") as movies_fp, \
        open(reviews_path, "w", encoding="utf-8", newline="") as reviews_fp:

        movies_writer = csv.DictWriter(movies_fp, fieldnames=movies_headers)
        reviews_writer = csv.DictWriter(reviews_fp, fieldnames=reviews_headers)
        movies_writer.writeheader()
        reviews_writer.writeheader()

        while True:
            if max_movies is not None and exported_movies >= max_movies:
                break

            r = client.get(f"{base_url.rstrip('/')}/movies", params={"page": page, "page_size": page_size})
            r.raise_for_status()
            payload = r.json()
            items = payload.get("movies") or []
            if not items:
                break

            for m in items:
                if max_movies is not None and exported_movies >= max_movies:
                    break

                movie_uuid = m.get("id")
                tmdb_id = m.get("tmdb_id")
                if not movie_uuid or tmdb_id is None:
                    continue

                # movie detail contains reviews
                r2 = client.get(f"{base_url.rstrip('/')}/movies/{movie_uuid}")
                r2.raise_for_status()
                detail = r2.json()

                title = m.get("title") or detail.get("title") or ""
                overview = m.get("overview") or detail.get("overview") or ""
                genres_str = _genres_to_str(m.get("genres") or detail.get("genres"))
                release_date = detail.get("release_date") or m.get("release_date")
                poster_path = detail.get("poster_path") or m.get("poster_path")
                vote_average = m.get("average_rating")  # API uses average_rating
                vote_count = detail.get("review_count") or m.get("review_count")
                popularity = None  # API does not expose popularity/vote_count in this schema

                movies_writer.writerow(
                    {
                        "tmdb_id": tmdb_id,
                        "title": title,
                        "overview": overview,
                        "genres": genres_str,
                        "release_date": release_date,
                        "poster_path": poster_path,
                        "vote_average": vote_average,
                        "vote_count": vote_count,
                        "popularity": popularity,
                    }
                )
                exported_movies += 1

                # Reviews
                reviews = detail.get("reviews") or []
                reviews = _first_n(reviews, max_reviews_per_movie)
                for rev in reviews:
                    reviews_writer.writerow(
                        {
                            "review_id": rev.get("id"),
                            "tmdb_id": tmdb_id,
                            "author": rev.get("user") or "",
                            "author_name": rev.get("author_name") or "",
                            "content": rev.get("content") or "",
                            "rating": rev.get("rating"),
                            "avatar_path": rev.get("author_avatar_url") or "",
                            "created_at": rev.get("created_at"),
                            "url": "",
                            "source": rev.get("source") or "",
                        }
                    )
                exported_reviews += len(reviews)

            page += 1

    print(f"Export done: movies={exported_movies}, reviews={exported_reviews}")
    print(f"- {movies_path}")
    print(f"- {reviews_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Export movies+reviews CSV from running CineSense API.")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--out-dir", default="Notebook_Report", help="Output directory for CSV files")
    parser.add_argument("--page-size", type=int, default=20, help="GET /movies page_size")
    parser.add_argument("--max-movies", type=int, default=None, help="Limit number of movies (None for all)")
    parser.add_argument(
        "--max-reviews-per-movie",
        type=int,
        default=10,
        help="Limit number of reviews per movie to export (None for all)",
    )
    parser.add_argument("--timeout-s", type=float, default=30.0, help="HTTP timeout seconds")
    args = parser.parse_args()

    out_dir = Path(args.out_dir).resolve()
    export_csv(
        base_url=args.base_url,
        out_dir=out_dir,
        page_size=args.page_size,
        max_movies=args.max_movies,
        max_reviews_per_movie=args.max_reviews_per_movie,
        timeout_s=args.timeout_s,
    )


if __name__ == "__main__":
    main()

