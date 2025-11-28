"""Tests for RAG service."""

import pytest
from sqlmodel import SQLModel, create_engine

from app.services.chunking import TranscriptSegment
from app.services.rag import (
    has_rag_data,
    process_transcript_for_rag,
    retrieve_context_for_query,
)


@pytest.fixture
def test_db(monkeypatch):
    """Create an in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.create_all(engine)

    def get_test_engine():
        return engine

    monkeypatch.setattr("app.services.rag.get_engine", get_test_engine)

    yield engine

    engine.dispose()


class TestProcessTranscriptForRag:
    def test_empty_transcript_returns_false(self, test_db):
        result = process_transcript_for_rag("vid1", "")
        assert result is False

    def test_whitespace_transcript_returns_false(self, test_db):
        result = process_transcript_for_rag("vid1", "   \n\t  ")
        assert result is False

    def test_simple_transcript_creates_chunks(self, test_db):
        transcript = "This is a test transcript with some content."
        result = process_transcript_for_rag("vid1", transcript)

        assert result is True
        assert has_rag_data("vid1")

    def test_transcript_with_segments(self, test_db):
        segments = [
            TranscriptSegment(text="First segment.", start=0.0, duration=5.0),
            TranscriptSegment(text="Second segment.", start=5.0, duration=5.0),
        ]
        transcript = "First segment. Second segment."

        result = process_transcript_for_rag("vid2", transcript, segments=segments)

        assert result is True
        assert has_rag_data("vid2")

    def test_already_exists_returns_true(self, test_db):
        transcript = "Some content here."
        process_transcript_for_rag("vid3", transcript)

        result = process_transcript_for_rag("vid3", transcript)

        assert result is True

    def test_long_transcript_creates_multiple_chunks(self, test_db):
        transcript = "word " * 1000
        result = process_transcript_for_rag(
            "vid4", transcript, chunk_size=100, overlap=10
        )

        assert result is True
        assert has_rag_data("vid4")


class TestRetrieveContextForQuery:
    def test_no_videos_returns_empty(self, test_db):
        result = retrieve_context_for_query("what is this?", [])
        assert result == ""

    def test_missing_video_returns_empty(self, test_db):
        result = retrieve_context_for_query("query", ["nonexistent"])
        assert result == ""

    def test_retrieves_relevant_content(self, test_db):
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

    def test_retrieves_from_multiple_videos(self, test_db):
        process_transcript_for_rag(
            "vid1", "Python programming language basics.", chunk_size=50
        )
        process_transcript_for_rag("vid2", "JavaScript web development.", chunk_size=50)

        result = retrieve_context_for_query("programming", ["vid1", "vid2"], top_k=5)

        assert len(result) > 0

    def test_respects_max_tokens(self, test_db):
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
    def test_returns_false_for_missing(self, test_db):
        assert has_rag_data("nonexistent") is False

    def test_returns_true_after_processing(self, test_db):
        process_transcript_for_rag("vid1", "Some transcript content.")
        assert has_rag_data("vid1") is True
