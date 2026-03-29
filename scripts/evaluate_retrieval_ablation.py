from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from api.recommender import RecommendationStore


@dataclass(frozen=True)
class Metrics:
    recall_at_k: float
    mrr_at_k: float
    ndcg_at_k: float


def dcg(rels: list[int]) -> float:
    out = 0.0
    for i, r in enumerate(rels, start=1):
        if r <= 0:
            continue
        out += (2**r - 1) / np.log2(i + 1)
    return float(out)


def ndcg_at_k(ranked_ids: list[str], relevant: set[str], k: int) -> float:
    rels = [1 if mid in relevant else 0 for mid in ranked_ids[:k]]
    ideal = [1] * min(k, len(relevant))
    denom = dcg(ideal)
    return 0.0 if denom == 0 else dcg(rels) / denom


def mrr_at_k(ranked_ids: list[str], relevant: set[str], k: int) -> float:
    for i, mid in enumerate(ranked_ids[:k], start=1):
        if mid in relevant:
            return 1.0 / i
    return 0.0


def recall_at_k(ranked_ids: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    hit = sum(1 for mid in ranked_ids[:k] if mid in relevant)
    return hit / len(relevant)


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate recommendation retrieval (lightweight ablation).")
    parser.add_argument(
        "--queries",
        type=Path,
        default=Path("Notebook_Report/training/artifacts/tfidf_latest/splits.json"),
        help="JSON with query_ids/candidate_ids (or a custom query set).",
    )
    parser.add_argument("--k", type=int, default=10)
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()

    store = RecommendationStore.load()
    if not store.movie_index:
        raise SystemExit("RecommendationStore not ready. Missing movie_index.json")

    splits = json.loads(args.queries.read_text(encoding="utf-8"))
    query_ids = splits.get("query_ids") or []
    candidate_ids = splits.get("candidate_ids") or []
    if not query_ids or not candidate_ids:
        raise SystemExit("splits.json must contain query_ids and candidate_ids")

    # Build simple pseudo-queries from each query movie title.
    # Relevant set = top-20 similar_by_movie items (if available).
    metrics = []
    for qid in query_ids[: min(len(query_ids), 200)]:
        qrow = store.movie_index.get(str(qid))
        if not qrow:
            continue
        query_text = str(qrow.get("title") or "").strip()
        if len(query_text) < 2:
            continue
        relevant = {item["movie_id"] for item in (store.similar_by_movie.get(str(qid), []) or [])[:20]}
        if not relevant:
            continue
        rows, _semantic_label = store.search_movies(
            query_text, limit=args.limit, query_type="auto", explain=False, absa_refine=False
        )
        ranked = [r["movie_id"] for r in rows]
        metrics.append(
            Metrics(
                recall_at_k=recall_at_k(ranked, relevant, args.k),
                mrr_at_k=mrr_at_k(ranked, relevant, args.k),
                ndcg_at_k=ndcg_at_k(ranked, relevant, args.k),
            )
        )

    if not metrics:
        raise SystemExit("No samples evaluated (missing similar_by_movie or titles).")

    out = {
        "k": args.k,
        "limit": args.limit,
        "n": len(metrics),
        "recall@k": float(np.mean([m.recall_at_k for m in metrics])),
        "mrr@k": float(np.mean([m.mrr_at_k for m in metrics])),
        "ndcg@k": float(np.mean([m.ndcg_at_k for m in metrics])),
        "model": store.metadata.get("artifact_type", "unknown"),
        "artifact_dir": str(store.artifact_dir),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

