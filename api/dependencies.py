"""
CineSense API - Dependencies
============================

Dependency injection for database sessions and shared resources.
"""

from typing import Generator

from sqlalchemy.orm import Session

from etl_pipeline.database import get_session


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
