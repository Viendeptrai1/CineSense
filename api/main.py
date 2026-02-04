"""
CineSense API - Main Application
=================================

FastAPI application with semantic search for movie recommendations.

Usage:
    uvicorn api.main:app --reload --port 8000
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger
from sqlalchemy import text

from api import __version__
from api.schemas import HealthResponse
from api import __version__
from api.schemas import HealthResponse
from api.routes import search, movies, auth, social
from etl_pipeline.config import settings
from etl_pipeline.db_postgres import get_session, Movie
from etl_pipeline.config import settings
from etl_pipeline.db_postgres import get_session, Movie
from etl_pipeline.db_qdrant import get_qdrant_client, collection_exists
from etl_pipeline.embedder import get_embedding_model


# ============================================
# Lifespan: Preload models on startup
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan handler.
    
    Startup:
    - Preload embedding model (warm cache)
    - Verify database connections
    
    Shutdown:
    - Cleanup resources
    """
    logger.info("🚀 Starting CineSense API...")
    
    # Preload embedding model (takes a few seconds)
    logger.info("Loading embedding model...")
    try:
        model = get_embedding_model()
        logger.info(f"✅ Embedding model loaded: {settings.embedding.model}")
    except Exception as e:
        logger.error(f"❌ Failed to load embedding model: {e}")
    
    # Verify PostgreSQL connection
    try:
        session = get_session()
        session.execute(text("SELECT 1"))
        session.close()
        logger.info("✅ PostgreSQL connection verified")
    except Exception as e:
        logger.error(f"❌ PostgreSQL connection failed: {e}")
    
    # Verify Qdrant connection
    try:
        if collection_exists():
            logger.info("✅ Qdrant collection verified")
        else:
            logger.warning("⚠️ Qdrant collection not found")
    except Exception as e:
        logger.error(f"❌ Qdrant connection failed: {e}")
    
    logger.info("🎬 CineSense API ready!")
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down CineSense API...")


# ============================================
# FastAPI Application
# ============================================

app = FastAPI(
    title="CineSense API",
    description="""
    🎬 **CineSense** - Semantic Movie Search
    
    Search for movies by "vibe" using natural language in any language.
    
    Examples:
    - `"phim buồn cho ngày mưa"` → melancholic movies
    - `"scary horror movies for Halloween"` → horror films
    - `"feel good movies with happy endings"` → uplifting movies
    
    Powered by multilingual embeddings that understand 
    `"phim kinh dị"` ≈ `"horror movie"`.
    """,
    version=__version__,
    lifespan=lifespan,
)


# ============================================
# CORS Middleware
# ============================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================
# Include Routers
# ============================================

app.include_router(search.router)
app.include_router(movies.router)
app.include_router(auth.router)
app.include_router(social.router)


# ============================================
# Health Check
# ============================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns system status including database connections and statistics.
    """
    postgres_ok = False
    qdrant_ok = False
    movies_count = 0
    vectors_count = 0
    
    # Check PostgreSQL
    try:
        session = get_session()
        movies_count = session.query(Movie).count()
        session.close()
        postgres_ok = True
    except Exception as e:
        logger.error(f"Health check - PostgreSQL error: {e}")
    
    # Check Qdrant
    try:
        client = get_qdrant_client()
        info = client.get_collection(settings.qdrant.collection_name)
        vectors_count = info.points_count
        qdrant_ok = True
    except Exception as e:
        logger.error(f"Health check - Qdrant error: {e}")
    
    return HealthResponse(
        status="healthy" if (postgres_ok and qdrant_ok) else "degraded",
        version=__version__,
        postgres_connected=postgres_ok,
        qdrant_connected=qdrant_ok,
        embedding_model=settings.embedding.model,
        movies_count=movies_count,
        vectors_count=vectors_count,
    )


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API info."""
    return {
        "name": "CineSense API",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
    }
