"""
CineSense API - Search Routes
=============================

Semantic search endpoint for "vibe-based" movie discovery.

Flow:
1. Receive query string (any language)
2. Embed query → 384-dim vector
3. Search Qdrant for similar review vectors
4. Enrich with movie metadata from PostgreSQL
5. Return ranked results with matched reviews
"""

from typing import Dict, List, Optional, Set
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from sqlalchemy.orm import Session

from api.dependencies import get_db, get_qdrant
from api.schemas import SearchRequest, SearchResponse, SearchResultItem
from etl_pipeline.config import settings
from etl_pipeline.db_postgres import Movie, Genre
from etl_pipeline.embedder import embed_text, preprocess_text


router = APIRouter(prefix="/search", tags=["Search"])


def build_qdrant_filter(
    min_year: Optional[int] = None,
    max_year: Optional[int] = None,
    genres: Optional[List[str]] = None,
    min_rating: Optional[float] = None,
) -> Optional[qdrant_models.Filter]:
    """
    Build Qdrant filter conditions from search parameters.
    
    Args:
        min_year: Minimum release year
        max_year: Maximum release year
        genres: List of genre names to filter
        min_rating: Minimum rating threshold
        
    Returns:
        Qdrant Filter object or None if no filters
    """
    conditions = []
    
    if min_year is not None:
        conditions.append(
            qdrant_models.FieldCondition(
                key="year",
                range=qdrant_models.Range(gte=min_year)
            )
        )
    
    if max_year is not None:
        conditions.append(
            qdrant_models.FieldCondition(
                key="year",
                range=qdrant_models.Range(lte=max_year)
            )
        )
    
    if min_rating is not None:
        conditions.append(
            qdrant_models.FieldCondition(
                key="rating",
                range=qdrant_models.Range(gte=min_rating)
            )
        )
    
    # Note: Genre filtering would require genre_ids in payload
    # For now, we'll do post-filtering in Python
    
    if not conditions:
        return None
    
    return qdrant_models.Filter(must=conditions)


@router.post("", response_model=SearchResponse)
async def semantic_search(
    request: SearchRequest,
    db: Session = Depends(get_db),
    qdrant: QdrantClient = Depends(get_qdrant),
) -> SearchResponse:
    """
    Semantic search for movies by "vibe".
    
    Accepts natural language queries in any language and returns
    movies whose reviews semantically match the query.
    
    Examples:
    - "phim buồn cho ngày mưa" → sad/melancholic movies
    - "feel good movies with happy endings" → uplifting movies
    - "scary horror movies" → horror films
    
    The multilingual embedding model understands that
    "phim kinh dị" ≈ "horror movie".
    """
    logger.info(f"Search query: '{request.query}'")
    
    try:
        # Step 1: Preprocess and embed query
        clean_query = preprocess_text(request.query)
        query_vector = embed_text(clean_query, preprocess=False)
        
        # Step 2: Build filter
        qdrant_filter = build_qdrant_filter(
            min_year=request.min_year,
            max_year=request.max_year,
            min_rating=request.min_rating,
        )
        
        # Step 3: Search Qdrant
        # Request more results than limit to allow for deduplication
        search_results = qdrant.query_points(
            collection_name=settings.qdrant.collection_name,
            query=query_vector,
            limit=request.limit * 3,  # Get extra for deduplication
            score_threshold=0.3,  # Minimum similarity
            query_filter=qdrant_filter,
        ).points
        
        if not search_results:
            return SearchResponse(
                query=request.query,
                total_results=0,
                results=[]
            )
        
        # Step 4: Deduplicate by movie_id (keep highest score per movie)
        movie_scores: Dict[str, tuple] = {}  # movie_id -> (score, review, payload)
        
        for result in search_results:
            movie_id = result.payload.get("movie_id")
            if movie_id not in movie_scores or result.score > movie_scores[movie_id][0]:
                movie_scores[movie_id] = (
                    result.score,
                    result.payload.get("movie_title", "Unknown"),
                    result.payload,
                )
        
        # Step 5: Get movie details from PostgreSQL
        movie_ids = list(movie_scores.keys())[:request.limit]
        movies = db.query(Movie).filter(
            Movie.id.in_([UUID(mid) for mid in movie_ids])
        ).all()
        
        # Create lookup dict
        movie_lookup = {str(m.id): m for m in movies}
        
        # Step 6: Build response
        results = []
        for movie_id in movie_ids:
            score, title, payload = movie_scores[movie_id]
            movie = movie_lookup.get(movie_id)
            
            if movie:
                # Get genre names
                genre_names = [g.name for g in movie.genres]
                
                # Apply genre filter if specified
                if request.genres:
                    if not any(g in genre_names for g in request.genres):
                        continue
                
                results.append(SearchResultItem(
                    movie_id=movie_id,
                    title=movie.title,
                    score=round(score, 4),
                    year=movie.release_date.year if movie.release_date else None,
                    poster_path=movie.poster_path,
                    overview=movie.overview[:200] + "..." if movie.overview and len(movie.overview) > 200 else movie.overview,
                    matched_review="",  # We don't store review text in Qdrant payload currently
                    genres=genre_names,
                ))
        
        # Sort by score (descending)
        results.sort(key=lambda x: x.score, reverse=True)
        results = results[:request.limit]
        
        logger.info(f"Search returned {len(results)} results")
        
        return SearchResponse(
            query=request.query,
            total_results=len(results),
            results=results
        )
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")
