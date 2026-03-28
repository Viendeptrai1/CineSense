"""
CineSense API - Pydantic Schemas
================================

Request and response models for the API endpoints.
"""

from datetime import date
from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

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
    score_breakdown: Optional[Dict[str, float]] = None


class RecommendationSearchFilters(BaseModel):
    genres: Optional[List[str]] = None
    min_year: Optional[int] = Field(default=None, ge=1900, le=2100)
    max_year: Optional[int] = Field(default=None, ge=1900, le=2100)
    min_rating: Optional[float] = Field(default=None, ge=0, le=10)


class RecommendationWeightsOverride(BaseModel):
    title: Optional[float] = Field(default=None, ge=0)
    genre: Optional[float] = Field(default=None, ge=0)
    semantic: Optional[float] = Field(default=None, ge=0)


class SimilarMoviesResponse(BaseModel):
    source_movie_id: str
    total_results: int
    model: str
    results: List[RecommendationItem]


class RecommendationSearchRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=300)
    limit: int = Field(default=10, ge=1, le=50)
    query_type: Optional[str] = Field(default="auto", pattern="^(auto|title|genre|context)$")
    filters: Optional[RecommendationSearchFilters] = None
    absa_refine: bool = True
    explain: bool = False
    debug: bool = False
    user_history: Optional[List[str]] = None
    rerank: bool = False
    weights_override: Optional[RecommendationWeightsOverride] = None


class RecommendationSearchDebug(BaseModel):
    query_raw: str
    query_normalized: str
    tokens: List[str] = Field(default_factory=list)
    query_type_requested: str
    weights: Dict[str, float] = Field(default_factory=dict)
    filters: Dict[str, Any] = Field(default_factory=dict)
    absa_refine: bool
    absa_intents: List[Dict[str, str]] = Field(default_factory=list)
    semantic_ready: bool
    absa_profile_ready: bool
    personalization: Dict[str, Any] = Field(default_factory=dict)


class RecommendationSearchResponse(BaseModel):
    query: str
    total_results: int
    model: str
    debug: Optional[RecommendationSearchDebug] = None
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
    database_connected: bool
    movies_count: int
