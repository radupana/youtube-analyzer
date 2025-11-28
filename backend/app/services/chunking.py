"""Chunking service for splitting transcripts into retrievable segments."""

from dataclasses import dataclass
from typing import TypedDict

import tiktoken


class SegmentData(TypedDict):
    text: str
    tokens: list[int]
    start: float
    end: float


@dataclass
class TranscriptSegment:
    """A segment from the raw YouTube transcript with timestamp."""

    text: str
    start: float
    duration: float


@dataclass
class TranscriptChunk:
    """A chunk of transcript text optimized for retrieval."""

    id: str
    video_id: str
    text: str
    start_time: float
    end_time: float
    token_count: int


def chunk_transcript(
    segments: list[TranscriptSegment],
    video_id: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[TranscriptChunk]:
    """
    Split transcript segments into chunks suitable for embedding and retrieval.

    Args:
        segments: List of transcript segments with timestamps
        video_id: YouTube video ID
        chunk_size: Target token count per chunk
        overlap: Token overlap between consecutive chunks

    Returns:
        List of TranscriptChunk objects with preserved timestamps
    """
    if not segments:
        return []

    encoding = tiktoken.get_encoding("cl100k_base")

    segment_data: list[SegmentData] = []
    for seg in segments:
        tokens = encoding.encode(seg.text)
        segment_data.append(
            {
                "text": seg.text,
                "tokens": tokens,
                "start": seg.start,
                "end": seg.start + seg.duration,
            }
        )

    chunks: list[TranscriptChunk] = []
    current_tokens: list[int] = []
    current_start: float | None = None
    current_end: float = 0.0
    seg_idx = 0

    while seg_idx < len(segment_data):
        seg_data = segment_data[seg_idx]

        if current_start is None:
            current_start = seg_data["start"]

        current_tokens.extend(seg_data["tokens"])
        current_end = seg_data["end"]

        if len(current_tokens) >= chunk_size:
            chunk_text = encoding.decode(current_tokens)
            chunks.append(
                TranscriptChunk(
                    id=f"{video_id}_{len(chunks)}",
                    video_id=video_id,
                    text=chunk_text,
                    start_time=current_start,
                    end_time=current_end,
                    token_count=len(current_tokens),
                )
            )

            if overlap > 0 and len(current_tokens) > overlap:
                current_tokens = current_tokens[-overlap:]
                current_start = _estimate_start_time(
                    segments, current_end, overlap, encoding
                )
            else:
                current_tokens = []
                current_start = None

        seg_idx += 1

    if current_tokens and current_start is not None:
        chunk_text = encoding.decode(current_tokens)
        chunks.append(
            TranscriptChunk(
                id=f"{video_id}_{len(chunks)}",
                video_id=video_id,
                text=chunk_text,
                start_time=current_start,
                end_time=current_end,
                token_count=len(current_tokens),
            )
        )

    return chunks


def _estimate_start_time(
    segments: list[TranscriptSegment],
    end_time: float,
    overlap_tokens: int,
    encoding: tiktoken.Encoding,
) -> float:
    """Estimate start time for overlap portion by walking backwards."""
    tokens_counted = 0
    for seg in reversed(segments):
        seg_end = seg.start + seg.duration
        if seg_end > end_time:
            continue
        seg_tokens = len(encoding.encode(seg.text))
        tokens_counted += seg_tokens
        if tokens_counted >= overlap_tokens:
            return seg.start
    return segments[0].start if segments else 0.0


def chunk_transcript_simple(
    text: str,
    video_id: str,
    chunk_size: int = 500,
    overlap: int = 50,
) -> list[TranscriptChunk]:
    """
    Simple chunking for transcripts without timestamp data.

    Use this when timestamps are not available (e.g., whisper transcripts
    stored as plain text).
    """
    if not text.strip():
        return []

    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)

    if len(tokens) <= chunk_size:
        return [
            TranscriptChunk(
                id=f"{video_id}_0",
                video_id=video_id,
                text=text,
                start_time=0.0,
                end_time=0.0,
                token_count=len(tokens),
            )
        ]

    chunks: list[TranscriptChunk] = []
    start = 0

    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_tokens = tokens[start:end]
        chunk_text = encoding.decode(chunk_tokens)

        chunks.append(
            TranscriptChunk(
                id=f"{video_id}_{len(chunks)}",
                video_id=video_id,
                text=chunk_text,
                start_time=0.0,
                end_time=0.0,
                token_count=len(chunk_tokens),
            )
        )

        if end >= len(tokens):
            break

        start = end - overlap

    return chunks
