from __future__ import annotations

import argparse
import json
from datetime import datetime, UTC
from pathlib import Path

import numpy as np
from scipy.sparse import save_npz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from joblib import dump

from etl_pipeline.embedder import preprocess_text
from training.config import config
from training.data.loaders import load_movie_records
from training.data.profiles import build_profiles
from training.data.splits import deterministic_query_candidate_split


def _artifact_dir(name: str) -> Path:
    root = config.artifacts_root / name
    root.mkdir(parents=True, exist_ok=True)
    return root


def _top_k_neighbors(similarity_row: np.ndarray, self_index: int, top_k: int) -> np.ndarray:
    scores = similarity_row.copy()
    scores[self_index] = -1.0
    if top_k >= len(scores):
        return np.argsort(scores)[::-1]
    candidate = np.argpartition(scores, -top_k)[-top_k:]
    return candidate[np.argsort(scores[candidate])[::-1]]


def train_tfidf(top_k: int, artifact_name: str) -> Path:
    movies = load_movie_records(only_english_reviews=True)
    profiles = build_profiles(movies)

    vectorizer = TfidfVectorizer(
        min_df=2,
        max_df=0.9,
        ngram_range=(1, 2),
        strip_accents="unicode",
        stop_words="english",
        preprocessor=preprocess_text,
    )
    matrix = vectorizer.fit_transform(profiles)

    movie_index = [
        {
            "id": movie.id,
            "tmdb_id": movie.tmdb_id,
            "title": movie.title,
            "overview": movie.overview,
            "poster_path": movie.poster_path,
            "genres": movie.genres,
            "review_count": movie.review_count,
            "release_year": movie.release_year,
        }
        for movie in movies
    ]

    similarities = linear_kernel(matrix, matrix)
    similar_by_movie: dict[str, list[dict[str, float]]] = {}
    query_ids, candidate_ids = deterministic_query_candidate_split(movies)

    for idx, movie in enumerate(movies):
        neighbors = _top_k_neighbors(similarities[idx], idx, top_k)
        similar_by_movie[movie.id] = [
            {"movie_id": movies[n].id, "score": float(similarities[idx, n])}
            for n in neighbors
            if similarities[idx, n] > 0
        ]

    out_dir = _artifact_dir(artifact_name)
    dump(vectorizer, out_dir / "vectorizer.joblib")
    save_npz(out_dir / "tfidf_matrix.npz", matrix)
    (out_dir / "movie_index.json").write_text(
        json.dumps(movie_index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "similar_by_movie.json").write_text(
        json.dumps(similar_by_movie, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (out_dir / "splits.json").write_text(
        json.dumps({"query_ids": query_ids, "candidate_ids": candidate_ids}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    metadata = {
        "artifact_type": "tfidf",
        "artifact_version": artifact_name,
        "created_at": datetime.now(UTC).isoformat(),
        "model_name": "tfidf-unigram-bigram",
        "top_k": top_k,
        "movie_count": len(movies),
    }
    (out_dir / "metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Train TF-IDF recommendation baseline.")
    parser.add_argument("--top-k", type=int, default=config.default_top_k)
    parser.add_argument("--artifact-name", default="tfidf_latest")
    args = parser.parse_args()

    out_dir = train_tfidf(top_k=args.top_k, artifact_name=args.artifact_name)
    print(f"TF-IDF artifact saved to: {out_dir}")


if __name__ == "__main__":
    main()
