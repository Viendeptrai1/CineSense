"""
CineSense Qdrant Vector Database Module
========================================

Manages Qdrant collection for semantic search on movie reviews.

Architecture Notes:
- Each REVIEW is stored as a separate vector point (not aggregated per movie)
- This allows fine-grained semantic search matching specific sentiments
- Payload includes movie_id for joining back to PostgreSQL

Vector Configuration:
- Model: all-MiniLM-L6-v2
- Dimension: 384
- Distance: Cosine Similarity (normalized dot product)
"""

from typing import List, Dict, Any, Optional
from uuid import UUID

from qdrant_client import QdrantClient
from qdrant_client.http import models as qdrant_models
from qdrant_client.http.exceptions import UnexpectedResponse

from .config import settings


# ============================================
# Qdrant Client Singleton
# ============================================

_client: Optional[QdrantClient] = None


def get_qdrant_client() -> QdrantClient:
    """
    Get or create Qdrant client singleton.
    
    Returns:
        QdrantClient: Connected Qdrant client instance
    """
    global _client
    if _client is None:
        _client = QdrantClient(
            host=settings.qdrant.host,
            port=settings.qdrant.port,
            timeout=30,  # 30 second timeout
        )
    return _client


# ============================================
# Collection Management
# ============================================

def collection_exists(collection_name: Optional[str] = None) -> bool:
    """
    Check if collection exists in Qdrant.
    
    Args:
        collection_name: Name of collection (defaults to config value)
        
    Returns:
        bool: True if collection exists
    """
    client = get_qdrant_client()
    name = collection_name or settings.qdrant.collection_name
    
    try:
        client.get_collection(name)
        return True
    except UnexpectedResponse:
        return False


def create_collection(
    collection_name: Optional[str] = None,
    vector_size: Optional[int] = None,
    recreate: bool = False
) -> None:
    """
    Create Qdrant collection for movie reviews.
    
    Collection Configuration:
    - Vectors: 384 dimensions (all-MiniLM-L6-v2)
    - Distance: Cosine similarity
    - Optimizers: Default settings with indexing threshold
    
    Payload Schema:
    - movie_id (str): UUID of the movie in PostgreSQL
    - rating (float): Review rating (1-10)
    - year (int): Movie release year
    - genre_ids (list[int]): List of genre IDs
    - source (str): Review source
    
    Args:
        collection_name: Name for the collection
        vector_size: Vector dimension (default: 384)
        recreate: If True, delete existing collection first
    """
    client = get_qdrant_client()
    name = collection_name or settings.qdrant.collection_name
    size = vector_size or settings.embedding.dimension
    
    # Handle recreation
    if recreate and collection_exists(name):
        print(f"🗑️  Deleting existing collection: {name}")
        client.delete_collection(name)
    
    # Check if already exists
    if collection_exists(name):
        print(f"ℹ️  Collection '{name}' already exists. Skipping creation.")
        return
    
    # Create collection with optimized settings
    client.create_collection(
        collection_name=name,
        vectors_config=qdrant_models.VectorParams(
            size=size,
            distance=qdrant_models.Distance.COSINE,
        ),
        # Optional: Add payload indexing for filtered search
        # This enables efficient filtering by year, rating, etc.
        optimizers_config=qdrant_models.OptimizersConfigDiff(
            indexing_threshold=10000,  # Start indexing after 10k points
        ),
    )
    
    # Create payload indexes for common filter fields
    # This optimizes queries like: "sad movies from 2020s"
    _create_payload_indexes(client, name)
    
    print(f"✅ Created Qdrant collection: {name} (dim={size}, distance=COSINE)")


def _create_payload_indexes(client: QdrantClient, collection_name: str) -> None:
    """
    Create payload field indexes for efficient filtering.
    
    Indexes:
    - year: Integer index for release year filtering
    - rating: Float index for rating filtering
    - genre_ids: Keyword index for genre filtering
    """
    # Year index (integer)
    client.create_payload_index(
        collection_name=collection_name,
        field_name="year",
        field_schema=qdrant_models.PayloadSchemaType.INTEGER,
    )
    
    # Rating index (float)
    client.create_payload_index(
        collection_name=collection_name,
        field_name="rating",
        field_schema=qdrant_models.PayloadSchemaType.FLOAT,
    )
    
    # Genre IDs index (keyword for array membership)
    client.create_payload_index(
        collection_name=collection_name,
        field_name="genre_ids",
        field_schema=qdrant_models.PayloadSchemaType.KEYWORD,
    )
    
    print("✅ Created payload indexes: year, rating, genre_ids")


# ============================================
# Vector Operations
# ============================================

def upsert_review_vectors(
    review_data: List[Dict[str, Any]],
    collection_name: Optional[str] = None,
) -> None:
    """
    Upsert review vectors to Qdrant.
    
    Each item in review_data should contain:
    - id (str): Unique point ID (review UUID as string)
    - vector (list[float]): 384-dim embedding vector
    - payload (dict): Metadata including movie_id, rating, year, etc.
    
    Args:
        review_data: List of review vector dictionaries
        collection_name: Target collection name
    """
    if not review_data:
        print("⚠️  No review vectors to upsert.")
        return
    
    client = get_qdrant_client()
    name = collection_name or settings.qdrant.collection_name
    
    # Convert to Qdrant PointStruct format
    points = [
        qdrant_models.PointStruct(
            id=item["id"],
            vector=item["vector"],
            payload=item["payload"],
        )
        for item in review_data
    ]
    
    # Upsert in batches (Qdrant handles batching internally)
    client.upsert(
        collection_name=name,
        points=points,
        wait=True,  # Wait for indexing
    )
    
    print(f"✅ Upserted {len(points)} review vectors to Qdrant.")


def search_similar_reviews(
    query_vector: List[float],
    limit: int = 10,
    score_threshold: float = 0.5,
    filter_conditions: Optional[qdrant_models.Filter] = None,
    collection_name: Optional[str] = None,
) -> List[qdrant_models.ScoredPoint]:
    """
    Search for semantically similar reviews.
    
    Args:
        query_vector: 384-dim query embedding
        limit: Maximum number of results
        score_threshold: Minimum similarity score (0-1)
        filter_conditions: Optional Qdrant filter for metadata
        collection_name: Target collection name
        
    Returns:
        List of ScoredPoint with id, score, and payload
    """
    client = get_qdrant_client()
    name = collection_name or settings.qdrant.collection_name
    
    results = client.search(
        collection_name=name,
        query_vector=query_vector,
        limit=limit,
        score_threshold=score_threshold,
        query_filter=filter_conditions,
    )
    
    return results


def get_collection_info(collection_name: Optional[str] = None) -> Dict[str, Any]:
    """
    Get collection statistics and configuration.
    
    Returns:
        Dict with vectors_count, points_count, and config info
    """
    client = get_qdrant_client()
    name = collection_name or settings.qdrant.collection_name
    
    info = client.get_collection(name)
    
    return {
        "name": name,
        "vectors_count": info.vectors_count,
        "points_count": info.points_count,
        "status": info.status.value,
        "vector_size": info.config.params.vectors.size,
        "distance": info.config.params.vectors.distance.value,
    }


# ============================================
# Initialization
# ============================================

def init_qdrant() -> None:
    """
    Initialize Qdrant collection.
    
    Safe to call multiple times - will skip if collection exists.
    """
    create_collection()
