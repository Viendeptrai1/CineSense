#!/usr/bin/env python3
"""
Populate the parallel English-first core schema without touching legacy tables.

This migration is intentionally non-destructive:
- create new core_* tables if they do not exist
- copy/update data from existing tables
- keep all legacy social/search tables intact
"""

import os
import sys

from sqlalchemy.orm import selectinload

# Allow running the script from the repository root or scripts/ directory.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from etl_pipeline.database import (
    init_database,
    get_session,
    Movie,
    Review,
    Genre,
    CoreMovie,
    CoreReview,
    CoreGenre,
)
from etl_pipeline.crawler import TMDBClient


def _safe_title(movie: Movie) -> str:
    return (movie.title_en or movie.title_vi or "").strip()


def _safe_overview(movie: Movie) -> str | None:
    overview = (movie.overview_en or movie.overview_vi or "").strip()
    return overview or None


def migrate_genres(session) -> int:
    english_names = {}
    try:
        with TMDBClient(language="en-US") as client:
            english_names = {genre.id: genre.name for genre in client.get_genres()}
    except Exception:
        english_names = {}

    migrated = 0
    for genre in session.query(Genre).all():
        canonical_name = english_names.get(genre.id, genre.name)
        core_genre = session.get(CoreGenre, genre.id)
        if core_genre is None:
            core_genre = CoreGenre(id=genre.id, name=canonical_name)
            session.add(core_genre)
            migrated += 1
        elif core_genre.name != canonical_name:
            core_genre.name = canonical_name
    return migrated


def migrate_movies(session) -> tuple[int, int]:
    created = 0
    updated = 0
    movies = (
        session.query(Movie)
        .options(selectinload(Movie.genres))
        .all()
    )
    for movie in movies:
        title = _safe_title(movie)
        if not title or movie.tmdb_id is None:
            continue

        core_movie = session.get(CoreMovie, movie.id)
        if core_movie is None:
            core_movie = CoreMovie(id=movie.id, tmdb_id=movie.tmdb_id, title=title)
            session.add(core_movie)
            created += 1
        else:
            updated += 1

        core_movie.title = title
        core_movie.original_title = movie.title_en or movie.title_vi
        core_movie.overview = _safe_overview(movie)
        core_movie.release_date = movie.release_date
        core_movie.poster_path = movie.poster_path
        core_movie.created_at = movie.created_at
        core_movie.updated_at = movie.updated_at or movie.created_at
        core_movie.genres = [session.get(CoreGenre, genre.id) for genre in movie.genres]
    return created, updated


def migrate_reviews(session) -> tuple[int, int]:
    created = 0
    updated = 0
    reviews = session.query(Review).all()
    for review in reviews:
        if session.get(CoreMovie, review.movie_id) is None:
            continue

        core_review = session.get(CoreReview, review.id)
        if core_review is None:
            core_review = CoreReview(id=review.id, movie_id=review.movie_id, content=review.content)
            session.add(core_review)
            created += 1
        else:
            updated += 1

        core_review.movie_id = review.movie_id
        core_review.source = review.source or "tmdb"
        core_review.language = "en"
        core_review.author_name = review.author_name
        core_review.author_avatar_url = review.author_avatar_url
        core_review.content = review.content
        core_review.rating = review.rating
        core_review.created_at = review.created_at
    return created, updated


def main() -> None:
    print("Starting non-destructive core schema migration...")
    init_database()

    session = get_session()
    try:
        genres_created = migrate_genres(session)
        movies_created, movies_updated = migrate_movies(session)
        reviews_created, reviews_updated = migrate_reviews(session)
        session.commit()

        print(f"Core genres created: {genres_created}")
        print(f"Core movies created: {movies_created}, updated: {movies_updated}")
        print(f"Core reviews created: {reviews_created}, updated: {reviews_updated}")
        print("Core schema migration completed safely.")
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
