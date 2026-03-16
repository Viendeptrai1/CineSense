from __future__ import annotations

from dataclasses import dataclass
from typing import List

from sqlalchemy.orm import joinedload

from etl_pipeline.db_postgres import CoreMovie, get_session


@dataclass
class MovieRecord:
    id: str
    tmdb_id: int
    title: str
    overview: str
    poster_path: str | None
    genres: List[str]
    reviews: List[str]
    review_count: int
    release_year: int | None
    popularity: float | None
    vote_average: float | None
    vote_count: int | None


def load_movie_records(only_english_reviews: bool = True) -> List[MovieRecord]:
    session = get_session()
    try:
        movies = (
            session.query(CoreMovie)
            .options(joinedload(CoreMovie.genres), joinedload(CoreMovie.reviews))
            .order_by(CoreMovie.created_at.desc())
            .all()
        )

        records: List[MovieRecord] = []
        for movie in movies:
            review_texts = []
            for review in movie.reviews:
                if only_english_reviews and review.language not in {"en", "unknown", None}:
                    continue
                text = (review.content or "").strip()
                if text:
                    review_texts.append(text)

            release_year = movie.release_date.year if movie.release_date else None
            records.append(
                MovieRecord(
                    id=str(movie.id),
                    tmdb_id=movie.tmdb_id,
                    title=(movie.title or "").strip(),
                    overview=(movie.overview or "").strip(),
                    poster_path=movie.poster_path,
                    genres=sorted({g.name for g in movie.genres if g.name}),
                    reviews=review_texts,
                    review_count=len(movie.reviews),
                    release_year=release_year,
                    popularity=movie.popularity,
                    vote_average=movie.vote_average,
                    vote_count=movie.vote_count,
                )
            )

        return records
    finally:
        session.close()
