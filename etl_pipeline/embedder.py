"""
CineSense Text Embedding Module
================================

Handles text preprocessing and embedding generation using Sentence Transformers.

Model: paraphrase-multilingual-MiniLM-L12-v2
- Output: 384-dimensional dense vectors
- Languages: 50+ languages including Vietnamese & English
- Performance: Fast inference, excellent multilingual semantic similarity
- Use case: "phim kinh dị" ≈ "horror movie" cross-lingual search

Text Preprocessing Pipeline (English-first, multilingual safe):
1. Unicode normalization
2. HTML tag removal (BeautifulSoup)
3. URL / email / mention / hashtag removal
4. Emoji & emoticon handling (remove or collapse)
5. Whitespace normalization
6. Lowercase normalization (configurable, default: on)
"""

import re
import unicodedata
from typing import List, Optional

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

_URL_PATTERN = re.compile(
    r"(https?://\S+|www\.\S+)",
    flags=re.IGNORECASE,
)

_EMAIL_PATTERN = re.compile(
    r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b",
    flags=re.IGNORECASE,
)

_MENTION_HASHTAG_PATTERN = re.compile(
    r"(?:(?<!\w)[@#]\w+)",
    flags=re.UNICODE,
)

# Rough emoji / pictograph range matcher – intentionally simple & dependency-free
_EMOJI_PATTERN = re.compile(
    "["  # start character class
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F700-\U0001F77F"
    "\U0001F780-\U0001F7FF"
    "\U0001F800-\U0001F8FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\u2600-\u26FF"          # misc symbols
    "\u2700-\u27BF"          # dingbats
    "]+",
    flags=re.UNICODE,
)

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


def normalize_unicode(text: str) -> str:
    """
    Normalize text to a consistent Unicode form.
    """
    if not text:
        return ""
    return unicodedata.normalize("NFC", text)


def remove_urls_emails_handles(text: str) -> str:
    """
    Remove URLs, emails, mentions (@user) and hashtags (#tag).
    """
    if not text:
        return ""

    text = _URL_PATTERN.sub(" ", text)
    text = _EMAIL_PATTERN.sub(" ", text)
    text = _MENTION_HASHTAG_PATTERN.sub(" ", text)
    return text


def remove_emojis(text: str) -> str:
    """
    Remove emoji and common pictographs.

    We keep it conservative to avoid touching alphabetic characters
    in multilingual text.
    """
    if not text:
        return ""
    return _EMOJI_PATTERN.sub(" ", text)


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
    remove_urls_and_emails: bool = True,
    remove_emoji: bool = True,
    normalize_unicode_flag: bool = True,
) -> str:
    """
    Full text preprocessing pipeline.
    
    Pipeline steps:
    1. Unicode normalization (optional)
    2. HTML removal (optional)
    3. URL/email/mention/hashtag removal (optional)
    4. Emoji removal (optional)
    5. Whitespace normalization (optional)
    6. Lowercase conversion (optional)
    
    Args:
        text: Input text to preprocess
        lowercase: Whether to convert to lowercase
        remove_html: Whether to remove HTML tags
        normalize_ws: Whether to normalize whitespace
        remove_urls_and_emails: Whether to strip URLs, emails, @handles and #hashtags
        remove_emoji: Whether to strip emoji / pictographs
        normalize_unicode_flag: Whether to normalize Unicode (NFC)
        
    Returns:
        Preprocessed text ready for embedding
        
    Example:
        >>> preprocess_text("<p>Great Movie!</p>  Loved it.")
        "great movie! loved it."
    """
    if not text:
        return ""

    # Step 0: Unicode normalization
    if normalize_unicode_flag:
        text = normalize_unicode(text)

    # Step 1: Remove HTML
    if remove_html:
        text = clean_html(text)

    # Step 2: Remove URLs / emails / mentions / hashtags
    if remove_urls_and_emails:
        text = remove_urls_emails_handles(text)

    # Step 3: Remove emoji
    if remove_emoji:
        text = remove_emojis(text)

    # Step 4: Normalize whitespace
    if normalize_ws:
        text = normalize_whitespace(text)

    # Step 5: Lowercase
    if lowercase:
        text = text.lower()
    
    return text


def is_noisy_review(
    text: str,
    min_chars: int = 20,
    min_alpha_ratio: float = 0.3,
    min_alpha_tokens: int = 3,
) -> bool:
    """
    Heuristic to detect reviews that are essentially noise.

    Examples: strings dominated by dots, punctuation or repeated patterns like
    "... ... ...", with very few alphabetic characters.

    Args:
        text: Raw review text (will be minimally stripped before checks)
        min_chars: Minimum length (after strip) to be considered meaningful
        min_alpha_ratio: Minimum ratio of alphabetic characters to total length
        min_alpha_tokens: Minimum number of alphabetic tokens required

    Returns:
        True if the review should be treated as noise and skipped.
    """
    if not text:
        return True

    raw = (text or "").strip()
    if len(raw) < min_chars:
        return True

    # Work on a lightly preprocessed version (no HTML/URLs/emoji)
    cleaned = preprocess_text(
        raw,
        lowercase=True,
        remove_html=True,
        normalize_ws=True,
        remove_urls_and_emails=True,
        remove_emoji=True,
        normalize_unicode_flag=True,
    )

    if not cleaned:
        return True

    total_len = len(cleaned)
    alpha_count = sum(ch.isalpha() for ch in cleaned)
    if total_len == 0:
        return True

    alpha_ratio = alpha_count / total_len
    if alpha_ratio < min_alpha_ratio:
        return True

    tokens = [tok for tok in cleaned.split() if tok.isalpha()]
    if len(tokens) < min_alpha_tokens:
        return True

    return False


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
        int: Embedding dimension (384 for paraphrase-multilingual-MiniLM-L12-v2)
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
