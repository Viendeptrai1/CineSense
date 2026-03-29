from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.recommender import get_recommendation_store, reload_recommendation_store
from api.schemas import (
    BaselineCosineRequest,
    BaselineCosineResponse,
    RecommendationItem,
    RecommendationSearchDebug,
    RecommendationSearchRequest,
    RecommendationSearchResponse,
    SimilarMoviesResponse,
    TrendingRecommendationsResponse,
)


router = APIRouter(tags=["Recommendations"])


def _model_name() -> str:
    store = get_recommendation_store()
    return (
        store.metadata.get("artifact_version")
        or store.metadata.get("artifact_type")
        or "artifact-not-loaded"
    )


def _search_payload_with_effective_query(
    payload: RecommendationSearchRequest,
) -> tuple[RecommendationSearchRequest, str, bool]:
    """Return (payload for search, effective query, autocorrect applied)."""
    if not payload.autocorrect:
        return payload, payload.query, False

    from api.query_spelling import apply_autocorrect_english

    q, changed = apply_autocorrect_english(payload.query)
    q2 = (q or "").strip()
    if len(q2) < 2:
        return payload, payload.query, False
    if not changed:
        return payload, q2, False
    return payload.model_copy(update={"query": q2}), q2, True


def _search_artifact(
    payload: RecommendationSearchRequest,
) -> tuple[list[RecommendationItem], str, RecommendationSearchDebug | None]:
    store = get_recommendation_store()
    debug_obj = None
    sb = payload.semantic_backend or "auto"

    try:
        if payload.debug:
            rows, debug = store.search_movies_with_debug(
                payload.query,
                limit=payload.limit,
                query_type=payload.query_type or "auto",
                filters=payload.filters.model_dump(exclude_none=True) if payload.filters else None,
                absa_refine=payload.absa_refine,
                explain=payload.explain,
                user_history=payload.user_history,
                rerank=payload.rerank,
                weights_override=payload.weights_override.model_dump(exclude_none=True)
                if payload.weights_override
                else None,
                semantic_backend=sb,
            )
            artifact_model = _model_name()
            if debug:
                d = dict(debug)
                d["engine"] = "artifact"
                debug_obj = RecommendationSearchDebug(**d)
                artifact_model = str(debug.get("semantic_model_resolved") or artifact_model)
        else:
            rows, semantic_label = store.search_movies(
                payload.query,
                limit=payload.limit,
                query_type=payload.query_type or "auto",
                filters=payload.filters.model_dump(exclude_none=True) if payload.filters else None,
                absa_refine=payload.absa_refine,
                explain=payload.explain,
                user_history=payload.user_history,
                rerank=payload.rerank,
                weights_override=payload.weights_override.model_dump(exclude_none=True)
                if payload.weights_override
                else None,
                semantic_backend=sb,
            )
            artifact_model = str(semantic_label)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    results = [RecommendationItem(**item) for item in rows]
    return results, f"artifact:{artifact_model}", debug_obj


@router.post("/recommendations/reload", summary="Reload recommendation artifacts")
async def reload_recommendations() -> dict:
    store = reload_recommendation_store()
    return {
        "ready": store.is_ready(),
        "artifact_dir": str(store.artifact_dir),
        "model": _model_name(),
    }


@router.get("/movies/{movie_id}/similar", response_model=SimilarMoviesResponse)
async def get_similar_movies(
    movie_id: str,
    limit: int = Query(default=10, ge=1, le=50),
) -> SimilarMoviesResponse:
    store = get_recommendation_store()
    if not store.is_ready():
        raise HTTPException(
            status_code=503,
            detail="Recommendation artifacts not ready. Train/export notebook artifacts first.",
        )
    if movie_id not in store.movie_index:
        raise HTTPException(status_code=404, detail="Movie not found in recommendation index")

    results = [RecommendationItem(**item) for item in store.similar_movies(movie_id, limit=limit)]
    return SimilarMoviesResponse(
        source_movie_id=movie_id,
        total_results=len(results),
        model=_model_name(),
        results=results,
    )


@router.post("/recommendations/search", response_model=RecommendationSearchResponse)
async def search_recommendations(payload: RecommendationSearchRequest) -> RecommendationSearchResponse:
    search_payload, query_effective, autocorrect_applied = _search_payload_with_effective_query(payload)
    store = get_recommendation_store()
    if not store.is_ready():
        raise HTTPException(
            status_code=503,
            detail="Recommendation artifacts not ready. Train/export notebook artifacts first.",
        )

    results, model_label, debug_obj = _search_artifact(search_payload)
    return RecommendationSearchResponse(
        query=payload.query,
        query_effective=query_effective,
        autocorrect_applied=autocorrect_applied,
        engines_used=["artifact"],
        total_results=len(results),
        model=model_label,
        debug=debug_obj,
        results=results,
    )


@router.post("/recommendations/baseline-cosine", response_model=BaselineCosineResponse)
async def baseline_cosine_search(payload: BaselineCosineRequest) -> BaselineCosineResponse:
    """
    Embed câu query, cosine với toàn bộ vector đã lưu trong artifact baseline
    (SBERT gốc / SBERT English fine-tuned / TF-IDF / Word2Vec).
    Endpoint này chỉ phục vụ so sánh/evaluation, không phải luồng runtime chính của web demo.
    """
    from api.baseline_cosine import baseline_cosine_rank

    try:
        rows, model_label, artifact_ver = baseline_cosine_rank(
            payload.baseline, payload.query, payload.limit
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"Thiếu dependency: {e}") from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    results = [RecommendationItem(**item) for item in rows]
    return BaselineCosineResponse(
        query=payload.query,
        baseline=payload.baseline,
        model=model_label,
        artifact_version=artifact_ver,
        total_results=len(results),
        results=results,
    )


@router.get("/recommendations/trending", response_model=TrendingRecommendationsResponse)
async def get_trending_recommendations(
    limit: int = Query(default=10, ge=1, le=50),
) -> TrendingRecommendationsResponse:
    store = get_recommendation_store()
    if not store.is_ready():
        raise HTTPException(
            status_code=503,
            detail="Recommendation artifacts not ready. Train/export notebook artifacts first.",
        )
    rows = store.trending_movies(limit=limit)
    results = [RecommendationItem(**item) for item in rows]
    return TrendingRecommendationsResponse(
        total_results=len(results),
        model=_model_name(),
        results=results,
    )
