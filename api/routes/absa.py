"""
Aspect-Based Sentiment Analysis API.

POST /absa/analyze: analyze movie reviews for aspect-level sentiment.
"""

from pathlib import Path
from uuid import UUID

import torch
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from sqlalchemy.orm import Session, joinedload
from transformers import AutoTokenizer

from api.dependencies import get_db
from api.schemas import AbsaAnalyzeRequest, AbsaAnalyzeResponse, AbsaAspectItem
from etl_pipeline.db_postgres import CoreMovie
from etl_pipeline.embedder import preprocess_text

router = APIRouter(prefix="/absa", tags=["ABSA"])

# Path from project root so it works regardless of CWD when uvicorn runs
_project_root = Path(__file__).resolve().parent.parent.parent
_absa_notebook_artifact_dir = _project_root / "Notebook_Report" / "absa" / "artifacts" / "absa_bert_tiny_latest"
_model_tokenizer_schema = None


def _get_absa_model():
    """Lazy-load ABSA model/tokenizer from Notebook_Report artifact."""
    global _model_tokenizer_schema
    if _model_tokenizer_schema is not None:
        return _model_tokenizer_schema

    try:
        from training.models.absa_model import (
            AbsaClassifier,
            load_absa_artifact,
            predict_aspects,
        )

        model = None
        tokenizer = None
        schema = {}

        if (_absa_notebook_artifact_dir / "model.pt").exists() and (_absa_notebook_artifact_dir / "tokenizer").exists():
            ckpt_path = _absa_notebook_artifact_dir / "model.pt"
            ckpt = torch.load(ckpt_path, map_location="cpu")
            model_name = ckpt.get("model_name", "prajjwal1/bert-tiny")
            state_dict = ckpt.get("state_dict", ckpt)

            model = AbsaClassifier(model_name)
            model.load_state_dict(state_dict, strict=False)
            tokenizer = AutoTokenizer.from_pretrained(str(_absa_notebook_artifact_dir / "tokenizer"))
            schema = {
                "aspects": ckpt.get("aspects", []),
                "sentiments": ckpt.get("sentiments", []),
                "source": "Notebook_Report",
            }
            logger.info("Loaded ABSA artifact from {}", _absa_notebook_artifact_dir)
        if model is None or tokenizer is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "ABSA model not available. "
                    "Expected Notebook_Report/absa/artifacts/absa_bert_tiny_latest/."
                ),
            )

        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
        model.eval()
        _model_tokenizer_schema = (model, tokenizer, schema, device, predict_aspects)
        return _model_tokenizer_schema
    except Exception as e:
        logger.exception("ABSA model load failed: %s", e)
        raise HTTPException(status_code=503, detail=f"ABSA model load failed: {str(e)}") from e


@router.post("/analyze", response_model=AbsaAnalyzeResponse)
async def analyze_absa(
    request: AbsaAnalyzeRequest,
    db: Session = Depends(get_db),
) -> AbsaAnalyzeResponse:
    """
    Analyze aspect-based sentiment for a movie (by ID) or raw review text.

    Returns a list of {aspect, sentiment, score} for each detected aspect.
    """
    if not request.movie_id and not request.text:
        raise HTTPException(
            status_code=400,
            detail="Provide at least one of 'movie_id' or 'text'",
        )

    model, tokenizer, schema, device, predict_aspects = _get_absa_model()

    texts_to_analyze: list[str] = []
    movie_id: str | None = request.movie_id
    if request.text:
        cleaned = preprocess_text(request.text)
        if cleaned:
            texts_to_analyze.append(cleaned)
    if request.movie_id and not texts_to_analyze:
        try:
            uuid = UUID(request.movie_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid movie_id format")
        movie = (
            db.query(CoreMovie)
            .options(joinedload(CoreMovie.reviews))
            .filter(CoreMovie.id == uuid)
            .first()
        )
        if not movie:
            raise HTTPException(status_code=404, detail="Movie not found")
        for review in movie.reviews[:5]:
            raw = (review.content or "").strip()
            if not raw:
                continue
            cleaned = preprocess_text(raw)
            if cleaned and len(cleaned) >= 20:
                texts_to_analyze.append(cleaned)
        if not texts_to_analyze:
            return AbsaAnalyzeResponse(
                movie_id=request.movie_id,
                text=None,
                aspects=[],
            )

    if not texts_to_analyze:
        return AbsaAnalyzeResponse(
            movie_id=movie_id,
            text=request.text,
            aspects=[],
        )

    try:
        results = predict_aspects(model, tokenizer, texts_to_analyze, device)
    except Exception as e:
        logger.exception("ABSA inference failed: %s", e)
        raise HTTPException(status_code=500, detail=f"Inference failed: {str(e)}") from e

    # Aggregate: merge aspect-sentiment from all chunks, keep max score per (aspect, sentiment)
    merged: dict[tuple[str, str], float] = {}
    for per_text in results:
        for item in per_text:
            key = (item["aspect"], item["sentiment"])
            merged[key] = max(merged.get(key, 0), item["score"])
    aspects = [
        AbsaAspectItem(aspect=a, sentiment=s, score=round(score, 4))
        for (a, s), score in sorted(merged.items(), key=lambda x: -x[1])
    ]

    return AbsaAnalyzeResponse(
        movie_id=movie_id or request.movie_id,
        text=request.text if request.text else None,
        aspects=aspects,
    )
