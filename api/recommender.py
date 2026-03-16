from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _resolve_artifact_dir() -> Path:
    configured = os.getenv("RECOMMENDER_ARTIFACT_DIR")
    if configured:
        return Path(configured)
    # Prefer improved English SentenceTransformer output, then multilingual/baseline fallback.
    candidates = [
        Path("training/artifacts/sbert_en_latest"),
        Path("training/artifacts/sbert_latest"),
        Path("training/artifacts/tfidf_latest"),
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


@dataclass
class RecommendationStore:
    artifact_dir: Path
    metadata: dict[str, Any]
    movie_index: dict[str, dict[str, Any]]
    similar_by_movie: dict[str, list[dict[str, Any]]]

    @classmethod
    def load(cls) -> "RecommendationStore":
        artifact_dir = _resolve_artifact_dir()
        metadata = {}
        movie_index: dict[str, dict[str, Any]] = {}
        similar_by_movie: dict[str, list[dict[str, Any]]] = {}

        metadata_path = artifact_dir / "metadata.json"
        index_path = artifact_dir / "movie_index.json"
        similar_path = artifact_dir / "similar_by_movie.json"

        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        if index_path.exists():
            rows = json.loads(index_path.read_text(encoding="utf-8"))
            movie_index = {row["id"]: row for row in rows}
        if similar_path.exists():
            similar_by_movie = json.loads(similar_path.read_text(encoding="utf-8"))

        return cls(
            artifact_dir=artifact_dir,
            metadata=metadata,
            movie_index=movie_index,
            similar_by_movie=similar_by_movie,
        )

    def is_ready(self) -> bool:
        return bool(self.movie_index and self.similar_by_movie)

    def similar_movies(self, movie_id: str, limit: int = 10) -> list[dict[str, Any]]:
        rows = self.similar_by_movie.get(movie_id, [])
        output = []
        for row in rows[:limit]:
            candidate = self.movie_index.get(row["movie_id"])
            if not candidate:
                continue
            output.append(
                {
                    "movie_id": candidate["id"],
                    "title": candidate.get("title"),
                    "overview": candidate.get("overview"),
                    "poster_path": candidate.get("poster_path"),
                    "genres": candidate.get("genres", []),
                    "review_count": candidate.get("review_count", 0),
                    "score": float(row.get("score", 0.0)),
                }
            )
        return output

    def trending_movies(self, limit: int = 10) -> list[dict[str, Any]]:
        ranked = sorted(
            self.movie_index.values(),
            key=lambda m: (m.get("review_count", 0), m.get("release_year") or 0),
            reverse=True,
        )
        return [
            {
                "movie_id": row["id"],
                "title": row.get("title"),
                "overview": row.get("overview"),
                "poster_path": row.get("poster_path"),
                "genres": row.get("genres", []),
                "review_count": row.get("review_count", 0),
                "score": None,
            }
            for row in ranked[:limit]
        ]

    def search_movies(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        query_terms = {token for token in query.lower().split() if token}
        if not query_terms:
            return []

        scored = []
        for row in self.movie_index.values():
            haystack = " ".join(
                [
                    row.get("title", ""),
                    row.get("overview", ""),
                    " ".join(row.get("genres", [])),
                ]
            ).lower()
            hits = sum(1 for term in query_terms if term in haystack)
            if hits > 0:
                score = hits / len(query_terms)
                scored.append((score, row))

        scored.sort(key=lambda item: (item[0], item[1].get("review_count", 0)), reverse=True)
        return [
            {
                "movie_id": row["id"],
                "title": row.get("title"),
                "overview": row.get("overview"),
                "poster_path": row.get("poster_path"),
                "genres": row.get("genres", []),
                "review_count": row.get("review_count", 0),
                "score": float(score),
            }
            for score, row in scored[:limit]
        ]


_store: RecommendationStore | None = None


def get_recommendation_store() -> RecommendationStore:
    global _store
    if _store is None:
        _store = RecommendationStore.load()
    return _store


def reload_recommendation_store() -> RecommendationStore:
    global _store
    _store = RecommendationStore.load()
    return _store
