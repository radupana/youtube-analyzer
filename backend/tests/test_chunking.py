"""Tests for chunking service."""

from app.services.chunking import (
    TranscriptChunk,
    TranscriptSegment,
    chunk_transcript,
    chunk_transcript_simple,
)


class TestChunkTranscript:
    def test_empty_segments_returns_empty_list(self):
        result = chunk_transcript([], "video123")
        assert result == []

    def test_single_short_segment(self):
        segments = [TranscriptSegment(text="Hello world", start=0.0, duration=2.0)]
        result = chunk_transcript(segments, "vid1", chunk_size=500)

        assert len(result) == 1
        assert result[0].video_id == "vid1"
        assert result[0].id == "vid1_0"
        assert result[0].text == "Hello world"
        assert result[0].start_time == 0.0
        assert result[0].end_time == 2.0
        assert result[0].token_count > 0

    def test_multiple_segments_combined_into_one_chunk(self):
        segments = [
            TranscriptSegment(text="First part.", start=0.0, duration=1.0),
            TranscriptSegment(text="Second part.", start=1.0, duration=1.0),
            TranscriptSegment(text="Third part.", start=2.0, duration=1.0),
        ]
        result = chunk_transcript(segments, "vid2", chunk_size=500)

        assert len(result) == 1
        assert "First part." in result[0].text
        assert "Second part." in result[0].text
        assert "Third part." in result[0].text
        assert result[0].start_time == 0.0
        assert result[0].end_time == 3.0

    def test_segments_split_into_multiple_chunks(self):
        long_text = "word " * 200
        segments = [
            TranscriptSegment(text=long_text, start=0.0, duration=60.0),
            TranscriptSegment(text=long_text, start=60.0, duration=60.0),
        ]
        result = chunk_transcript(segments, "vid3", chunk_size=100, overlap=10)

        assert len(result) > 1
        for i, chunk in enumerate(result):
            assert chunk.id == f"vid3_{i}"
            assert chunk.video_id == "vid3"
            assert len(chunk.text) > 0

    def test_chunk_ids_are_sequential(self):
        long_text = "word " * 300
        segments = [TranscriptSegment(text=long_text, start=0.0, duration=120.0)]
        result = chunk_transcript(segments, "vid4", chunk_size=50, overlap=5)

        for i, chunk in enumerate(result):
            assert chunk.id == f"vid4_{i}"

    def test_timestamps_preserved_across_chunks(self):
        segments = [
            TranscriptSegment(text="Start of video.", start=0.0, duration=10.0),
            TranscriptSegment(text="word " * 100, start=10.0, duration=50.0),
            TranscriptSegment(text="End of video.", start=60.0, duration=10.0),
        ]
        result = chunk_transcript(segments, "vid5", chunk_size=50, overlap=5)

        assert result[0].start_time == 0.0
        assert result[-1].end_time == 70.0

    def test_overlap_creates_redundant_content(self):
        text1 = "alpha beta gamma delta epsilon "
        text2 = "zeta eta theta iota kappa "

        segments = [
            TranscriptSegment(text=text1 * 20, start=0.0, duration=30.0),
            TranscriptSegment(text=text2 * 20, start=30.0, duration=30.0),
        ]

        result_no_overlap = chunk_transcript(segments, "v1", chunk_size=50, overlap=0)
        result_with_overlap = chunk_transcript(
            segments, "v2", chunk_size=50, overlap=20
        )

        total_tokens_no_overlap = sum(c.token_count for c in result_no_overlap)
        total_tokens_with_overlap = sum(c.token_count for c in result_with_overlap)

        assert total_tokens_with_overlap > total_tokens_no_overlap


class TestChunkTranscriptSimple:
    def test_empty_text_returns_empty_list(self):
        result = chunk_transcript_simple("", "vid1")
        assert result == []

    def test_whitespace_only_returns_empty_list(self):
        result = chunk_transcript_simple("   \n\t  ", "vid1")
        assert result == []

    def test_short_text_single_chunk(self):
        result = chunk_transcript_simple("Hello world", "vid1", chunk_size=500)

        assert len(result) == 1
        assert result[0].text == "Hello world"
        assert result[0].video_id == "vid1"
        assert result[0].id == "vid1_0"
        assert result[0].start_time == 0.0
        assert result[0].end_time == 0.0

    def test_long_text_multiple_chunks(self):
        long_text = "word " * 500
        result = chunk_transcript_simple(long_text, "vid2", chunk_size=100, overlap=10)

        assert len(result) > 1
        for i, chunk in enumerate(result):
            assert chunk.id == f"vid2_{i}"

    def test_overlap_working(self):
        text = "word " * 300
        result_no_overlap = chunk_transcript_simple(
            text, "v1", chunk_size=50, overlap=0
        )
        result_with_overlap = chunk_transcript_simple(
            text, "v2", chunk_size=50, overlap=20
        )

        total_no_overlap = sum(c.token_count for c in result_no_overlap)
        total_with_overlap = sum(c.token_count for c in result_with_overlap)

        assert total_with_overlap > total_no_overlap


class TestTranscriptChunkDataclass:
    def test_chunk_attributes(self):
        chunk = TranscriptChunk(
            id="vid_0",
            video_id="vid",
            text="test text",
            start_time=10.5,
            end_time=20.5,
            token_count=5,
        )

        assert chunk.id == "vid_0"
        assert chunk.video_id == "vid"
        assert chunk.text == "test text"
        assert chunk.start_time == 10.5
        assert chunk.end_time == 20.5
        assert chunk.token_count == 5
