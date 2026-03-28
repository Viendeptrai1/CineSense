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
from api.routes import movies, recommendations, absa as absa_routes
from etl_pipeline.database import get_session, CoreMovie


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
    
    try:
        session = get_session()
        session.execute(text("SELECT 1"))
        session.close()
        logger.info("✅ Database connection verified")
    except Exception as e:
        logger.error(f"❌ Database connection failed: {e}")
    
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
    Discovery-first API for browsing the English movie catalog (SQLite by default).

    Current scope:
    - paginated movie discovery
    - SQL database as the source of truth
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
app.include_router(absa_routes.router)


# ============================================
# Health Check
# ============================================

@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check() -> HealthResponse:
    """
    Health check endpoint.
    
    Returns system status including database connections and statistics.
    """
    db_ok = False
    movies_count = 0
    
    try:
        session = get_session()
        movies_count = session.query(CoreMovie).count()
        session.close()
        db_ok = True
    except Exception as e:
        logger.error(f"Health check - database error: {e}")
    
    return HealthResponse(
        status="healthy" if db_ok else "degraded",
        version=__version__,
        database_connected=db_ok,
        movies_count=movies_count,
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
