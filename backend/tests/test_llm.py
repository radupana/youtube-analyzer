"""Tests for LLM service."""

import shutil
import tempfile

import pytest

from app.services.llm import _build_context_fallback, build_context_with_rag
from app.services.rag import process_transcript_for_rag


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
    def test_empty_transcripts(self, temp_cache_dir):
        result = build_context_with_rag("test query", [])
        assert result == "No videos have been loaded yet."

    def test_falls_back_when_no_rag_data(self, temp_cache_dir):
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

    def test_uses_rag_when_available(self, temp_cache_dir):
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

    def test_mixed_videos_rag_and_no_rag(self, temp_cache_dir):
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
