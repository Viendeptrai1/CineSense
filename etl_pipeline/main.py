"""
CineSense ETL Pipeline - Main Orchestrator
============================================

Entry point for the ETL (Extract, Transform, Load) pipeline.

Pipeline Flow:
1. EXTRACT: Fetch movies/reviews from TMDB API (or mock data for testing)
2. TRANSFORM: Clean text and generate embeddings
3. LOAD: Upsert to PostgreSQL and Qdrant

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
from datetime import date
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from loguru import logger

from .config import settings
from .db_postgres import (
    init_database,
    get_session,
    get_engine,
    Base,
    Movie,
    Review,
    Genre,
    create_or_get_genre,
)
from .db_qdrant import init_qdrant, upsert_review_vectors, get_collection_info
from .embedder import embed_text, preprocess_text, embed_texts
from .crawler import TMDBClient, TMDBMovie, TMDBReview, TMDBGenre


# ============================================
# ETL Pipeline - TMDB Data Ingestion
# ============================================

def load_genres_from_tmdb(session, client: TMDBClient) -> Dict[int, Genre]:
    """
    Fetch and load genres from TMDB to PostgreSQL.
    
    Returns:
        Dict mapping TMDB genre ID to Genre ORM object
    """
    tmdb_genres = client.get_genres()
    genre_map = {}
    
    for tmdb_genre in tmdb_genres:
        # Use TMDB genre ID as our genre ID for consistency
        existing = session.query(Genre).filter(Genre.id == tmdb_genre.id).first()
        if existing:
            genre_map[tmdb_genre.id] = existing
        else:
            genre = Genre(id=tmdb_genre.id, name=tmdb_genre.name)
            session.add(genre)
            session.flush()
            genre_map[tmdb_genre.id] = genre
    
    logger.info(f"Loaded {len(genre_map)} genres to PostgreSQL")
    return genre_map


def process_tmdb_movie(
    session,
    tmdb_movie: TMDBMovie,
    tmdb_reviews: List[TMDBReview],
    genre_map: Dict[int, Genre],
) -> Optional[Dict[str, Any]]:
    """
    Process a single movie and its reviews into PostgreSQL.
    
    Returns:
        Dict with movie_id, review_ids, genre_ids, year for Qdrant loading
    """
    # Check if movie already exists (by TMDB ID)
    existing = session.query(Movie).filter(Movie.tmdb_id == tmdb_movie.tmdb_id).first()
    if existing:
        logger.debug(f"Movie already exists: {tmdb_movie.title}")
        return None
    
    # Get genre objects
    genre_objects = [
        genre_map[gid] for gid in tmdb_movie.genre_ids
        if gid in genre_map
    ]
    
    # Create movie
    movie = Movie(
        tmdb_id=tmdb_movie.tmdb_id,
        title=tmdb_movie.title,
        overview=tmdb_movie.overview,
        release_date=tmdb_movie.release_date,
        poster_path=tmdb_movie.poster_path,
        genres=genre_objects,
    )
    session.add(movie)
    session.flush()
    
    # Create reviews
    review_ids = []
    review_contents = []
    review_ratings = []
    
    for tmdb_review in tmdb_reviews:
        # Skip empty reviews
        if not tmdb_review.content or len(tmdb_review.content.strip()) < 20:
            continue
        
        review = Review(
            movie_id=movie.id,
            content=tmdb_review.content,
            source="tmdb",
            rating=tmdb_review.rating,
            author_name=tmdb_review.author_name,
            author_avatar_url=f"https://image.tmdb.org/t/p/original{tmdb_review.avatar_path}" if tmdb_review.avatar_path else None
        )
        session.add(review)
        session.flush()
        
        review_ids.append(str(review.id))
        review_contents.append(tmdb_review.content)
        review_ratings.append(tmdb_review.rating)
    
    if not review_ids:
        logger.debug(f"No valid reviews for: {tmdb_movie.title}")
        return None
    
    return {
        "movie_id": str(movie.id),
        "movie_title": tmdb_movie.title,
        "review_ids": review_ids,
        "review_contents": review_contents,
        "review_ratings": review_ratings,
        "genre_ids": [g.id for g in genre_objects],
        "year": tmdb_movie.release_date.year if tmdb_movie.release_date else 2000,
    }


def embed_and_load_reviews(
    movie_data_list: List[Dict[str, Any]],
    batch_size: int = 32,
) -> int:
    """
    Generate embeddings for reviews and load to Qdrant.
    
    Uses batch embedding for efficiency.
    
    Returns:
        Number of vectors upserted
    """
    all_vectors = []
    
    for movie_data in movie_data_list:
        movie_id = movie_data["movie_id"]
        movie_title = movie_data["movie_title"]
        review_ids = movie_data["review_ids"]
        review_contents = movie_data["review_contents"]
        review_ratings = movie_data["review_ratings"]
        genre_ids = movie_data["genre_ids"]
        year = movie_data["year"]
        
        # Preprocess all review contents
        clean_contents = [preprocess_text(content) for content in review_contents]
        
        # Batch embed
        vectors = embed_texts(clean_contents, preprocess=False, show_progress=False)
        
        # Build Qdrant points
        for i, (review_id, vector, rating) in enumerate(zip(review_ids, vectors, review_ratings)):
            point_data = {
                "id": review_id,
                "vector": vector,
                "payload": {
                    "movie_id": movie_id,
                    "movie_title": movie_title,
                    "rating": rating or 0.0,
                    "year": year,
                    "genre_ids": [str(gid) for gid in genre_ids],
                    "source": "tmdb",
                },
            }
            all_vectors.append(point_data)
    
    # Upsert in batches
    if all_vectors:
        for i in range(0, len(all_vectors), batch_size):
            batch = all_vectors[i:i+batch_size]
            upsert_review_vectors(batch)
    
    return len(all_vectors)


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
    logger.info(f"   Embedding Model: {settings.embedding.model}")
    
    # Initialize databases
    if reset_db:
        logger.warning("🗑️  Resetting database tables...")
        engine = get_engine()
        Base.metadata.drop_all(engine)
        init_database()
        # Note: We might want to clear Qdrant too, but it handles upserts gracefully
    else:
        logger.info("📦 Initializing databases...")
        init_database()

    init_qdrant()
    
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
            movie_data_batch = []
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
                        movie_data_batch.append(movie_data)
                        total_movies += 1
                        total_reviews += len(movie_data["review_ids"])
                    
                    # Commit batch
                    if len(movie_data_batch) >= commit_batch_size:
                        session.commit()
                        logger.info(f"🔮 Embedding {len(movie_data_batch)} movies...")
                        vectors_count = embed_and_load_reviews(movie_data_batch)
                        logger.info(f"   → {vectors_count} vectors upserted")
                        movie_data_batch = []
                
                logger.info(f"📊 Progress: Page {page}/{pages} | Movies: {total_movies} | Reviews: {total_reviews}")
            
            # Final batch
            if movie_data_batch:
                session.commit()
                logger.info(f"🔮 Embedding final batch of {len(movie_data_batch)} movies...")
                vectors_count = embed_and_load_reviews(movie_data_batch)
                logger.info(f"   → {vectors_count} vectors upserted")
            
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
    
    try:
        qdrant_info = get_collection_info()
        logger.info(f"   Qdrant Vectors: {qdrant_info.get('points_count', 'N/A')}")
    except Exception as e:
        logger.warning(f"   Could not fetch Qdrant stats: {e}")
    
    logger.success("✅ TMDB ETL Pipeline completed successfully!")


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
    logger.info(f"   Embedding Model: {settings.embedding.model}")
    
    # Initialize databases
    logger.info("📦 Initializing databases...")
    init_database()
    init_qdrant()
    
    # Generate mock data
    logger.info("🎬 Generating mock movie data...")
    mock_movies = generate_mock_data()
    
    session = get_session()
    movie_data_list = []
    
    try:
        for mock_movie in mock_movies:
            # Create genres
            genre_objects = [
                create_or_get_genre(session, name)
                for name in mock_movie.genres
            ]
            
            # Create movie
            movie = Movie(
                title=mock_movie.title,
                overview=mock_movie.overview,
                release_date=mock_movie.release_date,
                poster_path=mock_movie.poster_path,
                genres=genre_objects,
            )
            session.add(movie)
            session.flush()
            
            # Create reviews
            review_ids = []
            review_contents = []
            review_ratings = []
            
            for mock_review in mock_movie.reviews:
                review = Review(
                    movie_id=movie.id,
                    content=mock_review.content,
                    source=mock_review.source,
                    rating=mock_review.rating,
                )
                session.add(review)
                session.flush()
                review_ids.append(str(review.id))
                review_contents.append(mock_review.content)
                review_ratings.append(mock_review.rating)
            
            movie_data_list.append({
                "movie_id": str(movie.id),
                "movie_title": mock_movie.title,
                "review_ids": review_ids,
                "review_contents": review_contents,
                "review_ratings": review_ratings,
                "genre_ids": [g.id for g in genre_objects],
                "year": mock_movie.release_date.year,
            })
            
            logger.info(f"Loaded: {mock_movie.title} ({len(review_ids)} reviews)")
        
        session.commit()
        
        # Embed and load to Qdrant
        logger.info("🔮 Generating embeddings...")
        vectors_count = embed_and_load_reviews(movie_data_list)
        logger.info(f"   → {vectors_count} vectors upserted")
        
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
