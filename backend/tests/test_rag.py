"""Tests for RAG service."""

import shutil
import tempfile

import pytest

from app.services.chunking import TranscriptSegment
from app.services.rag import (
    has_rag_data,
    process_transcript_for_rag,
    retrieve_context_for_query,
)


@pytest.fixture
def temp_cache_dir(monkeypatch):
    """Create a temporary cache directory for tests."""
    temp_dir = tempfile.mkdtemp()
    monkeypatch.setenv("CACHE_DIR", temp_dir)

    import app.services.cache

    app.services.cache._cache_service = None

    yield temp_dir

    shutil.rmtree(temp_dir, ignore_errors=True)
    app.services.cache._cache_service = None


class TestProcessTranscriptForRag:
    def test_empty_transcript_returns_false(self, temp_cache_dir):
        result = process_transcript_for_rag("vid1", "")
        assert result is False

    def test_whitespace_transcript_returns_false(self, temp_cache_dir):
        result = process_transcript_for_rag("vid1", "   \n\t  ")
        assert result is False

    def test_simple_transcript_creates_chunks(self, temp_cache_dir):
        transcript = "This is a test transcript with some content."
        result = process_transcript_for_rag("vid1", transcript)

        assert result is True
        assert has_rag_data("vid1")

    def test_transcript_with_segments(self, temp_cache_dir):
        segments = [
            TranscriptSegment(text="First segment.", start=0.0, duration=5.0),
            TranscriptSegment(text="Second segment.", start=5.0, duration=5.0),
        ]
        transcript = "First segment. Second segment."

        result = process_transcript_for_rag("vid2", transcript, segments=segments)

        assert result is True
        assert has_rag_data("vid2")

    def test_already_cached_returns_true(self, temp_cache_dir):
        transcript = "Some content here."
        process_transcript_for_rag("vid3", transcript)

        result = process_transcript_for_rag("vid3", transcript)

        assert result is True

    def test_long_transcript_creates_multiple_chunks(self, temp_cache_dir):
        transcript = "word " * 1000
        result = process_transcript_for_rag(
            "vid4", transcript, chunk_size=100, overlap=10
        )

        assert result is True
        assert has_rag_data("vid4")


class TestRetrieveContextForQuery:
    def test_no_videos_returns_empty(self, temp_cache_dir):
        result = retrieve_context_for_query("what is this?", [])
        assert result == ""

    def test_missing_video_returns_empty(self, temp_cache_dir):
        result = retrieve_context_for_query("query", ["nonexistent"])
        assert result == ""

    def test_retrieves_relevant_content(self, temp_cache_dir):
        transcript = (
            "Machine learning is a subset of artificial intelligence. "
            "Weather forecasting uses various models. "
            "Deep learning involves neural networks."
        )
        process_transcript_for_rag("vid1", transcript, chunk_size=50, overlap=5)

        result = retrieve_context_for_query(
            "Tell me about machine learning", ["vid1"], top_k=2
        )

        assert len(result) > 0
        assert "machine learning" in result.lower() or "neural" in result.lower()

    def test_retrieves_from_multiple_videos(self, temp_cache_dir):
        process_transcript_for_rag(
            "vid1", "Python programming language basics.", chunk_size=50
        )
        process_transcript_for_rag("vid2", "JavaScript web development.", chunk_size=50)

        result = retrieve_context_for_query("programming", ["vid1", "vid2"], top_k=5)

        assert len(result) > 0

    def test_respects_max_tokens(self, temp_cache_dir):
        transcript = "word " * 500
        process_transcript_for_rag("vid1", transcript, chunk_size=100)

        result_short = retrieve_context_for_query(
            "word", ["vid1"], top_k=10, max_tokens=50
        )
        result_long = retrieve_context_for_query(
            "word", ["vid1"], top_k=10, max_tokens=500
        )

        assert len(result_short) < len(result_long)


class TestHasRagData:
    def test_returns_false_for_missing(self, temp_cache_dir):
        assert has_rag_data("nonexistent") is False

    def test_returns_true_after_processing(self, temp_cache_dir):
        process_transcript_for_rag("vid1", "Some transcript content.")
        assert has_rag_data("vid1") is True
