"""
CineSense ETL Pipeline
=======================

A data engineering module for extracting, transforming, and loading
movie review data for semantic search capabilities.

Components:
- config: Configuration management (Pydantic Settings)
- db_postgres: SQLAlchemy models and PostgreSQL connection
- db_qdrant: Qdrant vector database operations
- embedder: Sentence Transformer embedding logic
- main: ETL orchestration script
"""

__version__ = "0.1.0"
__author__ = "CineSense Team"
