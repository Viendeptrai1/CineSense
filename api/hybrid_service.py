"""
Lazy-loaded MultiFieldMoviePipeline for POST /recommendations/search? engine=hybrid.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from api.hybrid_search import MultiFieldMoviePipeline, PipelineConfig

_project_root = Path(__file__).resolve().parents[1]
_pipeline: MultiFieldMoviePipeline | None = None


def default_notebook_dir() -> Path:
    return _project_root / "Notebook_Report"


def _resolve_hybrid_csv() -> tuple[Path, str]:
    """Return (data_dir, cleaned_csv filename relative to data_dir)."""
    default_dir = default_notebook_dir()
    env_csv = os.getenv("HYBRID_CLEANED_CSV", "").strip()
    if env_csv:
        p = Path(env_csv).expanduser()
        if p.is_file():
            return p.parent.resolve(), p.name
        if p.is_dir():
            return p.resolve(), "cleaned_profiles.csv"
    env_dir = os.getenv("HYBRID_DATA_DIR", "").strip()
    if env_dir:
        d = Path(env_dir).expanduser().resolve()
        fname = (
            os.getenv("HYBRID_CLEANED_BASENAME", "cleaned_profiles.csv").strip()
            or "cleaned_profiles.csv"
        )
        return d, fname
    return default_dir.resolve(), "cleaned_profiles.csv"


def _absa_artifact_rel_path() -> str:
    name = (
        os.getenv("ABSA_ARTIFACT_NAME", "absa_distilroberta_latest").strip()
        or "absa_distilroberta_latest"
    )
    return f"absa/artifacts/{name}"


def build_hybrid_pipeline_config() -> PipelineConfig:
    data_dir, cleaned_csv = _resolve_hybrid_csv()
    return PipelineConfig(
        data_dir=data_dir,
        cleaned_csv=cleaned_csv,
        absa_artifact_dir=_absa_artifact_rel_path(),
        sbert_show_progress=False,
    )


def get_hybrid_pipeline(*, refit: bool = False) -> MultiFieldMoviePipeline:
    """Return a fitted pipeline; first call runs SBERT encode (slow)."""
    global _pipeline
    if _pipeline is None or refit:
        _pipeline = MultiFieldMoviePipeline(build_hybrid_pipeline_config())
        _pipeline.fit()
    return _pipeline


def invalidate_hybrid_pipeline() -> None:
    """Clear cached pipeline (e.g. after POST /recommendations/reload)."""
    global _pipeline
    _pipeline = None


def build_tmdb_index(movie_index: dict[str, dict]) -> dict[str, dict]:
    """Map TMDB id string → movie_index row (UUID id, poster, …)."""
    tmdb_map: dict[str, dict] = {}
    for row in movie_index.values():
        tid = row.get("tmdb_id")
        if tid is None:
            continue
        try:
            key = str(int(tid))
        except (TypeError, ValueError):
            key = str(tid).strip()
        tmdb_map[key] = row
    return tmdb_map


def hybrid_df_to_api_items(
    movie_index: dict[str, dict],
    df: Any,
    *,
    explain: bool,
) -> tuple[list[dict], list[str]]:
    """Turn pipeline DataFrame rows into recommender-style dicts; drop rows missing from index."""
    tmdb_map = build_tmdb_index(movie_index)
    notes: list[str] = []
    items: list[dict] = []
    for _, hr in df.iterrows():
        tid_raw = str(hr["tmdb_id"]).strip()
        try:
            tid_norm = str(int(float(tid_raw)))
        except (TypeError, ValueError):
            tid_norm = tid_raw
        meta = tmdb_map.get(tid_norm) or tmdb_map.get(tid_raw)
        if not meta:
            notes.append(f"missing_index_tmdb={tid_raw}")
            continue
        genres = meta.get("genres") or []
        if isinstance(genres, str):
            genres = [g.strip() for g in genres.split(",") if g.strip()]
        elif not isinstance(genres, list):
            genres = []
        item: dict = {
            "movie_id": meta["id"],
            "title": meta.get("title") or hr.get("title"),
            "overview": meta.get("overview"),
            "poster_path": meta.get("poster_path"),
            "genres": genres,
            "review_count": int(meta.get("review_count") or 0),
            "score": float(hr["score_final"]),
        }
        if explain:
            item["score_breakdown"] = {
                "title": float(hr["score_title"]),
                "genre": float(hr["score_genre"]),
                "semantic": float(hr["score_sbert"]),
                "stage2": float(hr["score_stage2"]),
                "absa_bonus": float(hr["absa_query_profile_cos"]),
                "final": float(hr["score_final"]),
            }
        items.append(item)
    return items, notes
