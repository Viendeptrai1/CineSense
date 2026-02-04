"""
CineSense PostgreSQL Database Module
=====================================

SQLAlchemy ORM models and database connection management.

Schema Design:
- movies: Core movie metadata (UUID primary key, TMDB integration ready)
- reviews: User/critic reviews linked to movies (1:N relationship)
- genres: Movie genre taxonomy
- movie_genres: Many-to-many junction table

Design Decisions:
- UUID primary keys for distributed system compatibility
- Soft delete patterns ready (can add is_deleted flag later)
- Timestamps for audit trail
"""

import uuid
from datetime import datetime, date
from typing import List, Optional

from sqlalchemy import (
    Column,
    String,
    Integer,
    Text,
    Date,
    DateTime,
    ForeignKey,
    Table,
    create_engine,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    sessionmaker,
    Session,
)
from sqlalchemy.sql import func

from .config import settings


# ============================================
# SQLAlchemy Base Class
# ============================================

class Base(DeclarativeBase):
    """Base class for all ORM models."""
    pass


# ============================================
# Association Tables (Many-to-Many)
# ============================================

# Junction table for Movie <-> Genre relationship
movie_genres = Table(
    "movie_genres",
    Base.metadata,
    Column("movie_id", UUID(as_uuid=True), ForeignKey("movies.id"), primary_key=True),
    Column("genre_id", Integer, ForeignKey("genres.id"), primary_key=True),
)


# ============================================
# ORM Models
# ============================================

class Movie(Base):
    """
    Movie entity - core metadata storage.
    
    Attributes:
        id: Internal UUID primary key
        tmdb_id: The Movie Database ID for external API integration
        title: Movie title
        overview: Plot synopsis
        release_date: Theatrical release date
        poster_path: TMDB poster image path (e.g., /abc123.jpg)
        created_at: Record creation timestamp
        updated_at: Last modification timestamp
    """
    
    __tablename__ = "movies"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Internal unique identifier"
    )
    tmdb_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        unique=True,
        nullable=True,
        index=True,
        comment="The Movie Database external ID"
    )
    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
        index=True,
        comment="Movie title"
    )
    overview: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Plot synopsis"
    )
    release_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
        comment="Theatrical release date"
    )
    poster_path: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="TMDB poster image path"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Record creation timestamp"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        comment="Last modification timestamp"
    )
    
    # Relationships
    reviews: Mapped[List["Review"]] = relationship(
        "Review",
        back_populates="movie",
        cascade="all, delete-orphan"
    )
    genres: Mapped[List["Genre"]] = relationship(
        "Genre",
        secondary=movie_genres,
        back_populates="movies"
    )
    
    def __repr__(self) -> str:
        return f"<Movie(id={self.id}, title='{self.title}')>"


class Review(Base):
    """
    Movie review entity.
    
    Design Note:
    - Each review is stored as a separate vector in Qdrant
    - This allows granular semantic search at the review level
    - movie_id links back to the movie for payload enrichment
    
    Attributes:
        id: Internal UUID primary key
        movie_id: Foreign key to movies table
        content: Review text content
        source: Origin of review (e.g., 'imdb', 'rotten_tomatoes', 'user')
        rating: Optional numeric rating (1-10 scale normalized)
        created_at: Record creation timestamp
    """
    
    __tablename__ = "reviews"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="Internal unique identifier"
    )
    movie_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("movies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to parent movie"
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Review text content"
    )
    source: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        default="unknown",
        comment="Review source (imdb, rotten_tomatoes, user)"
    )
    rating: Mapped[Optional[float]] = mapped_column(
        nullable=True,
        comment="Numeric rating (1-10 scale)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        comment="Record creation timestamp"
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
        comment="Author user ID (null if crawler review)"
    )
    author_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Real name of external reviewer (from TMDB)"
    )
    author_avatar_url: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Avatar URL for external reviewer"
    )
    likes_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
        server_default="0",
        comment="Denormalized like count"
    )

    # Relationships
    movie: Mapped["Movie"] = relationship("Movie", back_populates="reviews")
    user: Mapped["User"] = relationship("User", back_populates="reviews")
    likes: Mapped[List["ReviewLike"]] = relationship("ReviewLike", back_populates="review")
    
    def __repr__(self) -> str:
        return f"<Review(id={self.id}, movie_id={self.movie_id}, source='{self.source}')>"


class User(Base):
    """
    User entity for authentication and personalization.
    """
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        comment="User unique identifier"
    )
    username: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        index=True,
        nullable=False,
        comment="Login username"
    )
    nickname: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Display name"
    )
    password_hash: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Argon2 password hash"
    )
    email: Mapped[Optional[str]] = mapped_column(
        String(255),
        unique=True,
        nullable=True,
        comment="Optional email for recovery"
    )
    avatar_url: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True
    )
    preferences: Mapped[Optional[dict]] = mapped_column(
        JSONB,
        nullable=True,
        default={},
        comment="User preferences for cold start (genres, fav movies)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now()
    )

    # Relationships
    reviews: Mapped[List["Review"]] = relationship("Review", back_populates="user")
    likes: Mapped[List["ReviewLike"]] = relationship("ReviewLike", back_populates="user")
    watchlist: Mapped[List["Watchlist"]] = relationship("Watchlist", back_populates="user")

    def __repr__(self) -> str:
        return f"<User(username='{self.username}')>"


class ReviewLike(Base):
    """Interaction: User likes a review."""
    __tablename__ = "review_likes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("reviews.id", ondelete="CASCADE"), primary_key=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="likes")
    review: Mapped["Review"] = relationship("Review", back_populates="likes")


class Watchlist(Base):
    """User's movie watchlist."""
    __tablename__ = "watchlist"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    movie_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("movies.id", ondelete="CASCADE")
    )
    status: Mapped[str] = mapped_column(
        String(20), default="plan_to_watch", comment="plan_to_watch, completed, dropped"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="watchlist")
    movie: Mapped["Movie"] = relationship("Movie")

    __table_args__ = (
        UniqueConstraint('user_id', 'movie_id', name='uq_user_movie_watchlist'),
    )


class Genre(Base):
    """
    Movie genre taxonomy.
    
    Attributes:
        id: Integer primary key (can match TMDB genre IDs)
        name: Genre name (e.g., 'Action', 'Drama')
    """
    
    __tablename__ = "genres"
    
    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True,
        autoincrement=True,
        comment="Genre identifier"
    )
    name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
        comment="Genre name"
    )
    
    # Relationships
    movies: Mapped[List["Movie"]] = relationship(
        "Movie",
        secondary=movie_genres,
        back_populates="genres"
    )
    
    def __repr__(self) -> str:
        return f"<Genre(id={self.id}, name='{self.name}')>"


# ============================================
# Database Connection & Session Management
# ============================================

def get_engine():
    """
    Create SQLAlchemy engine with connection pooling.
    
    Returns:
        Engine: SQLAlchemy engine instance
    """
    return create_engine(
        settings.postgres.database_url,
        echo=False,  # Set to True for SQL debugging
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,  # Verify connections before use
    )


def get_session_factory() -> sessionmaker:
    """
    Create session factory for database operations.
    
    Returns:
        sessionmaker: Session factory bound to engine
    """
    engine = get_engine()
    return sessionmaker(bind=engine, expire_on_commit=False)


def init_database() -> None:
    """
    Initialize database schema.
    
    Creates all tables defined in the ORM models if they don't exist.
    Safe to call multiple times (uses CREATE IF NOT EXISTS).
    """
    engine = get_engine()
    Base.metadata.create_all(engine)
    print("✅ PostgreSQL database schema initialized successfully.")


def get_session() -> Session:
    """
    Get a new database session.
    
    Usage:
        session = get_session()
        try:
            # ... database operations
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    Returns:
        Session: SQLAlchemy session instance
    """
    SessionLocal = get_session_factory()
    return SessionLocal()


# ============================================
# Utility Functions
# ============================================

def create_or_get_genre(session: Session, name: str) -> Genre:
    """
    Get existing genre or create new one.
    
    Args:
        session: Database session
        name: Genre name
        
    Returns:
        Genre: Existing or newly created genre
    """
    genre = session.query(Genre).filter(Genre.name == name).first()
    if not genre:
        genre = Genre(name=name)
        session.add(genre)
        session.flush()  # Get the ID without committing
    return genre
