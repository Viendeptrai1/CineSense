"""
CineSense ETL Pipeline - Main Orchestrator
============================================

Entry point for the ETL (Extract, Transform, Load) pipeline.

Pipeline Flow:
1. EXTRACT: Fetch movies/reviews from TMDB API (or mock data for testing)
2. TRANSFORM: Normalize English metadata and review corpus
3. LOAD: Upsert to PostgreSQL core tables

Usage:
    # Run with mock data (for testing)
    python -m etl_pipeline.main --mock
    
    # Run with real TMDB data (default: 10 pages = 200 movies)
    python -m etl_pipeline.main --pages 10
    
    # Full ingestion (50 pages = 1000 movies)
    python -m etl_pipeline.main --pages 50
"""

import argparse
import uuid
from datetime import date, datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from loguru import logger

from .config import settings
from .db_postgres import (
    init_database,
    get_session,
    get_engine,
    Base,
    CoreMovie,
    CoreReview,
    CoreGenre,
)
from .crawler import TMDBClient, TMDBMovie, TMDBReview, TMDBGenre


def _parse_tmdb_datetime(value: str) -> Optional[datetime]:
    """Parse TMDB ISO datetime safely."""
    if not value:
        return None
    try:
        # TMDB timestamps often end with Z; normalize for datetime.fromisoformat
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _infer_review_language(content: str) -> str:
    """
    Lightweight language heuristic for training contract.

    We default to English and mark unknown only for very short/noisy text.
    """
    text = (content or "").strip()
    if len(text) < 20:
        return "unknown"
    ascii_letters = sum(ch.isascii() and ch.isalpha() for ch in text)
    alpha_total = sum(ch.isalpha() for ch in text)
    if alpha_total == 0:
        return "unknown"
    ratio = ascii_letters / alpha_total
    return "en" if ratio >= 0.85 else "unknown"


# ============================================
# ETL Pipeline - TMDB Data Ingestion
# ============================================

def load_genres_from_tmdb(session, client: TMDBClient) -> Dict[int, CoreGenre]:
    """
    Fetch and load genres from TMDB to PostgreSQL.
    
    Returns:
        Dict mapping TMDB genre ID to CoreGenre ORM object
    """
    tmdb_genres = client.get_genres()
    genre_map = {}
    
    for tmdb_genre in tmdb_genres:
        # Use TMDB genre ID as our genre ID for consistency
        existing = session.query(CoreGenre).filter(CoreGenre.id == tmdb_genre.id).first()
        if existing:
            genre_map[tmdb_genre.id] = existing
        else:
            genre = CoreGenre(id=tmdb_genre.id, name=tmdb_genre.name)
            session.add(genre)
            session.flush()
            genre_map[tmdb_genre.id] = genre
    
    logger.info(f"Loaded {len(genre_map)} genres to PostgreSQL")
    return genre_map


def process_tmdb_movie(
    session,
    tmdb_movie: TMDBMovie,
    tmdb_reviews: List[TMDBReview],
    genre_map: Dict[int, CoreGenre],
) -> Optional[Dict[str, Any]]:
    """
    Process a single movie and its reviews into PostgreSQL.
    
    Returns:
        Dict with inserted movie/review counts for reporting
    """
    existing = session.query(CoreMovie).filter(CoreMovie.tmdb_id == tmdb_movie.tmdb_id).first()

    genre_objects = [
        genre_map[gid] for gid in tmdb_movie.genre_ids
        if gid in genre_map
    ]

    movie_created = existing is None
    movie = existing or CoreMovie(
        tmdb_id=tmdb_movie.tmdb_id,
        title=tmdb_movie.title or tmdb_movie.original_title or "Unknown",
    )
    movie.title = tmdb_movie.title or tmdb_movie.original_title or movie.title
    movie.original_title = tmdb_movie.original_title or tmdb_movie.title
    movie.overview = tmdb_movie.overview or None
    movie.release_date = tmdb_movie.release_date
    movie.poster_path = tmdb_movie.poster_path
    movie.backdrop_path = tmdb_movie.backdrop_path
    movie.popularity = tmdb_movie.popularity
    movie.vote_average = tmdb_movie.vote_average
    movie.vote_count = tmdb_movie.vote_count
    movie.genres = genre_objects
    session.add(movie)
    session.flush()

    existing_review_ids = {
        review_id
        for (review_id,) in session.query(CoreReview.external_review_id)
        .filter(CoreReview.movie_id == movie.id, CoreReview.external_review_id.is_not(None))
        .all()
    }
    reviews_inserted = 0

    for tmdb_review in tmdb_reviews:
        if not tmdb_review.content or len(tmdb_review.content.strip()) < 20:
            continue

        if tmdb_review.tmdb_id in existing_review_ids:
            continue

        source_created_at = _parse_tmdb_datetime(tmdb_review.created_at)

        review = CoreReview(
            id=uuid.uuid4(),
            movie_id=movie.id,
            external_review_id=tmdb_review.tmdb_id,
            source="tmdb",
            language=_infer_review_language(tmdb_review.content),
            author_username=tmdb_review.author,
            author_name=tmdb_review.author_name,
            author_avatar_url=f"https://image.tmdb.org/t/p/original{tmdb_review.avatar_path}" if tmdb_review.avatar_path else None,
            content=tmdb_review.content,
            rating=tmdb_review.rating,
            source_created_at=source_created_at,
            source_url=tmdb_review.url,
        )
        session.add(review)
        reviews_inserted += 1

    return {
        "movie_id": str(movie.id),
        "movie_title": tmdb_movie.title,
        "movie_created": movie_created,
        "reviews_inserted": reviews_inserted,
    }


def embed_and_load_reviews(
    movie_data_list: List[Dict[str, Any]],
    batch_size: int = 32,
) -> int:
    """
    Placeholder kept for backwards compatibility while vector serving is disabled.
    """
    del movie_data_list
    del batch_size
    return 0


def run_tmdb_etl_pipeline(
    pages: int = 10,
    max_reviews_per_movie: int = 10,
    commit_batch_size: int = 50,
    reset_db: bool = False,
) -> None:
    """
    Execute ETL pipeline with real TMDB data.
    
    Args:
        pages: Number of discovery pages (20 movies/page)
        max_reviews_per_movie: Maximum reviews to fetch per movie
        commit_batch_size: Movies to process before committing
        reset_db: Whether to drop and recreate database tables
    """
    logger.info("🚀 Starting CineSense ETL Pipeline (TMDB Mode)")
    logger.info(f"   Pages to fetch: {pages} (~{pages * 20} movies)")
    logger.info("   Mode: PostgreSQL core schema only")
    
    # Initialize databases
    if reset_db:
        logger.warning("🗑️  Resetting database tables...")
        engine = get_engine()
        Base.metadata.drop_all(engine)
        init_database()
    else:
        logger.info("📦 Initializing databases...")
        init_database()
    
    # Start TMDB client
    with TMDBClient() as client:
        session = get_session()
        
        try:
            # Load genres first
            logger.info("📚 Loading genres from TMDB...")
            genre_map = load_genres_from_tmdb(session, client)
            session.commit()
            
            # Process movies in batches
            logger.info("🎬 Fetching movies and reviews from TMDB...")
            total_movies = 0
            total_reviews = 0
            
            for page in range(1, pages + 1):
                movies = client.get_popular_movies(page=page)
                
                for tmdb_movie in movies:
                    # Fetch reviews
                    tmdb_reviews = client.get_movie_reviews(
                        tmdb_movie.tmdb_id,
                        max_pages=2
                    )[:max_reviews_per_movie]
                    
                    # Process and store
                    movie_data = process_tmdb_movie(
                        session, tmdb_movie, tmdb_reviews, genre_map
                    )
                    
                    if movie_data:
                        total_movies += 1 if movie_data["movie_created"] else 0
                        total_reviews += movie_data["reviews_inserted"]
                    
                    # Commit batch
                    if (total_movies + total_reviews) and (total_movies + total_reviews) % commit_batch_size == 0:
                        session.commit()
                
                logger.info(f"📊 Progress: Page {page}/{pages} | Movies: {total_movies} | Reviews: {total_reviews}")

            session.commit()
            
        except Exception as e:
            session.rollback()
            logger.error(f"❌ ETL Pipeline failed: {e}")
            raise
        finally:
            session.close()
    
    # Display final statistics
    logger.info("📊 Final Statistics:")
    logger.info(f"   Total Movies: {total_movies}")
    logger.info(f"   Total Reviews: {total_reviews}")
    logger.success("✅ PostgreSQL core ETL completed successfully!")


# ============================================
# Mock Data for Testing
# ============================================

@dataclass
class MockReview:
    """Mock review data structure."""
    content: str
    source: str
    rating: float


@dataclass
class MockMovie:
    """Mock movie data structure."""
    title: str
    overview: str
    release_date: date
    poster_path: str
    genres: List[str]
    reviews: List[MockReview] = field(default_factory=list)


def generate_mock_data() -> List[MockMovie]:
    """Generate mock movie data for testing."""
    return [
        MockMovie(
            title="The Dark Knight",
            overview="When the menace known as the Joker wreaks havoc on Gotham...",
            release_date=date(2008, 7, 18),
            poster_path="/qJ2tW6WMUDux911r6m7haRef0WH.jpg",
            genres=["Action", "Crime", "Drama"],
            reviews=[
                MockReview("A masterpiece of modern cinema. Heath Ledger's Joker is terrifying.", "imdb", 9.5),
                MockReview("Dark, gritty, and thought-provoking. Perfect for intense nights.", "user", 8.5),
            ],
        ),
        MockMovie(
            title="Inception",
            overview="A thief who steals secrets through dream-sharing technology...",
            release_date=date(2010, 7, 16),
            poster_path="/edv5CZvWj09upOsy2Y6IwDhK8bt.jpg",
            genres=["Action", "Science Fiction"],
            reviews=[
                MockReview("Mind-bending brilliance! Layered dreams are stunning.", "imdb", 9.0),
            ],
        ),
        MockMovie(
            title="Titanic",
            overview="A seventeen-year-old aristocrat falls in love aboard the Titanic.",
            release_date=date(1997, 12, 19),
            poster_path="/9xjZS2rlVxm8SFx8kPC3aIGCOYQ.jpg",
            genres=["Drama", "Romance"],
            reviews=[
                MockReview("An emotional rollercoaster. Perfect for a sad movie night.", "imdb", 8.5),
                MockReview("Epic romance meets historical disaster. Get tissues ready.", "user", 8.0),
            ],
        ),
    ]


def run_mock_etl_pipeline() -> None:
    """Execute ETL pipeline with mock data for testing."""
    logger.info("🚀 Starting CineSense ETL Pipeline (Mock Mode)")
    logger.info("   Mode: PostgreSQL core schema only")
    
    # Initialize databases
    logger.info("📦 Initializing databases...")
    init_database()
    
    # Generate mock data
    logger.info("🎬 Generating mock movie data...")
    mock_movies = generate_mock_data()
    
    session = get_session()
    movie_data_list = []
    
    try:
        for mock_movie in mock_movies:
            # Create genres
            genre_objects = []
            for index, name in enumerate(mock_movie.genres, start=1):
                genre = session.query(CoreGenre).filter(CoreGenre.name == name).first()
                if genre is None:
                    genre = CoreGenre(id=1000 + index, name=name)
                    session.add(genre)
                    session.flush()
                genre_objects.append(genre)
            
            # Create movie
            movie = CoreMovie(
                title=mock_movie.title,
                original_title=mock_movie.title,
                overview=mock_movie.overview,
                release_date=mock_movie.release_date,
                poster_path=mock_movie.poster_path,
                genres=genre_objects,
            )
            session.add(movie)
            session.flush()
            
            # Create reviews
            for mock_review in mock_movie.reviews:
                review = CoreReview(
                    movie_id=movie.id,
                    content=mock_review.content,
                    source=mock_review.source,
                    language="en",
                    rating=mock_review.rating,
                )
                session.add(review)
                session.flush()
            
            logger.info(f"Loaded: {mock_movie.title} ({len(mock_movie.reviews)} reviews)")
        
        session.commit()
        
    except Exception as e:
        session.rollback()
        logger.error(f"❌ Mock ETL failed: {e}")
        raise
    finally:
        session.close()
    
    logger.success("✅ Mock ETL Pipeline completed successfully!")


# ============================================
# CLI Entry Point
# ============================================

def main():
    parser = argparse.ArgumentParser(
        description="CineSense ETL Pipeline - Ingest movie data from TMDB"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock data instead of TMDB API (for testing)",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=10,
        help="Number of TMDB pages to fetch (20 movies/page, default: 10)",
    )
    parser.add_argument(
        "--max-reviews",
        type=int,
        default=10,
        help="Maximum reviews per movie (default: 10)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset database tables before starting (WARNING: Deletes all data)",
    )
    
    args = parser.parse_args()
    
    # Configure logging
    logger.add(
        "etl_pipeline.log",
        rotation="10 MB",
        retention="7 days",
        level=settings.etl.log_level,
    )
    
    if args.mock:
        run_mock_etl_pipeline()
    else:
        run_tmdb_etl_pipeline(
            pages=args.pages,
            max_reviews_per_movie=args.max_reviews,
            reset_db=args.reset,
        )


if __name__ == "__main__":
    main()
