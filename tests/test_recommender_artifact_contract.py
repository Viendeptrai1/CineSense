from __future__ import annotations

import json
from pathlib import Path

from api.recommender import RecommendationStore


def _write_artifact(root: Path) -> Path:
    artifact = root / "artifact"
    artifact.mkdir(parents=True)
    metadata = {
        "artifact_type": "sentence_transformer_finetuned",
        "artifact_version": "unit_test_artifact",
        "document_text_field": "search_text",
        "text_representation": "review_profile_then_movie_profile_then_title_genres",
        "fine_tuned": True,
    }
    rows = [
        {
            "id": "m1",
            "tmdb_id": 1,
            "title": "Space Echoes",
            "overview": "Sci-fi drama",
            "genres": ["Science Fiction", "Drama"],
            "review_count": 4,
            "search_text": "space survival visuals emotional sci fi drama",
        },
        {
            "id": "m2",
            "tmdb_id": 2,
            "title": "Quiet Orbit",
            "overview": "Slow mission",
            "genres": ["Science Fiction"],
            "review_count": 2,
            "search_text": "slow burn orbit mission with strong acting and visuals",
        },
    ]
    similar = {
        "m1": [{"movie_id": "m2", "score": 0.88}],
        "m2": [{"movie_id": "m1", "score": 0.88}],
    }
    (artifact / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (artifact / "movie_index.json").write_text(json.dumps(rows), encoding="utf-8")
    (artifact / "similar_by_movie.json").write_text(json.dumps(similar), encoding="utf-8")
    return artifact


def test_load_from_artifact_prefers_search_text(tmp_path: Path) -> None:
    artifact = _write_artifact(tmp_path)

    store = RecommendationStore.load_from_artifact(artifact)

    assert store.document_text_field == "search_text"
    assert store.text_representation == "review_profile_then_movie_profile_then_title_genres"
    assert store.search_docs[0] == "space survival visuals emotional sci fi drama"


def test_debug_exposes_artifact_metadata(tmp_path: Path) -> None:
    artifact = _write_artifact(tmp_path)

    store = RecommendationStore.load_from_artifact(artifact)
    rows, debug = store.search_movies_with_debug(
        query="space visuals and strong acting",
        limit=2,
        query_type="auto",
        filters=None,
        absa_refine=False,
        explain=False,
        user_history=None,
        rerank=False,
        weights_override=None,
        semantic_backend="tfidf",
    )

    assert rows
    assert debug is not None
    assert debug["artifact_version"] == "unit_test_artifact"
    assert debug["artifact_text_representation"] == "review_profile_then_movie_profile_then_title_genres"
    assert debug["artifact_fine_tuned"] is True
