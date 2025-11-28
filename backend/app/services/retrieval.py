"""Retrieval service for finding relevant transcript chunks using FAISS."""

import logging

import faiss
import numpy as np

from app.services.chunking import TranscriptChunk
from app.services.embeddings import EMBEDDING_DIMENSION, generate_query_embedding

logger = logging.getLogger(__name__)


def retrieve_relevant_chunks(
    query: str,
    chunks: list[TranscriptChunk],
    embeddings: np.ndarray,
    top_k: int = 10,
) -> list[TranscriptChunk]:
    """
    Retrieve the most relevant chunks for a query.

    Args:
        query: Search query text
        chunks: List of TranscriptChunk objects
        embeddings: numpy array of embeddings (shape: len(chunks), EMBEDDING_DIMENSION)
        top_k: Number of chunks to retrieve

    Returns:
        List of most relevant TranscriptChunk objects, sorted by relevance
    """
    if not chunks or len(embeddings) == 0:
        return []

    if len(chunks) != len(embeddings):
        raise ValueError(
            f"Chunks ({len(chunks)}) and embeddings ({len(embeddings)}) count mismatch"
        )

    k = min(top_k, len(chunks))

    index = faiss.IndexFlatL2(EMBEDDING_DIMENSION)
    index.add(embeddings.astype(np.float32))

    query_embedding = generate_query_embedding(query)
    query_embedding = query_embedding.reshape(1, -1)

    distances, indices = index.search(query_embedding, k)

    results = []
    for idx in indices[0]:
        if 0 <= idx < len(chunks):
            results.append(chunks[idx])

    return results


def build_context_from_chunks(
    chunks: list[TranscriptChunk],
    max_tokens: int = 4000,
) -> str:
    """
    Build context string from retrieved chunks.

    Args:
        chunks: List of relevant TranscriptChunk objects (already sorted by relevance)
        max_tokens: Maximum total tokens to include

    Returns:
        Formatted context string with timestamps
    """
    if not chunks:
        return ""

    context_parts = []
    total_tokens = 0

    for chunk in chunks:
        if total_tokens + chunk.token_count > max_tokens:
            break

        if chunk.start_time > 0 or chunk.end_time > 0:
            timestamp = _format_timestamp(chunk.start_time)
            context_parts.append(f"[{timestamp}] {chunk.text}")
        else:
            context_parts.append(chunk.text)

        total_tokens += chunk.token_count

    return "\n\n".join(context_parts)


def _format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS or MM:SS."""
    total_seconds = int(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    secs = total_seconds % 60

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"
