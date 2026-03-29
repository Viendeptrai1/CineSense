"""
CineSense API - Pydantic Schemas
================================

Request and response models for the API endpoints.
"""

from datetime import date
from datetime import datetime
from typing import List, Optional, Dict, Any, Literal
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
    semantic_backend: Optional[Literal["auto", "sbert", "tfidf"]] = Field(
        default="auto",
        description="Chỉ áp dụng engine artifact: auto=ưu tiên SBERT nếu có embeddings.npy, không thì TF-IDF; "
        "sbert|tfidf=ép dùng đúng lớp ngữ nghĩa để so sánh hiệu năng mô hình.",
    )
    autocorrect: bool = Field(
        default=False,
        description="Nếu True: sửa chính tả tiếng Anh (từ điển) trước khi tìm; phản hồi có query_effective.",
    )


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
    semantic_backend_requested: Optional[str] = None
    semantic_model_resolved: Optional[str] = None
    artifact_version: Optional[str] = None
    artifact_text_representation: Optional[str] = None
    artifact_fine_tuned: bool = False
    absa_profile_ready: bool
    personalization: Dict[str, Any] = Field(default_factory=dict)
    engine: Optional[Literal["artifact"]] = None
    rerank: Optional[Dict[str, Any]] = None


class RecommendationSearchResponse(BaseModel):
    query: str
    query_effective: str = Field(
        ...,
        description="Chuỗi thực tế đưa vào engine (sau autocorrect nếu bật; không thì trùng query).",
    )
    autocorrect_applied: bool = False
    engines_used: List[str] = Field(
        default_factory=lambda: ["artifact"],
        description="Engine runtime hiện tại. CineSen chỉ dùng artifact search cho luồng demo web.",
    )
    total_results: int
    model: str
    debug: Optional[RecommendationSearchDebug] = None
    results: List[RecommendationItem]


class BaselineCosineRequest(BaseModel):
    """Tìm phim chỉ bằng cosine(query, doc_vector) trên artifact baseline (notebook 03)."""

    query: str = Field(..., min_length=2, max_length=300)
    baseline: Literal["sbert", "sbert_en_finetuned", "tfidf", "word2vec"] = Field(
        ...,
        description="Thư mục: sbert_latest | sbert_en_finetuned_latest | tfidf_latest | word2vec_latest.",
    )
    limit: int = Field(default=24, ge=1, le=50)


class BaselineCosineResponse(BaseModel):
    """Kết quả xếp hạng thuần cosine, tách biệt khỏi artifact runtime chính."""

    query: str
    baseline: Literal["sbert", "sbert_en_finetuned", "tfidf", "word2vec"]
    model: str
    ranking: str = Field(default="cosine_similarity", description="Chỉ cosine, không BM25/ABSA/rerank.")
    artifact_version: str = Field("", description="Ví dụ sbert_latest")
    total_results: int
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
