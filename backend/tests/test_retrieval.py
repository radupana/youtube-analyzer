"""Tests for retrieval service."""

import numpy as np
import pytest

from app.services.chunking import TranscriptChunk
from app.services.embeddings import EMBEDDING_DIMENSION, generate_embeddings
from app.services.retrieval import (
    _format_timestamp,
    build_context_from_chunks,
    retrieve_relevant_chunks,
)


def make_chunk(
    video_id: str,
    idx: int,
    text: str,
    start: float = 0.0,
    end: float = 0.0,
    token_count: int = 10,
) -> TranscriptChunk:
    return TranscriptChunk(
        id=f"{video_id}_{idx}",
        video_id=video_id,
        text=text,
        start_time=start,
        end_time=end,
        token_count=token_count,
    )


class TestRetrieveRelevantChunks:
    def test_empty_chunks_returns_empty(self):
        embeddings = np.array([], dtype=np.float32).reshape(0, EMBEDDING_DIMENSION)
        result = retrieve_relevant_chunks("query", [], embeddings)
        assert result == []

    def test_single_chunk_returns_that_chunk(self):
        chunk = make_chunk("v1", 0, "Machine learning is great")
        embeddings = generate_embeddings([chunk.text])

        result = retrieve_relevant_chunks("what is ML?", [chunk], embeddings, top_k=5)

        assert len(result) == 1
        assert result[0] is chunk

    def test_retrieves_most_relevant_chunks(self):
        chunks = [
            make_chunk("v1", 0, "Machine learning and artificial intelligence"),
            make_chunk("v1", 1, "The weather forecast for tomorrow"),
            make_chunk("v1", 2, "Deep neural networks and backpropagation"),
            make_chunk("v1", 3, "Cooking recipes and ingredients"),
            make_chunk("v1", 4, "Supervised and unsupervised learning algorithms"),
        ]
        embeddings = generate_embeddings([c.text for c in chunks])

        result = retrieve_relevant_chunks(
            "Tell me about machine learning", chunks, embeddings, top_k=3
        )

        assert len(result) == 3
        result_texts = [r.text for r in result]
        assert "Machine learning and artificial intelligence" in result_texts
        assert "Deep neural networks and backpropagation" in result_texts
        assert "Supervised and unsupervised learning algorithms" in result_texts

    def test_top_k_limits_results(self):
        chunks = [make_chunk("v1", i, f"Chunk {i} text") for i in range(10)]
        embeddings = generate_embeddings([c.text for c in chunks])

        result = retrieve_relevant_chunks("chunk", chunks, embeddings, top_k=3)

        assert len(result) == 3

    def test_top_k_larger_than_chunks_returns_all(self):
        chunks = [make_chunk("v1", i, f"Content {i}") for i in range(3)]
        embeddings = generate_embeddings([c.text for c in chunks])

        result = retrieve_relevant_chunks("content", chunks, embeddings, top_k=10)

        assert len(result) == 3

    def test_mismatched_counts_raises_error(self):
        chunks = [make_chunk("v1", 0, "Test")]
        embeddings = generate_embeddings(["Text 1", "Text 2"])

        with pytest.raises(ValueError, match="mismatch"):
            retrieve_relevant_chunks("query", chunks, embeddings)


class TestBuildContextFromChunks:
    def test_empty_chunks_returns_empty_string(self):
        result = build_context_from_chunks([])
        assert result == ""

    def test_single_chunk_without_timestamp(self):
        chunk = make_chunk("v1", 0, "Hello world", start=0.0, end=0.0, token_count=2)
        result = build_context_from_chunks([chunk])

        assert result == "Hello world"

    def test_single_chunk_with_timestamp(self):
        chunk = make_chunk("v1", 0, "Hello world", start=65.0, end=70.0, token_count=2)
        result = build_context_from_chunks([chunk])

        assert result == "[1:05] Hello world"

    def test_multiple_chunks_joined_with_newlines(self):
        chunks = [
            make_chunk("v1", 0, "First chunk", start=10.0, end=20.0, token_count=2),
            make_chunk("v1", 1, "Second chunk", start=20.0, end=30.0, token_count=2),
        ]
        result = build_context_from_chunks(chunks)

        assert "[0:10] First chunk" in result
        assert "[0:20] Second chunk" in result
        assert "\n\n" in result

    def test_respects_max_tokens(self):
        chunks = [
            make_chunk("v1", 0, "First", token_count=100),
            make_chunk("v1", 1, "Second", token_count=100),
            make_chunk("v1", 2, "Third", token_count=100),
        ]
        result = build_context_from_chunks(chunks, max_tokens=150)

        assert "First" in result
        assert "Second" not in result
        assert "Third" not in result


class TestFormatTimestamp:
    def test_zero_seconds(self):
        assert _format_timestamp(0) == "0:00"

    def test_under_one_minute(self):
        assert _format_timestamp(45) == "0:45"

    def test_exactly_one_minute(self):
        assert _format_timestamp(60) == "1:00"

    def test_minutes_and_seconds(self):
        assert _format_timestamp(125) == "2:05"

    def test_one_hour(self):
        assert _format_timestamp(3600) == "1:00:00"

    def test_hours_minutes_seconds(self):
        assert _format_timestamp(3725) == "1:02:05"

    def test_float_truncates(self):
        assert _format_timestamp(65.7) == "1:05"
