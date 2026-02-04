"""
CineSense API - Movies Routes
=============================

CRUD endpoints for movie data.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from api.dependencies import get_db
from api.schemas import (
    MovieSchema,
    MovieDetailSchema,
    MovieListResponse,
    ReviewSchema,
    GenreSchema,
)
from etl_pipeline.db_postgres import Movie, Review, Genre


router = APIRouter(prefix="/movies", tags=["Movies"])


@router.get("", response_model=MovieListResponse)
async def list_movies(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    genre: Optional[str] = Query(default=None, description="Filter by genre name"),
    year: Optional[int] = Query(default=None, description="Filter by release year"),
    search: Optional[str] = Query(default=None, description="Search title (simple text match)"),
    db: Session = Depends(get_db),
) -> MovieListResponse:
    """
    List movies with pagination and filters.
    
    This is a simple list endpoint for browsing movies.
    For semantic "vibe" search, use POST /search instead.
    """
    # Base query with eager loading of genres
    query = db.query(Movie).options(joinedload(Movie.genres))
    
    # Apply filters
    if genre:
        query = query.join(Movie.genres).filter(Genre.name.ilike(f"%{genre}%"))
    
    if year:
        query = query.filter(
            func.extract('year', Movie.release_date) == year
        )
    
    if search:
        query = query.filter(Movie.title.ilike(f"%{search}%"))
    
    # Get total count
    total = query.distinct().count()
    
    # Apply pagination
    offset = (page - 1) * page_size
    movies = query.distinct().order_by(Movie.created_at.desc()).offset(offset).limit(page_size).all()
    
    # Convert to schema
    movie_schemas = []
    for movie in movies:
        movie_schemas.append(MovieSchema(
            id=str(movie.id),
            tmdb_id=movie.tmdb_id,
            title=movie.title,
            overview=movie.overview,
            release_date=movie.release_date,
            poster_path=movie.poster_path,
            genres=[GenreSchema(id=g.id, name=g.name) for g in movie.genres],
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
    
    # Query movie with reviews and genres
    movie = db.query(Movie).options(
        joinedload(Movie.genres),
        joinedload(Movie.reviews)
    ).filter(Movie.id == uuid).first()
    
    if not movie:
        raise HTTPException(status_code=404, detail="Movie not found")
    
    # Convert to schema
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
                user=r.user.nickname if r.user else None,
                author_name=r.author_name if r.author_name else (r.user.nickname if r.user else r.source),
                author_avatar_url=r.author_avatar_url or (r.user.avatar_url if r.user else None),
                likes_count=r.likes_count,
                created_at=r.created_at
            ) for r in sorted(movie.reviews, key=lambda x: x.created_at, reverse=True)
        ],
        review_count=len(movie.reviews)
    )

@router.get("/genres/list", response_model=List[GenreSchema])
async def list_genres(
    db: Session = Depends(get_db),
) -> List[GenreSchema]:
    """
    List all available genres.
    """
    genres = db.query(Genre).order_by(Genre.name).all()
    return [GenreSchema(id=g.id, name=g.name) for g in genres]
