import shutil

import pytest

from yt_agent_kit.embeddings import (
    DEFAULT_CHUNK_SIZE,
    Chunk,
    build_index,
    chunk_transcript,
    get_index_stats,
    search,
)


class TestChunkTranscript:
    def test_empty_text_returns_empty_list(self):
        result = chunk_transcript("", "vid1", "Video 1")
        assert result == []

    def test_whitespace_only_returns_empty_list(self):
        result = chunk_transcript("   ", "vid1", "Video 1")
        assert result == []

    def test_short_text_returns_single_chunk(self):
        text = "This is a short transcript."
        result = chunk_transcript(text, "vid1", "Video 1", chunk_size=100)
        assert len(result) == 1
        assert result[0].content == text
        assert result[0].video_id == "vid1"
        assert result[0].video_title == "Video 1"
        assert result[0].chunk_index == 0

    def test_text_splits_into_multiple_chunks(self):
        text = "a" * 300
        result = chunk_transcript(
            text, "vid1", "Title", chunk_size=100, chunk_overlap=20
        )

        assert len(result) > 1
        assert all(isinstance(c, Chunk) for c in result)
        assert all(c.video_id == "vid1" for c in result)
        assert all(c.video_title == "Title" for c in result)
        assert [c.chunk_index for c in result] == list(range(len(result)))

    def test_chunk_size_respected(self):
        text = "a" * 500
        chunk_size = 100
        result = chunk_transcript(
            text, "vid1", "Title", chunk_size=chunk_size, chunk_overlap=0
        )

        for chunk in result:
            assert len(chunk.content) <= chunk_size

    def test_overlap_creates_overlapping_content(self):
        text = "abcdefghijklmnopqrstuvwxyz"
        result = chunk_transcript(text, "vid1", "Title", chunk_size=10, chunk_overlap=3)

        if len(result) >= 2:
            end_of_first = result[0].content[-3:]
            start_of_second = result[1].content[:3]
            assert end_of_first == start_of_second

    def test_metadata_preserved(self):
        result = chunk_transcript("Some text", "test_id", "Test Title")
        assert result[0].video_id == "test_id"
        assert result[0].video_title == "Test Title"

    def test_default_parameters(self):
        text = "a" * (DEFAULT_CHUNK_SIZE + 100)
        result = chunk_transcript(text, "vid1", "Title")
        assert len(result) >= 2


@pytest.fixture
def temp_index_dir(tmp_path, monkeypatch):
    test_index = tmp_path / ".index"
    monkeypatch.setattr("yt_agent_kit.embeddings.INDEX_DIR", test_index)
    yield test_index
    if test_index.exists():
        shutil.rmtree(test_index)


class TestBuildIndex:
    def test_empty_transcripts_returns_zero(self, temp_index_dir):
        result = build_index("channel1", {})
        assert result == 0

    def test_builds_index_for_transcripts(self, temp_index_dir):
        transcripts = {
            "vid1": ("Video One", "This is the first video transcript."),
            "vid2": ("Video Two", "This is the second video transcript."),
        }
        result = build_index("channel1", transcripts)
        assert result == 2

        index_path = temp_index_dir / "channel1"
        assert index_path.exists()

    def test_incremental_indexing_skips_existing(self, temp_index_dir):
        transcripts = {"vid1": ("Video One", "First transcript.")}
        build_index("channel1", transcripts)

        new_transcripts = {
            "vid1": ("Video One", "First transcript."),
            "vid2": ("Video Two", "Second transcript."),
        }
        result = build_index("channel1", new_transcripts)
        assert result == 1


class TestSearch:
    def test_search_empty_index_returns_empty(self, temp_index_dir):
        result = search("nonexistent_channel", "test query")
        assert result == []

    def test_search_returns_relevant_chunks(self, temp_index_dir):
        transcripts = {
            "vid1": (
                "Strength Training",
                "Progressive overload is key for muscle growth.",
            ),
            "vid2": ("Nutrition Guide", "Protein intake should be around 1.6g per kg."),
        }
        build_index("channel1", transcripts)

        results = search("channel1", "muscle building protein", k=2)
        assert len(results) > 0
        assert all(isinstance(c, Chunk) for c in results)

    def test_search_returns_metadata(self, temp_index_dir):
        transcripts = {"vid1": ("My Video", "Some content here.")}
        build_index("channel1", transcripts)

        results = search("channel1", "content")
        assert len(results) > 0
        assert results[0].video_id == "vid1"
        assert results[0].video_title == "My Video"

    def test_search_respects_k_parameter(self, temp_index_dir):
        transcripts = {
            f"vid{i}": (f"Video {i}", f"Content number {i} about topic.")
            for i in range(10)
        }
        build_index("channel1", transcripts)

        results = search("channel1", "topic", k=3)
        assert len(results) <= 3


class TestGetIndexStats:
    def test_nonexistent_index_returns_zeros(self, temp_index_dir):
        stats = get_index_stats("nonexistent")
        assert stats["total_chunks"] == 0
        assert stats["total_videos"] == 0
        assert stats["index_size_mb"] == 0.0

    def test_returns_correct_stats(self, temp_index_dir):
        transcripts = {
            "vid1": ("Video One", "a" * 2000),
            "vid2": ("Video Two", "b" * 2000),
        }
        build_index("channel1", transcripts)

        stats = get_index_stats("channel1")
        assert stats["total_chunks"] > 0
        assert stats["total_videos"] == 2
        assert stats["index_size_mb"] >= 0
