from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List, Set

from training.evaluation.metrics import aggregate_retrieval_metrics


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as fp:
        return json.load(fp)


def _build_gold_relevance(movie_index: List[dict]) -> Dict[str, Set[str]]:
    """
    Build weak supervision relevance by shared genre overlap.

    This gives a stable offline metric before manually curated labels exist.
    """
    by_id = {item["id"]: item for item in movie_index}
    gold: Dict[str, Set[str]] = {}
    for movie_id, item in by_id.items():
        target_genres = set(item.get("genres", []))
        if not target_genres:
            gold[movie_id] = set()
            continue
        relevant = {
            other_id
            for other_id, other in by_id.items()
            if other_id != movie_id and target_genres.intersection(other.get("genres", []))
        }
        gold[movie_id] = relevant
    return gold


def evaluate_artifact(artifact_dir: Path) -> dict:
    similar_path = artifact_dir / "similar_by_movie.json"
    index_path = artifact_dir / "movie_index.json"
    metadata_path = artifact_dir / "metadata.json"

    if not similar_path.exists() or not index_path.exists():
        raise FileNotFoundError(
            f"Missing artifact files in {artifact_dir}. "
            "Expected movie_index.json and similar_by_movie.json."
        )

    similar_by_movie = _load_json(similar_path)
    movie_index = _load_json(index_path)
    metadata = _load_json(metadata_path) if metadata_path.exists() else {}

    recommendations: Dict[str, List[str]] = {
        movie_id: [item["movie_id"] for item in rows]
        for movie_id, rows in similar_by_movie.items()
    }
    gold = _build_gold_relevance(movie_index)
    metrics = aggregate_retrieval_metrics(recommendations, gold, k_values=(5, 10))

    return {
        "artifact_dir": str(artifact_dir),
        "artifact_metadata": metadata,
        "query_count": len(recommendations),
        "metrics": metrics,
        "evaluation_label_source": "weak-supervision-shared-genres",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate recommendation artifact.")
    parser.add_argument(
        "--artifact-dir",
        required=True,
        help="Path to artifact directory (contains movie_index + similar_by_movie).",
    )
    parser.add_argument(
        "--output-json",
        default="",
        help="Optional output JSON path for metrics.",
    )
    args = parser.parse_args()

    result = evaluate_artifact(Path(args.artifact_dir))
    serialized = json.dumps(result, indent=2, ensure_ascii=False)
    print(serialized)

    if args.output_json:
        output = Path(args.output_json)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(serialized + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
