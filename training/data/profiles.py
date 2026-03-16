from __future__ import annotations

from typing import Iterable, List

from training.config import config
from training.data.loaders import MovieRecord
from etl_pipeline.embedder import is_noisy_review


def _truncate(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rsplit(" ", 1)[0] + "..."


def build_movie_profile(movie: MovieRecord) -> str:
    title = movie.title or ""
    overview = movie.overview or ""
    genres = ", ".join(movie.genres) if movie.genres else ""
    # Filter out noisy reviews (e.g. "... ... ...") before building snippets
    meaningful_reviews = [
        r for r in movie.reviews if r and not is_noisy_review(r)
    ]
    snippets = [
        _truncate(r, config.max_review_chars)
        for r in meaningful_reviews[: config.max_review_snippets]
    ]
    review_block = " ".join(snippets)

    sections = [
        f"title: {title}",
        f"overview: {overview}",
        f"genres: {genres}",
        f"reviews: {review_block}",
    ]
    return " | ".join(section for section in sections if section.strip())


def build_profiles(movies: Iterable[MovieRecord]) -> List[str]:
    return [build_movie_profile(movie) for movie in movies]
