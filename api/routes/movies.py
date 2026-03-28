"""
CineSense API - Movies Routes
=============================

Discovery-only movie endpoints backed by the English-first core schema.
"""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from api.dependencies import get_db
from api.schemas import (
    MovieSchema,
    MovieDetailSchema,
    MovieListResponse,
    ReviewSchema,
    GenreSchema,
)
from etl_pipeline.database import CoreMovie, CoreReview, CoreGenre


router = APIRouter(prefix="/movies", tags=["Movies"])


@router.get("", response_model=MovieListResponse)
async def list_movies(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    db: Session = Depends(get_db),
) -> MovieListResponse:
    """
    List all movies from the English-first core catalog.
    """
    query = db.query(CoreMovie).options(
        joinedload(CoreMovie.genres),
        joinedload(CoreMovie.reviews),
    )

    total = query.count()
    offset = (page - 1) * page_size
    movies = (
        query
        .order_by(CoreMovie.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )

    movie_schemas = []
    for movie in movies:
        ratings = [review.rating for review in movie.reviews if review.rating is not None]
        movie_schemas.append(MovieSchema(
            id=str(movie.id),
            tmdb_id=movie.tmdb_id,
            title=movie.title,
            overview=movie.overview,
            release_date=movie.release_date,
            poster_path=movie.poster_path,
            genres=[GenreSchema(id=g.id, name=g.name) for g in movie.genres],
            review_count=len(movie.reviews),
            average_rating=(sum(ratings) / len(ratings)) if ratings else None,
        ))

    return MovieListResponse(
        total=total,
        page=page,
        page_size=page_size,
        movies=movie_schemas
    )


@router.get("/{movie_id}", response_model=MovieDetailSchema)
async def get_movie(
    movie_id: str,
    db: Session = Depends(get_db),
) -> MovieDetailSchema:
    """
    Get movie details by ID.
    
    Returns movie metadata with all reviews.
    """
    try:
        uuid = UUID(movie_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid movie ID format")
    
    movie = db.query(CoreMovie).options(
        joinedload(CoreMovie.genres),
        joinedload(CoreMovie.reviews),
    ).filter(CoreMovie.id == uuid).first()

    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")

    ratings = [review.rating for review in movie.reviews if review.rating is not None]
    return MovieDetailSchema(
        id=str(movie.id),
        tmdb_id=movie.tmdb_id,
        title=movie.title,
        overview=movie.overview,
        release_date=movie.release_date,
        poster_path=movie.poster_path,
        genres=[GenreSchema(id=g.id, name=g.name) for g in movie.genres],
        reviews=[
            ReviewSchema(
                id=str(r.id),
                content=r.content,
                source=r.source,
                rating=r.rating,
                user=None,
                author_name=r.author_name or r.author_username or r.source,
                author_avatar_url=r.author_avatar_url,
                likes_count=0,
                created_at=r.created_at
            ) for r in sorted(movie.reviews, key=lambda x: x.created_at, reverse=True)
        ],
        review_count=len(movie.reviews),
        average_rating=(sum(ratings) / len(ratings)) if ratings else None,
    )

@router.get("/genres/list", response_model=List[GenreSchema])
async def list_genres(
    db: Session = Depends(get_db),
) -> List[GenreSchema]:
    """
    List all available genres.
    """
    genres = db.query(CoreGenre).order_by(CoreGenre.name).all()
    return [GenreSchema(id=g.id, name=g.name) for g in genres]
