from __future__ import annotations

import argparse
import json
import math
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from .build_query_bank import build_query_bank
from .common import (
    ARTIFACTS_DIR,
    DATASETS_DIR,
    DEFAULT_BASE_MODEL,
    DEFAULT_FINE_TUNED_ARTIFACT,
    QUERY_BANK_VERSION,
    load_profiles_dataframe,
    movie_index_row,
    normalize_text,
    relative_to_root,
    write_json,
)


def _select_device() -> str:
    import torch

    if torch.cuda.is_available():
        return "cuda"
    if getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _sample_rows(rows: list[dict[str, Any]], limit: int | None, seed: int) -> list[dict[str, Any]]:
    if limit is None or limit <= 0 or len(rows) <= limit:
        return rows
    rng = random.Random(seed)
    picked = list(rows)
    rng.shuffle(picked)
    return picked[:limit]


def _reference_index_rows() -> dict[str, dict[str, Any]]:
    for name in ("sbert_en_finetuned_latest", "sbert_latest", "tfidf_latest", "word2vec_latest"):
        path = ARTIFACTS_DIR / name / "movie_index.json"
        if path.exists():
            raw = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                return {str(row["id"]): row for row in raw if row.get("id")}
    return {}


def _doc_row(row: Any, ref_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    base = movie_index_row(row)
    ref = ref_map.get(str(base["id"]))
    if ref:
        for key in ("overview", "poster_path", "genres", "review_count", "release_year", "popularity"):
            if ref.get(key) not in (None, "", []):
                base[key] = ref[key]
    return base


def _precision_at_k(predicted: list[str], relevant: set[str], k: int) -> float:
    top = predicted[:k]
    if not top:
        return 0.0
    return sum(1 for item in top if item in relevant) / float(k)


def _recall_at_k(predicted: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    top = predicted[:k]
    return sum(1 for item in top if item in relevant) / float(len(relevant))


def _ndcg_at_k(predicted: list[str], relevant: set[str], k: int) -> float:
    if not relevant or k <= 0:
        return 0.0
    dcg = 0.0
    for rank, item in enumerate(predicted[:k], start=1):
        if item in relevant:
            dcg += 1.0 / math.log2(rank + 1)
    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(r + 1) for r in range(1, ideal_hits + 1))
    return (dcg / idcg) if idcg > 0 else 0.0


def _eval_retrieval(
    query_rows: list[dict[str, Any]],
    doc_ids: list[str],
    doc_embeddings: np.ndarray,
    query_embeddings: np.ndarray,
) -> dict[str, float]:
    if not query_rows:
        return {f"{metric}@{k}": 0.0 for metric in ("precision", "recall", "ndcg") for k in (5, 10)}

    sims = np.matmul(query_embeddings, doc_embeddings.T)
    metrics = {f"{metric}@{k}": [] for metric in ("precision", "recall", "ndcg") for k in (5, 10)}
    for idx, row in enumerate(query_rows):
        ranked_idx = np.argsort(-sims[idx])
        ranked_ids = [doc_ids[i] for i in ranked_idx]
        relevant = {str(mid) for mid in row.get("positive_movie_ids", [])}
        for k in (5, 10):
            metrics[f"precision@{k}"].append(_precision_at_k(ranked_ids, relevant, k))
            metrics[f"recall@{k}"].append(_recall_at_k(ranked_ids, relevant, k))
            metrics[f"ndcg@{k}"].append(_ndcg_at_k(ranked_ids, relevant, k))
    return {name: float(np.mean(values)) if values else 0.0 for name, values in metrics.items()}


def _similar_by_movie(doc_ids: list[str], doc_embeddings: np.ndarray, top_k: int) -> dict[str, list[dict[str, float]]]:
    sim = np.matmul(doc_embeddings, doc_embeddings.T)
    np.fill_diagonal(sim, -np.inf)
    n = sim.shape[0]
    out: dict[str, list[dict[str, float]]] = {}
    for idx in range(n):
        row = sim[idx]
        top_idx = np.argpartition(-row, range(min(top_k, n - 1)))[:top_k]
        ranked = sorted(top_idx.tolist(), key=lambda j: float(row[j]), reverse=True)
        out[doc_ids[idx]] = [
            {"movie_id": doc_ids[j], "score": float(round(float(row[j]), 6))}
            for j in ranked
            if np.isfinite(row[j])
        ]
    return out


def finetune_biencoder(
    artifact_dir: Path,
    query_bank_dir: Path,
    base_model: str = DEFAULT_BASE_MODEL,
    epochs: int = 1,
    batch_size: int = 32,
    learning_rate: float = 2e-5,
    warmup_ratio: float = 0.1,
    top_k: int = 20,
    max_train_pairs: int | None = 12000,
    seed: int = 42,
) -> dict[str, Path]:
    pairs_path = query_bank_dir / "retrieval_train_pairs.jsonl"
    query_bank_path = query_bank_dir / "retrieval_query_bank.jsonl"
    if not pairs_path.exists() or not query_bank_path.exists():
        build_query_bank(output_dir=query_bank_dir, seed=seed)
    pair_rows = _load_jsonl(pairs_path)
    query_rows = _load_jsonl(query_bank_path)

    train_rows = [row for row in pair_rows if row.get("split") == "train"]
    dev_rows = [row for row in query_rows if row.get("split") == "dev"]
    train_rows = _sample_rows(train_rows, max_train_pairs, seed)

    if not train_rows:
        raise ValueError("No training rows found in retrieval_train_pairs.jsonl")

    from sentence_transformers import InputExample, SentenceTransformer, losses
    from torch.utils.data import DataLoader

    device = _select_device()
    model = SentenceTransformer(base_model, device=device)
    model.max_seq_length = 256

    examples = [InputExample(texts=[row["query"], row["positive_text"]]) for row in train_rows]
    train_loader = DataLoader(examples, shuffle=True, batch_size=batch_size)
    train_loss = losses.MultipleNegativesRankingLoss(model)
    warmup_steps = int(len(train_loader) * max(1, epochs) * warmup_ratio)

    model.fit(
        train_objectives=[(train_loader, train_loss)],
        epochs=epochs,
        warmup_steps=warmup_steps,
        optimizer_params={"lr": learning_rate},
        show_progress_bar=True,
    )

    model_dir = artifact_dir / "model"
    model_dir.mkdir(parents=True, exist_ok=True)
    model.save(str(model_dir))

    df = load_profiles_dataframe()
    ref_map = _reference_index_rows()
    movie_rows = [_doc_row(row, ref_map) for _, row in df.iterrows()]
    doc_texts = [normalize_text(row.get("search_text", "")) for row in movie_rows]
    doc_ids = [str(row["id"]) for row in movie_rows]
    doc_embeddings = model.encode(
        doc_texts,
        batch_size=64,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype(np.float32)

    query_texts = [row["query"] for row in dev_rows]
    if query_texts:
        query_embeddings = model.encode(
            query_texts,
            batch_size=64,
            show_progress_bar=True,
            convert_to_numpy=True,
            normalize_embeddings=True,
        ).astype(np.float32)
    else:
        query_embeddings = np.zeros((0, doc_embeddings.shape[1]), dtype=np.float32)

    similar_by_movie = _similar_by_movie(doc_ids, doc_embeddings, top_k=top_k)
    eval_metrics = _eval_retrieval(dev_rows, doc_ids, doc_embeddings, query_embeddings)

    artifact_version = artifact_dir.name
    artifact_dir.mkdir(parents=True, exist_ok=True)
    np.save(artifact_dir / "embeddings.npy", doc_embeddings)
    write_json(artifact_dir / "movie_index.json", movie_rows)
    write_json(artifact_dir / "similar_by_movie.json", similar_by_movie)
    write_json(
        artifact_dir / "eval.json",
        {
            "query_bank_version": QUERY_BANK_VERSION,
            "dev_query_count": len(dev_rows),
            "train_pair_count": len(train_rows),
            "metrics": eval_metrics,
        },
    )
    metadata = {
        "artifact_type": "sentence_transformer_finetuned",
        "artifact_version": artifact_version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "movie_count": len(movie_rows),
        "top_k": top_k,
        "model_name": relative_to_root(model_dir),
        "base_model_name": base_model,
        "embedding_dim": int(doc_embeddings.shape[1]),
        "fine_tuned": True,
        "language_policy": "english_only",
        "query_bank_version": QUERY_BANK_VERSION,
        "query_bank_dir": relative_to_root(query_bank_dir),
        "train_pair_count": len(train_rows),
        "document_text_field": "search_text",
        "text_representation": "review_profile_then_movie_profile_then_title_genres",
        "eval_path": relative_to_root(artifact_dir / "eval.json"),
        "device_used": device,
    }
    write_json(artifact_dir / "metadata.json", metadata)
    return {
        "artifact_dir": artifact_dir,
        "model_dir": model_dir,
        "query_bank_dir": query_bank_dir,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Fine-tune an English bi-encoder for CineSen retrieval")
    parser.add_argument(
        "--artifact-dir",
        type=Path,
        default=DEFAULT_FINE_TUNED_ARTIFACT,
        help="Output artifact directory for the fine-tuned retriever.",
    )
    parser.add_argument(
        "--query-bank-dir",
        type=Path,
        default=DATASETS_DIR / QUERY_BANK_VERSION,
        help="Directory created by build_query_bank.py",
    )
    parser.add_argument("--base-model", default=DEFAULT_BASE_MODEL)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--learning-rate", type=float, default=2e-5)
    parser.add_argument("--warmup-ratio", type=float, default=0.1)
    parser.add_argument("--top-k", type=int, default=20)
    parser.add_argument("--max-train-pairs", type=int, default=12000)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    outputs = finetune_biencoder(
        artifact_dir=args.artifact_dir,
        query_bank_dir=args.query_bank_dir,
        base_model=args.base_model,
        epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.learning_rate,
        warmup_ratio=args.warmup_ratio,
        top_k=args.top_k,
        max_train_pairs=args.max_train_pairs,
        seed=args.seed,
    )
    for name, path in outputs.items():
        print(f"{name}: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
