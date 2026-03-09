from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from api.recommender import get_recommendation_store, reload_recommendation_store
from api.schemas import (
    SimilarMoviesResponse,
    RecommendationSearchRequest,
    RecommendationSearchResponse,
    TrendingRecommendationsResponse,
    RecommendationItem,
)


router = APIRouter(tags=["Recommendations"])


def _model_name() -> str:
    store = get_recommendation_store()
    return store.metadata.get("artifact_type", "artifact-not-loaded")


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
            detail="Recommendation artifacts not ready. Train models under training/ first.",
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
    store = get_recommendation_store()
    if not store.is_ready():
        raise HTTPException(
            status_code=503,
            detail="Recommendation artifacts not ready. Train models under training/ first.",
        )
    rows = store.search_movies(payload.query, limit=payload.limit)
    results = [RecommendationItem(**item) for item in rows]
    return RecommendationSearchResponse(
        query=payload.query,
        total_results=len(results),
        model=_model_name(),
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
            detail="Recommendation artifacts not ready. Train models under training/ first.",
        )
    rows = store.trending_movies(limit=limit)
    results = [RecommendationItem(**item) for item in rows]
    return TrendingRecommendationsResponse(
        total_results=len(results),
        model=_model_name(),
        results=results,
    )
