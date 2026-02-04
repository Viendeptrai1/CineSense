"""
CineSense TMDB Data Crawler
===========================

Fetches movie metadata and reviews from The Movie Database (TMDB) API.

Strategy:
1. Discovery: Fetch popular/top_rated movies (Vietnamese metadata)
2. Enrichment: Fetch English reviews for each movie
3. Genre Mapping: Fetch and cache genre taxonomy

API Endpoints Used:
- /movie/popular - Get popular movies
- /movie/top_rated - Get top rated movies
- /movie/{id}/reviews - Get movie reviews
- /genre/movie/list - Get genre taxonomy

Rate Limiting:
- TMDB allows ~40 requests/second
- We use conservative delays to be respectful
"""

import time
from dataclasses import dataclass, field
from datetime import date
from typing import List, Dict, Any, Optional, Generator
from uuid import UUID

import httpx
from loguru import logger

from .config import settings


# ============================================
# Data Transfer Objects (DTOs)
# ============================================

@dataclass
class TMDBGenre:
    """Genre from TMDB API."""
    id: int
    name: str


@dataclass
class TMDBMovie:
    """Movie data from TMDB API."""
    tmdb_id: int
    title: str
    original_title: str
    overview: str
    release_date: Optional[date]
    poster_path: Optional[str]
    backdrop_path: Optional[str]
    vote_average: float
    vote_count: int
    popularity: float
    genre_ids: List[int]
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "TMDBMovie":
        """Parse TMDB API response into TMDBMovie object."""
        # Parse release_date safely
        release_date = None
        if data.get("release_date"):
            try:
                release_date = date.fromisoformat(data["release_date"])
            except ValueError:
                pass
        
        return cls(
            tmdb_id=data["id"],
            title=data.get("title", "Unknown"),
            original_title=data.get("original_title", ""),
            overview=data.get("overview", ""),
            release_date=release_date,
            poster_path=data.get("poster_path"),
            backdrop_path=data.get("backdrop_path"),
            vote_average=data.get("vote_average", 0.0),
            vote_count=data.get("vote_count", 0),
            popularity=data.get("popularity", 0.0),
            genre_ids=data.get("genre_ids", []),
        )


@dataclass
class TMDBReview:
    """Review data from TMDB API."""
    tmdb_id: str  # TMDB review IDs are strings
    author: str # username
    author_name: str # real name
    content: str
    rating: Optional[float]  # Author's rating (if available)
    avatar_path: Optional[str]
    created_at: str
    url: str
    
    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "TMDBReview":
        """Parse TMDB API response into TMDBReview object."""
        # Rating and avatar are nested in author_details
        rating = None
        avatar_path = None
        author_name = ""
        
        author_details = data.get("author_details", {})
        if author_details.get("rating"):
            rating = float(author_details["rating"])
        
        avatar_path = author_details.get("avatar_path")
        author_name = author_details.get("name") or data.get("author") # Fallback to username
        
        return cls(
            tmdb_id=data["id"],
            author=data.get("author", "Anonymous"),
            author_name=author_name,
            content=data.get("content", ""),
            rating=rating,
            avatar_path=avatar_path,
            created_at=data.get("created_at", ""),
            url=data.get("url", ""),
        )


# ============================================
# TMDB API Client
# ============================================

class TMDBClient:
    """
    Client for TMDB API with rate limiting and error handling.
    
    Features:
    - Automatic retry on rate limit (429)
    - Configurable language for metadata
    - Pagination support for discovery endpoints
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        language: Optional[str] = None,
        request_delay: float = 0.1,  # 100ms between requests
    ):
        self.api_key = api_key or settings.tmdb.api_key
        self.base_url = base_url or settings.tmdb.base_url
        self.language = language or settings.tmdb.language
        self.request_delay = request_delay
        
        if not self.api_key:
            raise ValueError("TMDB API key is required. Set TMDB_API_KEY in .env")
        
        # Create HTTP client with timeout
        self.client = httpx.Client(
            base_url=self.base_url,
            timeout=30.0,
            headers={"accept": "application/json"},
        )
        
        # Cache for genre mapping
        self._genre_cache: Dict[int, str] = {}
    
    def _make_request(
        self,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        retry_count: int = 3,
    ) -> Dict[str, Any]:
        """
        Make API request with rate limiting and retry logic.
        
        Args:
            endpoint: API endpoint (e.g., /movie/popular)
            params: Query parameters
            retry_count: Number of retries on failure
            
        Returns:
            API response as dictionary
        """
        # Add API key to params
        params = params or {}
        params["api_key"] = self.api_key
        
        for attempt in range(retry_count):
            try:
                # Respect rate limiting
                time.sleep(self.request_delay)
                
                response = self.client.get(endpoint, params=params)
                
                # Handle rate limiting
                if response.status_code == 429:
                    wait_time = int(response.headers.get("Retry-After", 10))
                    logger.warning(f"Rate limited. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                
                response.raise_for_status()
                return response.json()
                
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP error on {endpoint}: {e}")
                if attempt == retry_count - 1:
                    raise
            except httpx.RequestError as e:
                logger.error(f"Request error on {endpoint}: {e}")
                if attempt == retry_count - 1:
                    raise
        
        return {}
    
    def get_genres(self) -> List[TMDBGenre]:
        """
        Fetch movie genre taxonomy from TMDB.
        
        Returns:
            List of TMDBGenre objects
        """
        response = self._make_request(
            "/genre/movie/list",
            params={"language": self.language}
        )
        
        genres = []
        for genre_data in response.get("genres", []):
            genre = TMDBGenre(id=genre_data["id"], name=genre_data["name"])
            genres.append(genre)
            # Cache for later use
            self._genre_cache[genre.id] = genre.name
        
        logger.info(f"Fetched {len(genres)} genres from TMDB")
        return genres
    
    def get_genre_name(self, genre_id: int) -> str:
        """Get genre name by ID (from cache or API)."""
        if not self._genre_cache:
            self.get_genres()
        return self._genre_cache.get(genre_id, "Unknown")
    
    def get_popular_movies(
        self,
        page: int = 1,
        language: Optional[str] = None,
    ) -> List[TMDBMovie]:
        """
        Fetch popular movies from TMDB.
        
        Args:
            page: Page number (1-based)
            language: Override default language
            
        Returns:
            List of TMDBMovie objects (up to 20 per page)
        """
        response = self._make_request(
            "/movie/popular",
            params={
                "language": language or self.language,
                "page": page,
            }
        )
        
        movies = [
            TMDBMovie.from_api_response(movie_data)
            for movie_data in response.get("results", [])
        ]
        
        logger.debug(f"Fetched {len(movies)} popular movies (page {page})")
        return movies
    
    def get_top_rated_movies(
        self,
        page: int = 1,
        language: Optional[str] = None,
    ) -> List[TMDBMovie]:
        """
        Fetch top rated movies from TMDB.
        
        Args:
            page: Page number (1-based)
            language: Override default language
            
        Returns:
            List of TMDBMovie objects (up to 20 per page)
        """
        response = self._make_request(
            "/movie/top_rated",
            params={
                "language": language or self.language,
                "page": page,
            }
        )
        
        movies = [
            TMDBMovie.from_api_response(movie_data)
            for movie_data in response.get("results", [])
        ]
        
        logger.debug(f"Fetched {len(movies)} top rated movies (page {page})")
        return movies
    
    def get_movie_reviews(
        self,
        movie_id: int,
        max_pages: int = 3,
    ) -> List[TMDBReview]:
        """
        Fetch reviews for a specific movie.
        
        Note: Reviews are mostly in English, which is fine for our
        multilingual embedding model.
        
        Args:
            movie_id: TMDB movie ID
            max_pages: Maximum pages to fetch (20 reviews/page)
            
        Returns:
            List of TMDBReview objects
        """
        all_reviews = []
        
        for page in range(1, max_pages + 1):
            response = self._make_request(
                f"/movie/{movie_id}/reviews",
                params={"page": page}
            )
            
            reviews = [
                TMDBReview.from_api_response(review_data)
                for review_data in response.get("results", [])
            ]
            
            all_reviews.extend(reviews)
            
            # Check if we've reached the last page
            total_pages = response.get("total_pages", 1)
            if page >= total_pages:
                break
        
        logger.debug(f"Fetched {len(all_reviews)} reviews for movie {movie_id}")
        return all_reviews
    
    def discover_movies(
        self,
        pages: int = 50,
        source: str = "popular",
    ) -> Generator[TMDBMovie, None, None]:
        """
        Generator that yields movies from discovery endpoints.
        
        Args:
            pages: Number of pages to fetch (20 movies/page)
            source: "popular" or "top_rated"
            
        Yields:
            TMDBMovie objects
        """
        fetch_func = (
            self.get_popular_movies if source == "popular"
            else self.get_top_rated_movies
        )
        
        for page in range(1, pages + 1):
            movies = fetch_func(page=page)
            
            for movie in movies:
                yield movie
            
            if page % 10 == 0:
                logger.info(f"Discovery progress: {page}/{pages} pages")
    
    def close(self):
        """Close HTTP client."""
        self.client.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


# ============================================
# Data Ingestion Functions
# ============================================

def fetch_movies_with_reviews(
    pages: int = 10,
    max_reviews_per_movie: int = 5,
    source: str = "popular",
) -> Generator[tuple[TMDBMovie, List[TMDBReview]], None, None]:
    """
    Fetch movies and their reviews from TMDB.
    
    This is the main ingestion function that combines movie discovery
    with review fetching.
    
    Args:
        pages: Number of discovery pages (20 movies/page)
        max_reviews_per_movie: Max reviews to fetch per movie
        source: "popular" or "top_rated"
        
    Yields:
        Tuple of (TMDBMovie, List[TMDBReview])
    """
    with TMDBClient() as client:
        # Pre-fetch genres for caching
        client.get_genres()
        
        movie_count = 0
        review_count = 0
        
        for movie in client.discover_movies(pages=pages, source=source):
            # Fetch reviews for this movie
            reviews = client.get_movie_reviews(
                movie.tmdb_id,
                max_pages=(max_reviews_per_movie // 20) + 1
            )[:max_reviews_per_movie]
            
            movie_count += 1
            review_count += len(reviews)
            
            yield movie, reviews
        
        logger.success(
            f"Ingestion complete: {movie_count} movies, {review_count} reviews"
        )


def test_tmdb_connection() -> bool:
    """
    Test TMDB API connection and credentials.
    
    Returns:
        True if connection successful
    """
    try:
        with TMDBClient() as client:
            genres = client.get_genres()
            movies = client.get_popular_movies(page=1)
            
            logger.info(f"✅ TMDB connection successful!")
            logger.info(f"   - {len(genres)} genres available")
            logger.info(f"   - Sample movie: {movies[0].title if movies else 'N/A'}")
            
            return True
    except Exception as e:
        logger.error(f"❌ TMDB connection failed: {e}")
        return False


# ============================================
# CLI Entry Point
# ============================================

if __name__ == "__main__":
    # Quick test of TMDB connection
    logger.info("Testing TMDB API connection...")
    test_tmdb_connection()
