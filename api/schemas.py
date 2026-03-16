"""
CineSense API - Pydantic Schemas
================================

Request and response models for the API endpoints.
"""

from datetime import date
from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, EmailStr

# ... (Previous schemas) ...

# ============================================
# Auth & User Schemas
# ============================================

class UserCreate(BaseModel):
    username: str = Field(..., min_length=4, max_length=50, description="Unique username")
    nickname: str = Field(..., min_length=2, max_length=50, description="Display name")
    password: str = Field(..., min_length=4, description="Password (min 4 chars)")

class UserLogin(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class UserResponse(BaseModel):
    id: UUID
    username: str
    nickname: str
    avatar_url: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True

# ============================================
# Search Schemas
# ============================================



# ============================================
# Search Schemas
# ============================================

class SearchRequest(BaseModel):
    """Semantic search request."""
    
    query: str = Field(
        ...,
        min_length=2,
        max_length=500,
        description="Search query in any language (e.g., 'phim buồn cho ngày mưa')",
        examples=["phim kinh dị đáng sợ", "feel good movies with happy endings"]
    )
    limit: int = Field(
        default=10,
        ge=1,
        le=50,
        description="Maximum number of results"
    )
    min_year: Optional[int] = Field(
        default=None,
        ge=1900,
        le=2100,
        description="Filter: minimum release year"
    )
    max_year: Optional[int] = Field(
        default=None,
        ge=1900,
        le=2100,
        description="Filter: maximum release year"
    )
    genres: Optional[List[str]] = Field(
        default=None,
        description="Filter: list of genre names"
    )
    min_rating: Optional[float] = Field(
        default=None,
        ge=0,
        le=10,
        description="Filter: minimum rating"
    )


class SearchResultItem(BaseModel):
    """Single search result item."""
    
    movie_id: str = Field(..., description="Movie UUID")
    title: str = Field(..., description="Movie title (Vietnamese if available)")
    score: float = Field(..., description="Similarity score (0-1)")
    year: Optional[int] = Field(None, description="Release year")
    poster_path: Optional[str] = Field(None, description="TMDB poster path")
    overview: Optional[str] = Field(None, description="Movie overview")
    matched_review: str = Field(..., description="The review that matched the query")
    genres: List[str] = Field(default_factory=list, description="Genre names")
    review_count: int = Field(0, description="Total reviews")
    average_rating: Optional[float] = Field(None, description="Average rating")


class SearchResponse(BaseModel):
    """Semantic search response."""
    
    query: str = Field(..., description="Original search query")
    total_results: int = Field(..., description="Number of results returned")
    results: List[SearchResultItem] = Field(..., description="Ranked movie results")


# ============================================
# Movie Schemas
# ============================================

class ReviewSchema(BaseModel):
    """Movie review schema."""
    
    id: str
    content: str
    source: str
    rating: Optional[float] = None
    user: Optional[str] = Field(None, description="Author nickname (system user)")
    author_name: Optional[str] = Field(None, description="Real author name (external)")
    author_avatar_url: Optional[str] = Field(None, description="Author avatar URL")
    likes_count: int = 0
    created_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class GenreSchema(BaseModel):
    """Genre schema."""
    
    id: int
    name: str
    
    class Config:
        from_attributes = True


class MovieSchema(BaseModel):
    """Movie schema for list view."""
    
    id: str
    tmdb_id: Optional[int] = None
    title: str
    overview: Optional[str] = None
    release_date: Optional[date] = None
    poster_path: Optional[str] = None
    genres: List[GenreSchema] = []
    review_count: int = 0
    average_rating: Optional[float] = None
    
    class Config:
        from_attributes = True


class MovieDetailSchema(MovieSchema):
    """Movie schema with reviews for detail view."""
    
    reviews: List[ReviewSchema] = []
    review_count: int = 0


class MovieListResponse(BaseModel):
    """Paginated movie list response."""
    
    total: int
    page: int
    page_size: int
    movies: List[MovieSchema]


class RecommendationItem(BaseModel):
    movie_id: str
    title: Optional[str] = None
    overview: Optional[str] = None
    poster_path: Optional[str] = None
    genres: List[str] = []
    review_count: int = 0
    score: Optional[float] = None


class SimilarMoviesResponse(BaseModel):
    source_movie_id: str
    total_results: int
    model: str
    results: List[RecommendationItem]


class RecommendationSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=300)
    limit: int = Field(default=10, ge=1, le=50)


class RecommendationSearchResponse(BaseModel):
    query: str
    total_results: int
    model: str
    results: List[RecommendationItem]


class TrendingRecommendationsResponse(BaseModel):
    total_results: int
    model: str
    results: List[RecommendationItem]


# ============================================
# ABSA (Aspect-Based Sentiment Analysis)
# ============================================

class AbsaAnalyzeRequest(BaseModel):
    """Request for ABSA: provide movie_id and/or raw review text."""
    movie_id: Optional[str] = Field(None, description="Movie UUID; reviews will be fetched from DB")
    text: Optional[str] = Field(None, description="Raw review text to analyze")


class AbsaAspectItem(BaseModel):
    aspect: str
    sentiment: str
    score: float


class AbsaAnalyzeResponse(BaseModel):
    movie_id: Optional[str] = None
    text: Optional[str] = None
    aspects: List[AbsaAspectItem] = Field(default_factory=list)


# ============================================
# Health Check
# ============================================

class HealthResponse(BaseModel):
    """Health check response."""
    
    status: str = "healthy"
    version: str
    postgres_connected: bool
    qdrant_connected: bool
    embedding_model: str
    movies_count: int
    vectors_count: int
