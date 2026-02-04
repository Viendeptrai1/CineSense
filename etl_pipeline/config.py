"""
CineSense Configuration Module
==============================

Uses Pydantic Settings for type-safe configuration management.
Loads settings from environment variables with .env file support.
"""

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PostgresSettings(BaseSettings):
    """PostgreSQL connection configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix="POSTGRES_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    host: str = Field(default="localhost", description="PostgreSQL host")
    port: int = Field(default=5432, description="PostgreSQL port")
    user: str = Field(default="cinesense", description="Database user")
    password: str = Field(default="cinesense_secret", description="Database password")
    db: str = Field(default="cinesense_db", description="Database name")
    
    @property
    def database_url(self) -> str:
        """Generate SQLAlchemy connection string using psycopg (v3) driver."""
        return f"postgresql+psycopg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"
    
    @property
    def async_database_url(self) -> str:
        """Generate async SQLAlchemy connection string."""
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.db}"


class QdrantSettings(BaseSettings):
    """Qdrant vector database configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix="QDRANT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    host: str = Field(default="localhost", description="Qdrant host")
    port: int = Field(default=6333, description="Qdrant REST API port")
    grpc_port: int = Field(default=6334, description="Qdrant gRPC port")
    collection_name: str = Field(default="movie_reviews", description="Collection name")


class EmbeddingSettings(BaseSettings):
    """Embedding model configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix="EMBEDDING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # paraphrase-multilingual-MiniLM-L12-v2: 384-dim vectors with multilingual support
    # Enables semantic search in Vietnamese & English ("phim kinh dị" ≈ "horror movie")
    model: str = Field(default="paraphrase-multilingual-MiniLM-L12-v2", description="Sentence Transformer model")
    dimension: int = Field(default=384, description="Embedding vector dimension")


class ETLSettings(BaseSettings):
    """ETL pipeline configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    batch_size: int = Field(default=32, description="Batch size for processing")
    log_level: str = Field(default="INFO", description="Logging level")


class TMDBSettings(BaseSettings):
    """TMDB API configuration for data ingestion."""
    
    model_config = SettingsConfigDict(
        env_prefix="TMDB_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    api_key: str = Field(default="", description="TMDB API key")
    base_url: str = Field(default="https://api.themoviedb.org/3", description="TMDB API base URL")
    language: str = Field(default="vi-VN", description="Language for metadata (Vietnamese)")
    pages_to_fetch: int = Field(default=50, description="Number of pages to fetch (20 movies/page)")
    
    @property
    def headers(self) -> dict:
        """Get authorization headers for TMDB API requests."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }


class Settings(BaseSettings):
    """Aggregated application settings."""
    
    postgres: PostgresSettings = Field(default_factory=PostgresSettings)
    qdrant: QdrantSettings = Field(default_factory=QdrantSettings)
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    etl: ETLSettings = Field(default_factory=ETLSettings)
    tmdb: TMDBSettings = Field(default_factory=TMDBSettings)


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached application settings.
    
    Uses LRU cache to avoid reloading settings on every call.
    
    Returns:
        Settings: Application configuration instance
    """
    return Settings()


# Convenience access
settings = get_settings()
