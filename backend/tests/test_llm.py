"""Tests for LLM service."""

from unittest.mock import patch

import pytest
from sqlmodel import SQLModel, create_engine

from app.services.llm import (
    CONTEXT_THRESHOLD_RATIO,
    DEFAULT_CONTEXT_WINDOW,
    SYSTEM_PROMPT_FULL,
    SYSTEM_PROMPT_RAG,
    _build_context_fallback,
    _build_full_transcript_context,
    build_context,
    build_context_with_rag,
    estimate_tokens,
    get_model_context_window,
)
from app.services.rag import process_transcript_for_rag


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


class TestBuildContextFallback:
    def test_empty_transcripts(self):
        result = _build_context_fallback([])
        assert "You have access to the following video transcripts:" in result

    def test_single_video_with_transcript(self, sample_video_transcripts):
        result = _build_context_fallback([sample_video_transcripts[0]])
        assert "Test Video 1" in result
        assert "Test Channel" in result
        assert "This is the transcript of test video 1." in result

    def test_video_without_transcript(self, sample_video_transcripts):
        result = _build_context_fallback([sample_video_transcripts[1]])
        assert "Test Video 2" in result
        assert "Another Channel" in result
        assert "Transcript: Not available" in result

    def test_multiple_videos(self, sample_video_transcripts):
        result = _build_context_fallback(sample_video_transcripts)
        assert "Test Video 1" in result
        assert "Test Video 2" in result
        assert "This is the transcript of test video 1." in result
        assert "Transcript: Not available" in result

    def test_long_transcript_truncation(self, long_transcript):
        videos = [
            {
                "title": "Long Video",
                "channel_title": "Channel",
                "transcript": long_transcript,
            }
        ]
        result = _build_context_fallback(videos)
        assert "... (truncated)" in result
        assert len(long_transcript) > 5000
        truncated_part = result.split("Transcript: ")[1].split("\n")[0]
        assert len(truncated_part) < len(long_transcript)


class TestBuildContextWithRag:
    def test_empty_transcripts(self, test_db):
        result = build_context_with_rag("test query", [])
        assert result == "No videos have been loaded yet."

    def test_falls_back_when_no_rag_data(self, test_db):
        videos = [
            {
                "video_id": "vid1",
                "title": "Test Video",
                "channel_title": "Channel",
                "transcript": "Some transcript",
            }
        ]
        result = build_context_with_rag("query", videos)
        assert "You have access to the following video transcripts:" in result
        assert "Test Video" in result

    @pytest.mark.requires_embeddings
    def test_uses_rag_when_available(self, test_db):
        video_id = "testvid123"
        transcript = "Machine learning is a subset of artificial intelligence."

        process_transcript_for_rag(video_id, transcript, chunk_size=100)

        videos = [
            {
                "video_id": video_id,
                "title": "ML Tutorial",
                "channel_title": "Tech Channel",
                "transcript": transcript,
            }
        ]

        result = build_context_with_rag("What is machine learning?", videos)

        assert "Relevant excerpts" in result
        assert "ML Tutorial" in result

    @pytest.mark.requires_embeddings
    def test_mixed_videos_rag_and_no_rag(self, test_db):
        process_transcript_for_rag("vid1", "Content about Python programming.")

        videos = [
            {
                "video_id": "vid1",
                "title": "Python Video",
                "channel_title": "Channel 1",
                "transcript": "Content about Python programming.",
            },
            {
                "video_id": "vid2",
                "title": "Other Video",
                "channel_title": "Channel 2",
                "transcript": "No RAG data for this.",
            },
        ]

        result = build_context_with_rag("Python", videos)

        assert "Relevant excerpts" in result or "video transcripts" in result


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_short_string(self):
        # 12 chars / 4 = 3 tokens
        assert estimate_tokens("Hello World!") == 3

    def test_longer_string(self):
        # 400 chars / 4 = 100 tokens
        text = "x" * 400
        assert estimate_tokens(text) == 100


class TestGetModelContextWindow:
    def test_returns_default_on_unknown_model(self):
        with patch("app.services.llm.litellm.get_max_tokens", side_effect=Exception):
            result = get_model_context_window("unknown-model")
        assert result == DEFAULT_CONTEXT_WINDOW

    def test_returns_model_context_when_available(self):
        with patch("app.services.llm.litellm.get_max_tokens", return_value=200000):
            result = get_model_context_window("claude-sonnet")
        assert result == 200000

    def test_returns_default_on_zero_or_none(self):
        with patch("app.services.llm.litellm.get_max_tokens", return_value=0):
            result = get_model_context_window("model")
        assert result == DEFAULT_CONTEXT_WINDOW

        with patch("app.services.llm.litellm.get_max_tokens", return_value=None):
            result = get_model_context_window("model")
        assert result == DEFAULT_CONTEXT_WINDOW


class TestBuildFullTranscriptContext:
    def test_empty_transcripts(self):
        result = _build_full_transcript_context([])
        assert "Complete transcripts from loaded videos:" in result

    def test_single_video(self):
        videos = [
            {
                "title": "Test Video",
                "channel_title": "Test Channel",
                "transcript": "This is the full transcript.",
            }
        ]
        result = _build_full_transcript_context(videos)
        assert "Test Video" in result
        assert "Test Channel" in result
        assert "This is the full transcript." in result
        assert "Complete transcripts" in result

    def test_video_without_transcript(self):
        videos = [
            {
                "title": "No Transcript Video",
                "channel_title": "Channel",
                "transcript": None,
            }
        ]
        result = _build_full_transcript_context(videos)
        assert "No Transcript Video" in result
        assert "(Transcript not available)" in result


class TestBuildContext:
    def test_empty_transcripts_returns_no_videos_message(self):
        context, prompt = build_context("query", [], "gpt-4")
        assert context == "No videos have been loaded yet."
        assert prompt == SYSTEM_PROMPT_FULL

    def test_uses_full_transcripts_when_under_threshold(self):
        """Small transcripts should use full context."""
        # 1000 chars = ~250 tokens, well under 70% of 128K
        videos = [
            {
                "title": "Short Video",
                "channel_title": "Channel",
                "transcript": "x" * 1000,
            }
        ]
        with patch("app.services.llm.get_model_context_window", return_value=128000):
            context, prompt = build_context("query", videos, "gpt-4")

        assert "Complete transcripts" in context
        assert prompt == SYSTEM_PROMPT_FULL

    def test_uses_rag_when_over_threshold(self, test_db):
        """Large transcripts should trigger RAG."""
        # Create transcript that exceeds 70% of a small context window
        # 10000 chars = 2500 tokens, which exceeds 70% of 3000 = 2100 tokens
        videos = [
            {
                "video_id": "vid1",
                "title": "Long Video",
                "channel_title": "Channel",
                "transcript": "x" * 10000,
            }
        ]
        with patch("app.services.llm.get_model_context_window", return_value=3000):
            context, prompt = build_context("query", videos, "small-model")

        # Should use RAG or fallback (not full transcripts)
        assert prompt == SYSTEM_PROMPT_RAG
        # Context should NOT say "Complete transcripts"
        assert "Complete transcripts" not in context

    def test_threshold_ratio_is_70_percent(self):
        assert CONTEXT_THRESHOLD_RATIO == 0.70
