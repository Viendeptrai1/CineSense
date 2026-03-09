from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from training.config import config
from training.data.loaders import load_movie_records
from training.data.profiles import build_profiles
from training.data.splits import deterministic_query_candidate_split

try:
    from gensim.models import Word2Vec
except Exception as exc:  # pragma: no cover - defensive import guard
    Word2Vec = None
    IMPORT_ERROR = exc
else:
    IMPORT_ERROR = None


def _tokenize(text: str) -> list[str]:
    return [tok for tok in text.lower().split() if tok.isalpha() and len(tok) > 1]


def _average_embedding(tokens: list[str], model: "Word2Vec", dim: int) -> np.ndarray:
    vectors = [model.wv[t] for t in tokens if t in model.wv]
    if not vectors:
        return np.zeros(dim, dtype=np.float32)
    return np.mean(vectors, axis=0)


def train_word2vec(top_k: int, artifact_name: str) -> Path:
    if Word2Vec is None:
        raise RuntimeError(
            "gensim is required for Word2Vec baseline. "
            f"Import error: {IMPORT_ERROR}"
        )

    movies = load_movie_records(only_english_reviews=True)
    profiles = build_profiles(movies)
    tokenized = [_tokenize(text) for text in profiles]

    model = Word2Vec(
        sentences=tokenized,
        vector_size=200,
        window=5,
        min_count=2,
        workers=4,
        sg=1,
        seed=config.random_seed,
    )

    embeddings = np.vstack([
        _average_embedding(tokens, model, dim=200) for tokens in tokenized
    ])
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
    model.save(str(out_dir / "word2vec.model"))
    (out_dir / "movie_index.json").write_text(json.dumps(movie_index, indent=2), encoding="utf-8")
    (out_dir / "similar_by_movie.json").write_text(json.dumps(similar_by_movie, indent=2), encoding="utf-8")
    (out_dir / "splits.json").write_text(
        json.dumps({"query_ids": query_ids, "candidate_ids": candidate_ids}, indent=2),
        encoding="utf-8",
    )
    (out_dir / "metadata.json").write_text(
        json.dumps(
            {
                "artifact_type": "word2vec",
                "artifact_version": artifact_name,
                "created_at": datetime.now(UTC).isoformat(),
                "vector_size": 200,
                "top_k": top_k,
                "movie_count": len(movies),
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return out_dir


def main() -> None:
    parser = argparse.ArgumentParser(description="Train Word2Vec baseline.")
    parser.add_argument("--top-k", type=int, default=config.default_top_k)
    parser.add_argument("--artifact-name", default="word2vec_latest")
    args = parser.parse_args()

    out_dir = train_word2vec(top_k=args.top_k, artifact_name=args.artifact_name)
    print(f"Word2Vec artifact saved to: {out_dir}")


if __name__ == "__main__":
    main()
