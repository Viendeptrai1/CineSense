"""
CineSense Configuration Module
==============================

Uses Pydantic Settings for type-safe configuration management.
Loads settings from environment variables with .env file support.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class EmbeddingSettings(BaseSettings):
    """Embedding model configuration."""
    
    model_config = SettingsConfigDict(
        env_prefix="EMBEDDING_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )
    
    # Default: all-MiniLM-L6-v2 — compact English sentence embeddings (384-dim)
    # Matches the English-first retrieval fine-tuning pipeline in Notebook_Report.
    model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Sentence Transformer model for ETL/embedder utilities",
    )
    dimension: int = Field(
        default=384,
        description="Embedding vector dimension (must match the selected model)",
    )


class AbsaSettings(BaseSettings):
    """Aspect-Based Sentiment Analysis model configuration."""

    model_config = SettingsConfigDict(
        env_prefix="ABSA_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Backbone encoder for ABSA classifier (English-only)
    model_name: str = Field(
        default="roberta-base",
        description="HF model name for ABSA backbone (e.g., roberta-base, bert-base-uncased)",
    )


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
    language: str = Field(default="en-US", description="Language for metadata (English)")
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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="sqlite:///./data/cinesense.db",
        description="SQLite file URL for SQLAlchemy (e.g. sqlite:///./data/cinesense.db)",
    )
    embedding: EmbeddingSettings = Field(default_factory=EmbeddingSettings)
    etl: ETLSettings = Field(default_factory=ETLSettings)
    tmdb: TMDBSettings = Field(default_factory=TMDBSettings)
    absa: AbsaSettings = Field(default_factory=AbsaSettings)


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
