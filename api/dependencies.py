"""
CineSense API - Dependencies
============================

Dependency injection for database sessions and shared resources.
"""

from typing import Generator

from sqlalchemy.orm import Session

from etl_pipeline.db_postgres import get_session
from etl_pipeline.db_qdrant import get_qdrant_client
from etl_pipeline.embedder import get_embedding_model


def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency.
    
    Yields a SQLAlchemy session and ensures proper cleanup.
    
    Usage:
        @app.get("/movies")
        def list_movies(db: Session = Depends(get_db)):
            ...
    """
    session = get_session()
    try:
        yield session
    finally:
        session.close()


def get_qdrant():
    """
    Qdrant client dependency.
    
    Returns the Qdrant client singleton.
    """
    return get_qdrant_client()


def get_embedder():
    """
    Embedding model dependency.
    
    Returns the Sentence Transformer model singleton.
    Lazy-loaded on first request.
    """
    return get_embedding_model()
