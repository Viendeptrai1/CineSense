"""
CineSense ETL Pipeline
=======================

A data engineering module for extracting, transforming, and loading
movie review data for semantic search capabilities.

Components:
- config: Configuration management (Pydantic Settings)
- database: SQLAlchemy models and SQLite connection
- embedder: Sentence Transformer embedding logic
- main: ETL orchestration script
"""

__version__ = "0.1.0"
__author__ = "CineSense Team"
