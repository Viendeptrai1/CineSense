"""
CineSense Text Embedding Module
================================

Handles text preprocessing and embedding generation using Sentence Transformers.

Model: paraphrase-multilingual-MiniLM-L12-v2
- Output: 384-dimensional dense vectors
- Languages: 50+ languages including Vietnamese & English
- Performance: Fast inference, excellent multilingual semantic similarity
- Use case: "phim kinh dị" ≈ "horror movie" cross-lingual search

Text Preprocessing Pipeline:
1. HTML tag removal (BeautifulSoup)
2. Lowercase normalization
3. Whitespace normalization
4. Optional: Stopword removal (configurable)
"""

import re
from typing import List, Optional, Union

import numpy as np
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer

from .config import settings


# ============================================
# Model Singleton
# ============================================

_model: Optional[SentenceTransformer] = None


def get_embedding_model() -> SentenceTransformer:
    """
    Get or create Sentence Transformer model singleton.
    
    Lazy loading to avoid memory usage when not needed.
    Model is cached after first load.
    
    Returns:
        SentenceTransformer: Loaded embedding model
    """
    global _model
    if _model is None:
        print(f"🔄 Loading embedding model: {settings.embedding.model}")
        _model = SentenceTransformer(settings.embedding.model)
        print(f"✅ Model loaded. Output dimension: {_model.get_sentence_embedding_dimension()}")
    return _model


# ============================================
# Text Preprocessing
# ============================================

def clean_html(text: str) -> str:
    """
    Remove HTML tags from text.
    
    Uses BeautifulSoup for robust HTML parsing.
    
    Args:
        text: Input text potentially containing HTML
        
    Returns:
        Clean text without HTML tags
    """
    if not text:
        return ""
    
    # Parse HTML and extract text
    soup = BeautifulSoup(text, "lxml")
    
    # Remove script and style elements
    for element in soup(["script", "style"]):
        element.decompose()
    
    # Get text content
    clean = soup.get_text(separator=" ")
    
    return clean


def normalize_whitespace(text: str) -> str:
    """
    Normalize whitespace in text.
    
    - Replaces multiple spaces with single space
    - Removes leading/trailing whitespace
    - Handles newlines and tabs
    
    Args:
        text: Input text
        
    Returns:
        Text with normalized whitespace
    """
    if not text:
        return ""
    
    # Replace newlines and tabs with spaces
    text = re.sub(r"[\n\t\r]+", " ", text)
    
    # Replace multiple spaces with single space
    text = re.sub(r"\s+", " ", text)
    
    # Strip leading/trailing whitespace
    return text.strip()


def preprocess_text(
    text: str,
    lowercase: bool = True,
    remove_html: bool = True,
    normalize_ws: bool = True,
) -> str:
    """
    Full text preprocessing pipeline.
    
    Pipeline steps:
    1. HTML removal (optional)
    2. Whitespace normalization (optional)
    3. Lowercase conversion (optional)
    
    Args:
        text: Input text to preprocess
        lowercase: Whether to convert to lowercase
        remove_html: Whether to remove HTML tags
        normalize_ws: Whether to normalize whitespace
        
    Returns:
        Preprocessed text ready for embedding
        
    Example:
        >>> preprocess_text("<p>Great Movie!</p>  Loved it.")
        "great movie! loved it."
    """
    if not text:
        return ""
    
    # Step 1: Remove HTML
    if remove_html:
        text = clean_html(text)
    
    # Step 2: Normalize whitespace
    if normalize_ws:
        text = normalize_whitespace(text)
    
    # Step 3: Lowercase
    if lowercase:
        text = text.lower()
    
    return text


# ============================================
# Embedding Generation
# ============================================

def embed_text(text: str, preprocess: bool = True) -> List[float]:
    """
    Generate embedding vector for a single text.
    
    Args:
        text: Input text to embed
        preprocess: Whether to apply preprocessing
        
    Returns:
        384-dimensional embedding vector as list of floats
    """
    model = get_embedding_model()
    
    if preprocess:
        text = preprocess_text(text)
    
    # Generate embedding
    # Returns numpy array of shape (384,)
    embedding = model.encode(text, convert_to_numpy=True)
    
    # Convert to list for JSON serialization
    return embedding.tolist()


def embed_texts(
    texts: List[str],
    preprocess: bool = True,
    batch_size: int = 32,
    show_progress: bool = True,
) -> List[List[float]]:
    """
    Generate embeddings for multiple texts.
    
    Uses batched processing for efficiency.
    
    Args:
        texts: List of input texts
        preprocess: Whether to apply preprocessing
        batch_size: Batch size for encoding
        show_progress: Whether to show progress bar
        
    Returns:
        List of 384-dimensional embedding vectors
        
    Example:
        >>> reviews = ["Great film!", "Terrible acting."]
        >>> vectors = embed_texts(reviews)
        >>> len(vectors[0])
        384
    """
    if not texts:
        return []
    
    model = get_embedding_model()
    
    # Preprocess all texts
    if preprocess:
        texts = [preprocess_text(t) for t in texts]
    
    # Generate embeddings in batches
    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=show_progress,
        convert_to_numpy=True,
    )
    
    # Convert numpy array to list of lists
    return embeddings.tolist()


def get_embedding_dimension() -> int:
    """
    Get the dimension of embedding vectors.
    
    Returns:
        int: Embedding dimension (384 for all-MiniLM-L6-v2)
    """
    model = get_embedding_model()
    return model.get_sentence_embedding_dimension()


# ============================================
# Utility Functions
# ============================================

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """
    Compute cosine similarity between two vectors.
    
    Args:
        vec1: First embedding vector
        vec2: Second embedding vector
        
    Returns:
        Cosine similarity score (-1 to 1)
    """
    v1 = np.array(vec1)
    v2 = np.array(vec2)
    
    dot_product = np.dot(v1, v2)
    norm_product = np.linalg.norm(v1) * np.linalg.norm(v2)
    
    if norm_product == 0:
        return 0.0
    
    return float(dot_product / norm_product)
