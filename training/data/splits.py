from __future__ import annotations

import hashlib
from typing import Iterable, Tuple, List

from training.data.loaders import MovieRecord


def deterministic_query_candidate_split(
    movies: Iterable[MovieRecord],
    query_ratio: float = 0.2,
) -> Tuple[List[str], List[str]]:
    """
    Deterministic split based on movie ID hash for reproducibility.
    """
    query_ids: List[str] = []
    candidate_ids: List[str] = []

    for movie in movies:
        digest = hashlib.md5(movie.id.encode("utf-8")).hexdigest()
        bucket = int(digest[:8], 16) / 0xFFFFFFFF
        if bucket < query_ratio:
            query_ids.append(movie.id)
        else:
            candidate_ids.append(movie.id)

    if not query_ids and candidate_ids:
        query_ids.append(candidate_ids.pop(0))
    if not candidate_ids and query_ids:
        candidate_ids.append(query_ids.pop(0))

    return query_ids, candidate_ids
