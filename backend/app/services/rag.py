"""RAG service for processing and retrieving video transcript content."""

import logging

import numpy as np

from app.services.cache import get_cache_service
from app.services.chunking import (
    TranscriptChunk,
    TranscriptSegment,
    chunk_transcript,
    chunk_transcript_simple,
)
from app.services.embeddings import generate_embeddings
from app.services.retrieval import build_context_from_chunks, retrieve_relevant_chunks

logger = logging.getLogger(__name__)


def process_transcript_for_rag(
    video_id: str,
    transcript: str,
    segments: list[TranscriptSegment] | None = None,
    chunk_size: int = 500,
    overlap: int = 50,
) -> bool:
    """
    Process a transcript: chunk it, generate embeddings, and cache.

    Args:
        video_id: YouTube video ID
        transcript: Full transcript text
        segments: Optional list of transcript segments with timestamps
        chunk_size: Target tokens per chunk
        overlap: Token overlap between chunks

    Returns:
        True if processing succeeded
    """
    cache = get_cache_service()

    if cache.has_chunks(video_id):
        logger.info(f"Chunks already cached for {video_id}")
        return True

    if not transcript.strip():
        logger.warning(f"Empty transcript for {video_id}")
        return False

    if segments:
        chunks = chunk_transcript(segments, video_id, chunk_size, overlap)
    else:
        chunks = chunk_transcript_simple(transcript, video_id, chunk_size, overlap)

    if not chunks:
        logger.warning(f"No chunks generated for {video_id}")
        return False

    texts = [chunk.text for chunk in chunks]
    embeddings = generate_embeddings(texts)

    chunks_data = [
        {
            "id": chunk.id,
            "video_id": chunk.video_id,
            "text": chunk.text,
            "start_time": chunk.start_time,
            "end_time": chunk.end_time,
            "token_count": chunk.token_count,
        }
        for chunk in chunks
    ]

    cache.save_chunks(video_id, chunks_data, embeddings)
    logger.info(f"Processed {len(chunks)} chunks for {video_id}")
    return True


def retrieve_context_for_query(
    query: str,
    video_ids: list[str],
    top_k: int = 10,
    max_tokens: int = 4000,
) -> str:
    """
    Retrieve relevant context for a query from multiple videos.

    Args:
        query: User's question
        video_ids: List of video IDs to search
        top_k: Number of chunks to retrieve per video
        max_tokens: Maximum tokens in returned context

    Returns:
        Formatted context string with relevant chunks
    """
    cache = get_cache_service()

    all_chunks: list[TranscriptChunk] = []
    all_embeddings: list[np.ndarray] = []

    for video_id in video_ids:
        cached = cache.load_chunks(video_id)
        if not cached:
            logger.warning(f"No chunks found for {video_id}")
            continue

        chunks_data, embeddings = cached

        for chunk_dict in chunks_data:
            chunk = TranscriptChunk(
                id=chunk_dict["id"],
                video_id=chunk_dict["video_id"],
                text=chunk_dict["text"],
                start_time=chunk_dict["start_time"],
                end_time=chunk_dict["end_time"],
                token_count=chunk_dict["token_count"],
            )
            all_chunks.append(chunk)

        all_embeddings.append(embeddings)

    if not all_chunks:
        return ""

    combined_embeddings = np.vstack(all_embeddings)

    relevant_chunks = retrieve_relevant_chunks(
        query, all_chunks, combined_embeddings, top_k
    )

    return build_context_from_chunks(relevant_chunks, max_tokens)


def has_rag_data(video_id: str) -> bool:
    """Check if RAG data (chunks/embeddings) exists for a video."""
    cache = get_cache_service()
    return cache.has_chunks(video_id)
