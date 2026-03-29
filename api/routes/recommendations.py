from __future__ import annotations

import re
from fastapi import APIRouter, HTTPException, Query

from api.recommender import get_recommendation_store, reload_recommendation_store
from api.schemas import (
    SimilarMoviesResponse,
    RecommendationSearchRequest,
    RecommendationSearchResponse,
    BaselineCosineRequest,
    BaselineCosineResponse,
    TrendingRecommendationsResponse,
    RecommendationItem,
    RecommendationSearchDebug,
    EngineSearchBlock,
)


router = APIRouter(tags=["Recommendations"])


def _norm_tokens(s: str) -> list[str]:
    return [t for t in re.sub(r"[^a-zA-Z0-9\s]+", " ", str(s).lower()).split() if t]


def _model_name() -> str:
    store = get_recommendation_store()
    return store.metadata.get("artifact_type", "artifact-not-loaded")


def _effective_engines(payload: RecommendationSearchRequest) -> list[str]:
    if payload.engines is not None:
        return list(dict.fromkeys(payload.engines))
    if payload.engine is not None:
        return [payload.engine]
    return ["artifact"]


def _requires_artifact_store(engines: list[str]) -> bool:
    return "artifact" in engines or "hybrid" in engines


BASELINE_ENGINE_TO_KIND: dict[str, str] = {
    "baseline_sbert": "sbert",
    "baseline_tfidf": "tfidf",
    "baseline_word2vec": "word2vec",
}


def _search_baseline_block(payload: RecommendationSearchRequest, engine_id: str) -> EngineSearchBlock:
    from api.baseline_cosine import baseline_cosine_rank

    kind = BASELINE_ENGINE_TO_KIND[engine_id]
    try:
        rows, model_label, _artifact_ver = baseline_cosine_rank(kind, payload.query, payload.limit)
    except FileNotFoundError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ImportError as e:
        raise HTTPException(status_code=503, detail=f"Thiếu dependency: {e}") from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except ValueError as e:
        raise HTTPException(status_code=500, detail=str(e)) from e

    debug_obj = None
    if payload.debug:
        qlow = payload.query.strip().lower()
        notes = [
            "Baseline: embed câu query vào đúng không gian vector của mô hình (TF‑IDF sparse, SBERT dense, Word2Vec dense), "
            "rồi cosine similarity với từng vector phim trong artifact notebook 03 — không BM25/ABSA/rerank.",
        ]
        debug_obj = RecommendationSearchDebug(
            query_raw=payload.query,
            query_normalized=qlow,
            tokens=_norm_tokens(qlow),
            query_type_requested="baseline_cosine",
            weights={"title": 0.0, "genre": 0.0, "semantic": 1.0},
            filters=payload.filters.model_dump(exclude_none=True) if payload.filters else {},
            absa_refine=False,
            absa_intents=[],
            semantic_ready=True,
            semantic_backend_requested=kind,
            semantic_model_resolved=model_label,
            absa_profile_ready=False,
            personalization={"note": "Baseline không dùng lịch sử artifact."},
            rerank={"enabled": False, "model": None, "note": "Baseline: không Cross-Encoder."},
            engine=engine_id,  # type: ignore[arg-type]
            hybrid_notes=notes,
        )

    results = [RecommendationItem(**item) for item in rows]
    return EngineSearchBlock(
        engine=engine_id,  # type: ignore[arg-type]
        total_results=len(results),
        model=model_label,
        results=results,
        debug=debug_obj,
    )


def _search_payload_with_effective_query(
    payload: RecommendationSearchRequest,
) -> tuple[RecommendationSearchRequest, str, bool]:
    """(payload cho engine, query_effective, đã sửa chính tả hay không)."""
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


def _search_hybrid_block(payload: RecommendationSearchRequest) -> EngineSearchBlock:
    from api.hybrid_service import get_hybrid_pipeline, hybrid_df_to_api_items

    store = get_recommendation_store()
    try:
        pipe = get_hybrid_pipeline()
        df = pipe.search(payload.query, limit=payload.limit)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Hybrid search data missing: {e}. Set HYBRID_CLEANED_CSV or ensure Notebook_Report/cleaned_profiles.csv exists.",
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Hybrid pipeline failed: {e!s}",
        ) from e

    rows, join_notes = hybrid_df_to_api_items(
        store.movie_index,
        df,
        explain=payload.explain,
    )
    debug_obj = None
    if payload.debug:
        hybrid_notes = [
            "Engine hybrid: bỏ qua filters, user_history, rerank và weights_override của luồng artifact (phase 1).",
        ]
        if join_notes:
            capped = join_notes[:20]
            hybrid_notes.extend(capped)
            if len(join_notes) > 20:
                hybrid_notes.append(f"… và {len(join_notes) - 20} tmdb_id không có trong movie_index")
        qlow = payload.query.strip().lower()
        debug_obj = RecommendationSearchDebug(
            query_raw=payload.query,
            query_normalized=qlow,
            tokens=_norm_tokens(qlow),
            query_type_requested="hybrid",
            weights={},
            filters=payload.filters.model_dump(exclude_none=True) if payload.filters else {},
            absa_refine=payload.absa_refine,
            absa_intents=[],
            semantic_ready=True,
            semantic_backend_requested=None,
            semantic_model_resolved=None,
            absa_profile_ready=True,
            personalization={
                "history_count": len(payload.user_history or []),
                "user_vec_ready": False,
                "note": "Hybrid: không dùng lịch sử tìm kiếm artifact.",
            },
            rerank={
                "enabled": False,
                "model": None,
                "note": "Hybrid: Cross-Encoder rerank không áp dụng.",
            },
            engine="hybrid",
            hybrid_notes=hybrid_notes,
        )
    sbert_short = pipe.config.sbert_model.split("/")[-1]
    model_label = f"hybrid:{sbert_short}"
    results = [RecommendationItem(**item) for item in rows]
    return EngineSearchBlock(
        engine="hybrid",
        total_results=len(results),
        model=model_label,
        results=results,
        debug=debug_obj,
    )


def _search_artifact_block(payload: RecommendationSearchRequest) -> EngineSearchBlock:
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
                weights_override=payload.weights_override.model_dump(exclude_none=True) if payload.weights_override else None,
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
                weights_override=payload.weights_override.model_dump(exclude_none=True) if payload.weights_override else None,
                semantic_backend=sb,
            )
            artifact_model = str(semantic_label)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    results = [RecommendationItem(**item) for item in rows]
    return EngineSearchBlock(
        engine="artifact",
        total_results=len(results),
        model=f"artifact:{artifact_model}",
        results=results,
        debug=debug_obj,
    )


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
    search_payload, query_effective, autocorrect_applied = _search_payload_with_effective_query(payload)
    engines = _effective_engines(search_payload)
    if _requires_artifact_store(engines):
        store = get_recommendation_store()
        if not store.is_ready():
            raise HTTPException(
                status_code=503,
                detail="Recommendation artifacts not ready. Train models under training/ first.",
            )

    blocks: list[EngineSearchBlock] = []
    for eng in engines:
        if eng == "hybrid":
            blocks.append(_search_hybrid_block(search_payload))
        elif eng in BASELINE_ENGINE_TO_KIND:
            blocks.append(_search_baseline_block(search_payload, eng))
        else:
            blocks.append(_search_artifact_block(search_payload))

    first = blocks[0]
    combined_model = " + ".join(b.model for b in blocks)

    if len(blocks) == 1:
        return RecommendationSearchResponse(
            query=payload.query,
            query_effective=query_effective,
            autocorrect_applied=autocorrect_applied,
            engines_used=engines,
            total_results=first.total_results,
            model=first.model,
            debug=first.debug,
            results=first.results,
            by_engine=None,
        )

    return RecommendationSearchResponse(
        query=payload.query,
        query_effective=query_effective,
        autocorrect_applied=autocorrect_applied,
        engines_used=engines,
        total_results=first.total_results,
        model=combined_model,
        debug=first.debug,
        results=first.results,
        by_engine=blocks,
    )


@router.post("/recommendations/baseline-cosine", response_model=BaselineCosineResponse)
async def baseline_cosine_search(payload: BaselineCosineRequest) -> BaselineCosineResponse:
    """
    Embed câu query, cosine với toàn bộ vector đã lưu trong artifact baseline (SBERT / TF-IDF / Word2Vec).
    Không dùng pipeline Artifact (BM25, ABSA, rerank) hay Hybrid.
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
            detail="Recommendation artifacts not ready. Train models under training/ first.",
        )
    rows = store.trending_movies(limit=limit)
    results = [RecommendationItem(**item) for item in rows]
    return TrendingRecommendationsResponse(
        total_results=len(results),
        model=_model_name(),
        results=results,
    )
