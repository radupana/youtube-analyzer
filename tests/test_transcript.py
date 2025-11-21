from unittest.mock import Mock, patch

import pytest
from youtube_transcript_api._errors import (
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from yt_agent_kit.transcript import (
    clean_transcript,
    get_transcript,
    get_transcripts_batch,
)


class TestCleanTranscript:
    def test_removes_music_markers(self):
        text = "Hello [MUSIC] world [music] test"
        result = clean_transcript(text)
        assert result == "Hello world test"

    def test_removes_applause_markers(self):
        text = "Speech [APPLAUSE] continues [applause] here"
        result = clean_transcript(text)
        assert result == "Speech continues here"

    def test_removes_laughter_markers(self):
        text = "Funny joke [LAUGHTER] more content [laughter]"
        result = clean_transcript(text)
        assert result == "Funny joke more content"

    def test_removes_inaudible_markers(self):
        text = "Some words [INAUDIBLE] other words"
        result = clean_transcript(text)
        assert result == "Some words other words"

    def test_removes_generic_bracket_markers(self):
        text = "Text [COUGHING] more [RANDOM NOISE] end"
        result = clean_transcript(text)
        assert result == "Text more end"

    def test_normalizes_whitespace(self):
        text = "Too   many    spaces\n\nand\nnewlines"
        result = clean_transcript(text)
        assert result == "Too many spaces and newlines"

    def test_strips_leading_trailing_whitespace(self):
        text = "   content here   "
        result = clean_transcript(text)
        assert result == "content here"

    def test_handles_empty_string(self):
        result = clean_transcript("")
        assert result == ""

    def test_handles_only_markers(self):
        text = "[MUSIC] [APPLAUSE] [LAUGHTER]"
        result = clean_transcript(text)
        assert result == ""


class TestGetTranscript:
    def test_fetches_and_cleans_transcript(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        mock_snippet1 = Mock()
        mock_snippet1.text = "Hello [MUSIC] world"
        mock_snippet2 = Mock()
        mock_snippet2.text = "This is a test"
        mock_transcript_data = [mock_snippet1, mock_snippet2]

        mock_transcript = Mock()
        mock_transcript.fetch.return_value = mock_transcript_data

        mock_transcript_list = Mock()
        mock_transcript_list.find_transcript.return_value = mock_transcript

        mock_api = Mock()
        mock_api.list.return_value = mock_transcript_list

        with patch(
            "yt_agent_kit.transcript.YouTubeTranscriptApi", return_value=mock_api
        ):
            result = get_transcript("test_video_id")

        assert result == "Hello world This is a test"

    def test_uses_custom_languages(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        mock_snippet = Mock()
        mock_snippet.text = "Bonjour"
        mock_transcript_data = [mock_snippet]

        mock_transcript = Mock()
        mock_transcript.fetch.return_value = mock_transcript_data

        mock_transcript_list = Mock()
        mock_transcript_list.find_transcript.return_value = mock_transcript

        mock_api = Mock()
        mock_api.list.return_value = mock_transcript_list

        with patch(
            "yt_agent_kit.transcript.YouTubeTranscriptApi", return_value=mock_api
        ):
            result = get_transcript("test_id", languages=["fr", "en"])

        mock_transcript_list.find_transcript.assert_called_once_with(["fr", "en"])
        assert result == "Bonjour"

    def test_caches_transcript(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        mock_snippet = Mock()
        mock_snippet.text = "Cached content"
        mock_transcript_data = [mock_snippet]

        mock_transcript = Mock()
        mock_transcript.fetch.return_value = mock_transcript_data

        mock_transcript_list = Mock()
        mock_transcript_list.find_transcript.return_value = mock_transcript

        mock_api = Mock()
        mock_api.list.return_value = mock_transcript_list

        with patch(
            "yt_agent_kit.transcript.YouTubeTranscriptApi", return_value=mock_api
        ) as mock_ytt:
            result1 = get_transcript("cached_id")
            result2 = get_transcript("cached_id")

        assert result1 == result2 == "Cached content"
        assert mock_ytt.call_count == 1

    def test_raises_no_transcript_found(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        mock_transcript_list = Mock()
        mock_transcript_list.find_transcript.side_effect = NoTranscriptFound(
            "test_id", [], None
        )

        mock_api = Mock()
        mock_api.list.return_value = mock_transcript_list

        with patch(
            "yt_agent_kit.transcript.YouTubeTranscriptApi", return_value=mock_api
        ):
            with pytest.raises(NoTranscriptFound):
                get_transcript("test_id")

    def test_raises_transcripts_disabled(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        mock_api = Mock()
        mock_api.list.side_effect = TranscriptsDisabled("test_id")

        with patch(
            "yt_agent_kit.transcript.YouTubeTranscriptApi", return_value=mock_api
        ):
            with pytest.raises(TranscriptsDisabled):
                get_transcript("test_id")

    def test_raises_video_unavailable(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        mock_api = Mock()
        mock_api.list.side_effect = VideoUnavailable("test_id")

        with patch(
            "yt_agent_kit.transcript.YouTubeTranscriptApi", return_value=mock_api
        ):
            with pytest.raises(VideoUnavailable):
                get_transcript("test_id")


class TestGetTranscriptsBatch:
    def test_fetches_multiple_transcripts(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with patch("yt_agent_kit.transcript.get_transcript") as mock_get:
            mock_get.side_effect = lambda vid, langs=None: f"{vid} transcript"
            result = get_transcripts_batch(["vid1", "vid2"])

        assert len(result) == 2
        assert result["vid1"] == "vid1 transcript"
        assert result["vid2"] == "vid2 transcript"

    def test_skips_videos_without_transcripts(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        def mock_get_transcript(video_id, languages=None):
            if video_id == "vid_no_transcript":
                raise NoTranscriptFound(video_id, [], None)
            return "Has transcript"

        with patch(
            "yt_agent_kit.transcript.get_transcript", side_effect=mock_get_transcript
        ):
            result = get_transcripts_batch(["vid1", "vid_no_transcript", "vid2"])

        assert len(result) == 2
        assert "vid1" in result
        assert "vid2" in result
        assert "vid_no_transcript" not in result

    def test_calls_progress_callback(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        progress_calls = []

        def progress_callback(current, total, video_id):
            progress_calls.append((current, total, video_id))

        with patch("yt_agent_kit.transcript.get_transcript", return_value="Content"):
            get_transcripts_batch(
                ["vid1", "vid2", "vid3"], progress_callback=progress_callback
            )

        # Verify callback was called 3 times with correct total
        assert len(progress_calls) == 3
        # With parallel execution, order is non-deterministic
        assert all(call[1] == 3 for call in progress_calls)  # total is always 3
        assert all(
            call[0] in [1, 2, 3] for call in progress_calls
        )  # current is 1, 2, or 3
        assert set(call[2] for call in progress_calls) == {"vid1", "vid2", "vid3"}

    def test_continues_after_disabled_transcripts(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        def mock_get_transcript(video_id, languages=None):
            if video_id == "disabled":
                raise TranscriptsDisabled(video_id)
            return "Available"

        with patch(
            "yt_agent_kit.transcript.get_transcript", side_effect=mock_get_transcript
        ):
            result = get_transcripts_batch(["vid1", "disabled", "vid2"])

        assert len(result) == 2
        assert "disabled" not in result

    def test_continues_after_unavailable_videos(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        def mock_get_transcript(video_id, languages=None):
            if video_id == "unavailable":
                raise VideoUnavailable(video_id)
            return "Available"

        with patch(
            "yt_agent_kit.transcript.get_transcript", side_effect=mock_get_transcript
        ):
            result = get_transcripts_batch(["vid1", "unavailable", "vid2"])

        assert len(result) == 2
        assert "unavailable" not in result

    def test_returns_empty_dict_for_all_failures(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with patch(
            "yt_agent_kit.transcript.get_transcript",
            side_effect=NoTranscriptFound("id", [], None),
        ):
            result = get_transcripts_batch(["vid1", "vid2"])

        assert result == {}

    def test_uses_custom_languages_for_batch(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with patch("yt_agent_kit.transcript.get_transcript") as mock_get:
            mock_get.return_value = "Test"
            get_transcripts_batch(["vid1"], languages=["es", "en"])

        mock_get.assert_called_with("vid1", ["es", "en"])
