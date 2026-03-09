from __future__ import annotations

import math
from typing import Dict, Iterable, List, Sequence, Set


def precision_at_k(predicted: Sequence[str], relevant: Set[str], k: int) -> float:
    if k <= 0:
        return 0.0
    top_k = predicted[:k]
    if not top_k:
        return 0.0
    hit_count = sum(1 for item in top_k if item in relevant)
    return hit_count / k


def recall_at_k(predicted: Sequence[str], relevant: Set[str], k: int) -> float:
    if not relevant:
        return 0.0
    top_k = predicted[:k]
    hit_count = sum(1 for item in top_k if item in relevant)
    return hit_count / len(relevant)


def ndcg_at_k(predicted: Sequence[str], relevant: Set[str], k: int) -> float:
    if k <= 0 or not relevant:
        return 0.0
    top_k = predicted[:k]
    dcg = 0.0
    for idx, item in enumerate(top_k, start=1):
        if item in relevant:
            dcg += 1.0 / math.log2(idx + 1)

    ideal_hits = min(len(relevant), k)
    idcg = sum(1.0 / math.log2(i + 1) for i in range(1, ideal_hits + 1))
    if idcg == 0:
        return 0.0
    return dcg / idcg


def aggregate_retrieval_metrics(
    recommendations: Dict[str, List[str]],
    gold_relevant: Dict[str, Set[str]],
    k_values: Iterable[int] = (5, 10),
) -> Dict[str, float]:
    metrics: Dict[str, float] = {}
    query_ids = [qid for qid in recommendations.keys() if qid in gold_relevant]
    if not query_ids:
        for k in k_values:
            metrics[f"precision@{k}"] = 0.0
            metrics[f"recall@{k}"] = 0.0
            metrics[f"ndcg@{k}"] = 0.0
        return metrics

    for k in k_values:
        p_scores = []
        r_scores = []
        n_scores = []
        for qid in query_ids:
            predicted = recommendations[qid]
            relevant = gold_relevant[qid]
            p_scores.append(precision_at_k(predicted, relevant, k))
            r_scores.append(recall_at_k(predicted, relevant, k))
            n_scores.append(ndcg_at_k(predicted, relevant, k))
        metrics[f"precision@{k}"] = sum(p_scores) / len(p_scores)
        metrics[f"recall@{k}"] = sum(r_scores) / len(r_scores)
        metrics[f"ndcg@{k}"] = sum(n_scores) / len(n_scores)
    return metrics
