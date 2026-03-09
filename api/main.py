"""
CineSense API - Main Application
=================================

FastAPI application for discovery and artifact-based recommendations.

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
from api.routes import movies, recommendations
from etl_pipeline.db_postgres import get_session, CoreMovie


# ============================================
# Lifespan: Preload models on startup
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """
    Application lifespan handler.
    
    Startup:
    - Verify database connections
    
    Shutdown:
    - Cleanup resources
    """
    logger.info("🚀 Starting CineSense API...")
    
    # Verify PostgreSQL connection
    try:
        session = get_session()
        session.execute(text("SELECT 1"))
        session.close()
        logger.info("✅ PostgreSQL connection verified")
    except Exception as e:
        logger.error(f"❌ PostgreSQL connection failed: {e}")
    
    # NOTE: Qdrant/Embedding disabled — will be re-enabled after custom model training
    logger.warning("⚠️ Semantic search disabled (Qdrant not configured)")
    
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
    Discovery-first API for browsing the English movie catalog stored in PostgreSQL.

    Current scope:
    - paginated movie discovery
    - PostgreSQL as the source of truth
    - recommendation routes powered by offline training artifacts
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

app.include_router(movies.router)
app.include_router(recommendations.router)


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
    movies_count = 0
    
    # Check PostgreSQL
    try:
        session = get_session()
        movies_count = session.query(CoreMovie).count()
        session.close()
        postgres_ok = True
    except Exception as e:
        logger.error(f"Health check - PostgreSQL error: {e}")
    
    return HealthResponse(
        status="healthy" if postgres_ok else "degraded",
        version=__version__,
        postgres_connected=postgres_ok,
        qdrant_connected=False,  # Disabled until custom model is trained
        embedding_model="disabled",
        movies_count=movies_count,
        vectors_count=0,
    )


@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API info."""
    return {
        "name": "CineSense API",
        "version": __version__,
        "docs": "/docs",
        "health": "/health",
        "mode": "discovery+recommendation-artifacts",
    }
