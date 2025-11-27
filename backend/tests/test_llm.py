from app.services.llm import build_context


class TestBuildContext:
    def test_empty_transcripts(self):
        result = build_context([])
        assert result == "No videos have been loaded yet."

    def test_single_video_with_transcript(self, sample_video_transcripts):
        result = build_context([sample_video_transcripts[0]])
        assert "Test Video 1" in result
        assert "Test Channel" in result
        assert "This is the transcript of test video 1." in result

    def test_video_without_transcript(self, sample_video_transcripts):
        result = build_context([sample_video_transcripts[1]])
        assert "Test Video 2" in result
        assert "Another Channel" in result
        assert "Transcript: Not available" in result

    def test_multiple_videos(self, sample_video_transcripts):
        result = build_context(sample_video_transcripts)
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
        result = build_context(videos)
        assert "... (truncated)" in result
        assert len(long_transcript) > 5000
        truncated_part = result.split("Transcript: ")[1].split("\n")[0]
        assert len(truncated_part) < len(long_transcript)
