from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from etl_pipeline.config import settings
from etl_pipeline.embedder import get_embedding_model, preprocess_text
from training.config import config
from training.data.loaders import load_movie_records
from training.data.profiles import build_profiles
from training.data.splits import deterministic_query_candidate_split


def train_sentence_transformer(top_k: int, artifact_name: str, batch_size: int = 32) -> Path:
    movies = load_movie_records(only_english_reviews=True)
    raw_profiles = build_profiles(movies)
    profiles = [preprocess_text(text) for text in raw_profiles]

    model = get_embedding_model()
    embeddings = model.encode(
        profiles,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
    )

    sim = cosine_similarity(embeddings, embeddings)
    similar_by_movie: dict[str, list[dict[str, float]]] = {}
    query_ids, candidate_ids = deterministic_query_candidate_split(movies)
    for i, movie in enumerate(movies):
        row = sim[i].copy()
        row[i] = -1.0
        top_idx = np.argsort(row)[::-1][:top_k]
        similar_by_movie[movie.id] = [
            {"movie_id": movies[j].id, "score": float(row[j])}
            for j in top_idx
            if row[j] > 0
        ]

    movie_index = [
        {
            "id": m.id,
            "tmdb_id": m.tmdb_id,
            "title": m.title,
            "overview": m.overview,
            "poster_path": m.poster_path,
            "genres": m.genres,
            "review_count": m.review_count,
            "release_year": m.release_year,
        }
        for m in movies
    ]

    out_dir = config.artifacts_root / artifact_name
    out_dir.mkdir(parents=True, exist_ok=True)
    np.save(out_dir / "embeddings.npy", embeddings)
    (out_dir / "movie_index.json").write_text(
        json.dumps(movie_index, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "similar_by_movie.json").write_text(
        json.dumps(similar_by_movie, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (out_dir / "splits.json").write_text(
        json.dumps({"query_ids": query_ids, "candidate_ids": candidate_ids}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "metadata.json").write_text(
        json.dumps(
            {
                "artifact_type": "sentence_transformer",
                "artifact_version": artifact_name,
                "created_at": datetime.now(UTC).isoformat(),
                "model_name": settings.embedding.model,
                "embedding_dim": int(embeddings.shape[1]),
                "top_k": top_k,
                "movie_count": len(movies),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SentenceTransformer recommendation artifacts.")
    parser.add_argument("--top-k", type=int, default=config.default_top_k)
    parser.add_argument("--artifact-name", default="sbert_latest")
    parser.add_argument("--batch-size", type=int, default=32)
    args = parser.parse_args()

    out_dir = train_sentence_transformer(
        top_k=args.top_k,
        artifact_name=args.artifact_name,
        batch_size=args.batch_size,
    )
    print(f"SentenceTransformer artifact saved to: {out_dir}")


if __name__ == "__main__":
    main()
