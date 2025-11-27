"""Embedding service for generating vector representations of text."""

import logging

import numpy as np
from sentence_transformers import SentenceTransformer

from app.services.chunking import TranscriptChunk

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None
MODEL_NAME = "all-MiniLM-L6-v2"
EMBEDDING_DIMENSION = 384


def get_model() -> SentenceTransformer:
    """Get or initialize the sentence transformer model."""
    global _model
    if _model is None:
        logger.info(f"Loading embedding model: {MODEL_NAME}")
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def generate_embeddings(texts: list[str]) -> np.ndarray:
    """
    Generate embeddings for a list of texts.

    Args:
        texts: List of text strings to embed

    Returns:
        numpy array of shape (len(texts), EMBEDDING_DIMENSION)
    """
    if not texts:
        return np.array([], dtype=np.float32).reshape(0, EMBEDDING_DIMENSION)

    model = get_model()
    embeddings = model.encode(texts, convert_to_numpy=True)
    return embeddings.astype(np.float32)


def generate_chunk_embeddings(
    chunks: list[TranscriptChunk],
) -> list[tuple[TranscriptChunk, np.ndarray]]:
    """
    Generate embeddings for transcript chunks.

    Args:
        chunks: List of TranscriptChunk objects

    Returns:
        List of (chunk, embedding) tuples
    """
    if not chunks:
        return []

    texts = [chunk.text for chunk in chunks]
    embeddings = generate_embeddings(texts)

    return list(zip(chunks, embeddings, strict=True))


def generate_query_embedding(query: str) -> np.ndarray:
    """
    Generate embedding for a search query.

    Args:
        query: Search query text

    Returns:
        numpy array of shape (EMBEDDING_DIMENSION,)
    """
    model = get_model()
    embedding = model.encode([query], convert_to_numpy=True)
    return embedding[0].astype(np.float32)
