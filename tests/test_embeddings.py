import shutil

import pytest

from yt_agent_kit.embeddings import (
    DEFAULT_CHUNK_SIZE,
    Chunk,
    build_index,
    chunk_transcript,
    delete_videos,
    get_index_stats,
    search,
    sync_index,
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
        result = chunk_transcript(
            text, "vid1", "Video 1", chunk_size=100, chunk_overlap=20
        )
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

    def test_overlap_equal_to_chunk_size_raises(self):
        with pytest.raises(
            ValueError, match="chunk_overlap.*must be less than chunk_size"
        ):
            chunk_transcript(
                "some text", "vid1", "Title", chunk_size=100, chunk_overlap=100
            )

    def test_overlap_greater_than_chunk_size_raises(self):
        with pytest.raises(
            ValueError, match="chunk_overlap.*must be less than chunk_size"
        ):
            chunk_transcript(
                "some text", "vid1", "Title", chunk_size=100, chunk_overlap=150
            )


@pytest.fixture
def temp_index_dir(tmp_path, monkeypatch):
    test_index = tmp_path / ".index"
    monkeypatch.setattr("yt_agent_kit.embeddings.INDEX_DIR", test_index)
    yield test_index
    if test_index.exists():
        shutil.rmtree(test_index, ignore_errors=True)


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


class TestDeleteVideos:
    def test_delete_empty_set_returns_zero(self, temp_index_dir):
        result = delete_videos("channel1", set())
        assert result == 0

    def test_delete_from_nonexistent_index_returns_zero(self, temp_index_dir):
        result = delete_videos("nonexistent", {"vid1"})
        assert result == 0

    def test_deletes_specified_videos(self, temp_index_dir):
        transcripts = {
            "vid1": ("Video One", "First transcript content."),
            "vid2": ("Video Two", "Second transcript content."),
            "vid3": ("Video Three", "Third transcript content."),
        }
        build_index("channel1", transcripts)

        stats_before = get_index_stats("channel1")
        assert stats_before["total_videos"] == 3

        delete_videos("channel1", {"vid1", "vid2"})

        stats_after = get_index_stats("channel1")
        assert stats_after["total_videos"] == 1

        results = search("channel1", "transcript")
        video_ids = {r.video_id for r in results}
        assert "vid3" in video_ids
        assert "vid1" not in video_ids
        assert "vid2" not in video_ids


class TestSyncIndex:
    def test_sync_adds_new_videos(self, temp_index_dir):
        transcripts = {"vid1": ("Video One", "First transcript.")}
        added, removed = sync_index("channel1", transcripts)
        assert added == 1
        assert removed == 0

    def test_sync_removes_deleted_videos(self, temp_index_dir):
        initial = {
            "vid1": ("Video One", "First transcript."),
            "vid2": ("Video Two", "Second transcript."),
        }
        build_index("channel1", initial)

        updated = {"vid1": ("Video One", "First transcript.")}
        added, removed = sync_index("channel1", updated)

        assert added == 0
        assert removed == 1

        stats = get_index_stats("channel1")
        assert stats["total_videos"] == 1

    def test_sync_adds_and_removes(self, temp_index_dir):
        initial = {
            "vid1": ("Video One", "First transcript."),
            "vid2": ("Video Two", "Second transcript."),
        }
        build_index("channel1", initial)

        updated = {
            "vid1": ("Video One", "First transcript."),
            "vid3": ("Video Three", "Third transcript."),
        }
        added, removed = sync_index("channel1", updated)

        assert added == 1
        assert removed == 1

        stats = get_index_stats("channel1")
        assert stats["total_videos"] == 2


class TestIndexPersistence:
    def test_index_persists_across_client_instances(self, temp_index_dir):
        transcripts = {"vid1": ("Video One", "Persistent content here.")}
        build_index("channel1", transcripts)

        stats1 = get_index_stats("channel1")
        assert stats1["total_videos"] == 1

        results = search("channel1", "persistent")
        assert len(results) > 0
        assert results[0].video_id == "vid1"


class TestCollectionIdValidation:
    def test_valid_collection_ids(self, temp_index_dir):
        valid_ids = [
            "UCabcdef123",
            "channel_UCabcdef123",
            "video_dQw4w9WgXcQ",
            "playlist_PLtest123",
            "my-channel",
        ]
        for collection_id in valid_ids:
            build_index(collection_id, {})

    def test_path_traversal_rejected(self, temp_index_dir):
        with pytest.raises(ValueError, match="Invalid collection_id"):
            build_index("../malicious", {})

    def test_slash_rejected(self, temp_index_dir):
        with pytest.raises(ValueError, match="Invalid collection_id"):
            build_index("foo/bar", {})

    def test_empty_collection_id_rejected(self, temp_index_dir):
        with pytest.raises(ValueError, match="Invalid collection_id"):
            build_index("", {})

    def test_special_chars_rejected(self, temp_index_dir):
        with pytest.raises(ValueError, match="Invalid collection_id"):
            build_index("collection@test", {})
