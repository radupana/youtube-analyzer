"""RAG service for processing and retrieving video transcript content."""

import logging

import numpy as np
from sqlmodel import Session, select

from app.db.database import get_engine
from app.db.models import Chunk
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
    Process a transcript: chunk it, generate embeddings, and store in database.

    Args:
        video_id: YouTube video ID
        transcript: Full transcript text
        segments: Optional list of transcript segments with timestamps
        chunk_size: Target tokens per chunk
        overlap: Token overlap between chunks

    Returns:
        True if processing succeeded
    """
    if has_rag_data(video_id):
        logger.info(f"Chunks already exist for {video_id}")
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

    with Session(get_engine()) as db:
        for i, chunk in enumerate(chunks):
            db_chunk = Chunk(
                id=chunk.id,
                video_id=video_id,
                text=chunk.text,
                start_time=chunk.start_time,
                end_time=chunk.end_time,
                token_count=chunk.token_count,
                embedding=embeddings[i].tobytes(),
            )
            db.add(db_chunk)
        db.commit()

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
    if not video_ids:
        return ""

    all_chunks: list[TranscriptChunk] = []
    all_embeddings: list[np.ndarray] = []

    with Session(get_engine()) as db:
        for video_id in video_ids:
            db_chunks = db.exec(select(Chunk).where(Chunk.video_id == video_id)).all()

            if not db_chunks:
                logger.warning(f"No chunks found for {video_id}")
                continue

            for db_chunk in db_chunks:
                chunk = TranscriptChunk(
                    id=db_chunk.id,
                    video_id=db_chunk.video_id,
                    text=db_chunk.text,
                    start_time=db_chunk.start_time,
                    end_time=db_chunk.end_time,
                    token_count=db_chunk.token_count,
                )
                all_chunks.append(chunk)
                embedding = np.frombuffer(db_chunk.embedding, dtype=np.float32)
                all_embeddings.append(embedding)

    if not all_chunks:
        return ""

    combined_embeddings = np.vstack(all_embeddings)

    relevant_chunks = retrieve_relevant_chunks(
        query, all_chunks, combined_embeddings, top_k
    )

    return build_context_from_chunks(relevant_chunks, max_tokens)


def has_rag_data(video_id: str) -> bool:
    """Check if RAG data (chunks/embeddings) exists for a video."""
    with Session(get_engine()) as db:
        chunk = db.exec(
            select(Chunk).where(Chunk.video_id == video_id).limit(1)
        ).first()
        return chunk is not None
