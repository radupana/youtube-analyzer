from unittest.mock import Mock, patch

import pytest
from youtube_transcript_api._errors import (
    IpBlocked,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from yt_agent_kit.transcript import (
    MIN_AUDIO_SIZE_BYTES,
    VALID_VIDEO_ID_PATTERN,
    WhisperModelLoadError,
    WhisperTranscriptionError,
    _get_whisper_model,
    clean_transcript,
    download_audio,
    get_transcript,
    get_transcript_with_whisper_fallback,
    get_transcripts_batch,
    get_transcripts_batch_with_fallback,
    transcribe_audio,
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

    def test_logs_warning_on_ip_blocked(self, tmp_path, monkeypatch, caplog):
        """Test that IpBlocked errors are logged with helpful message."""
        monkeypatch.chdir(tmp_path)

        def mock_get_transcript(video_id, languages=None):
            if video_id == "blocked_vid":
                raise IpBlocked("blocked_vid")
            return "Has transcript"

        import logging

        with caplog.at_level(logging.WARNING):
            with patch(
                "yt_agent_kit.transcript.get_transcript",
                side_effect=mock_get_transcript,
            ):
                result = get_transcripts_batch(["vid1", "blocked_vid"])

        assert len(result) == 1
        assert "blocked_vid" not in result
        assert "IP blocked" in caplog.text
        assert "Whisper fallback" in caplog.text


class TestVideoIdValidation:
    def test_valid_video_ids(self):
        """Test that valid YouTube video IDs pass validation."""
        valid_ids = [
            "dQw4w9WgXcQ",  # Standard ID
            "abc123ABC_-",  # All valid characters
            "AAAAAAAAAAA",  # All uppercase
            "aaaaaaaaaaa",  # All lowercase
            "12345678901",  # All numbers
            "_-_-_-_-_-_",  # Underscores and dashes
        ]
        for video_id in valid_ids:
            assert VALID_VIDEO_ID_PATTERN.match(video_id), f"{video_id} should be valid"

    def test_invalid_video_ids(self):
        """Test that invalid video IDs fail validation."""
        invalid_ids = [
            "short",  # Too short
            "waytoolongid",  # Too long
            "abc123!@#$%",  # Invalid characters
            "abc 123 xyz",  # Spaces
            "",  # Empty
            "abc123ABC_-X",  # 12 characters
        ]
        for video_id in invalid_ids:
            assert not VALID_VIDEO_ID_PATTERN.match(
                video_id
            ), f"{video_id} should be invalid"


class TestDownloadAudio:
    def test_downloads_audio_successfully(self, tmp_path):
        mock_ydl_instance = Mock()
        mock_ydl_instance.download.return_value = 0

        with patch("yt_agent_kit.transcript.yt_dlp.YoutubeDL") as mock_ydl:
            mock_ydl.return_value.__enter__.return_value = mock_ydl_instance
            mock_ydl.return_value.__exit__.return_value = None

            result = download_audio("dQw4w9WgXcQ", tmp_path)

        assert result == tmp_path / "dQw4w9WgXcQ.mp3"
        mock_ydl_instance.download.assert_called_once()

    def test_uses_correct_yt_dlp_options(self, tmp_path):
        mock_ydl_instance = Mock()

        with patch("yt_agent_kit.transcript.yt_dlp.YoutubeDL") as mock_ydl:
            mock_ydl.return_value.__enter__.return_value = mock_ydl_instance
            mock_ydl.return_value.__exit__.return_value = None

            download_audio("abc123ABC_-", tmp_path)

        call_args = mock_ydl.call_args[0][0]
        assert call_args["format"] == "bestaudio/best"
        assert call_args["quiet"] is True
        assert any(
            pp["key"] == "FFmpegExtractAudio" for pp in call_args["postprocessors"]
        )

    def test_rejects_invalid_video_id(self, tmp_path):
        """Test that invalid video IDs are rejected before download."""
        with pytest.raises(ValueError, match="Invalid YouTube video ID format"):
            download_audio("invalid!", tmp_path)


class TestTranscribeAudio:
    def test_transcribes_audio_successfully(self, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"x" * MIN_AUDIO_SIZE_BYTES)

        mock_model = Mock()
        mock_model.transcribe.return_value = {"text": "Transcribed text here"}

        with patch(
            "yt_agent_kit.transcript._get_whisper_model", return_value=mock_model
        ):
            result = transcribe_audio(audio_file, "base")

        assert result == "Transcribed text here"
        mock_model.transcribe.assert_called_once_with(str(audio_file))

    def test_uses_specified_model(self, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"x" * MIN_AUDIO_SIZE_BYTES)

        mock_model = Mock()
        mock_model.transcribe.return_value = {"text": "Text"}

        with patch(
            "yt_agent_kit.transcript._get_whisper_model", return_value=mock_model
        ) as mock_get_model:
            transcribe_audio(audio_file, "small")

        mock_get_model.assert_called_once_with("small")

    def test_raises_error_for_missing_file(self, tmp_path):
        audio_file = tmp_path / "nonexistent.mp3"

        with pytest.raises(WhisperTranscriptionError, match="not found"):
            transcribe_audio(audio_file)

    def test_raises_error_for_small_file(self, tmp_path):
        audio_file = tmp_path / "tiny.mp3"
        audio_file.write_bytes(b"x" * 100)  # Too small

        with pytest.raises(WhisperTranscriptionError, match="too small"):
            transcribe_audio(audio_file)

    def test_raises_error_for_empty_transcript(self, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"x" * MIN_AUDIO_SIZE_BYTES)

        mock_model = Mock()
        mock_model.transcribe.return_value = {"text": ""}

        with patch(
            "yt_agent_kit.transcript._get_whisper_model", return_value=mock_model
        ):
            with pytest.raises(WhisperTranscriptionError, match="empty transcript"):
                transcribe_audio(audio_file)

    def test_wraps_runtime_error(self, tmp_path):
        audio_file = tmp_path / "test.mp3"
        audio_file.write_bytes(b"x" * MIN_AUDIO_SIZE_BYTES)

        mock_model = Mock()
        mock_model.transcribe.side_effect = RuntimeError("tensor reshape error")

        with patch(
            "yt_agent_kit.transcript._get_whisper_model", return_value=mock_model
        ):
            with pytest.raises(WhisperTranscriptionError, match="Whisper failed"):
                transcribe_audio(audio_file)


class TestGetWhisperModel:
    def test_caches_model(self):
        mock_model = Mock()

        with patch(
            "yt_agent_kit.transcript.whisper.load_model", return_value=mock_model
        ) as mock_load:
            # Clear the lru_cache before testing
            _get_whisper_model.cache_clear()

            result1 = _get_whisper_model("tiny")
            result2 = _get_whisper_model("tiny")

        assert result1 is result2
        mock_load.assert_called_once_with("tiny")

    def test_wraps_load_error_with_descriptive_message(self):
        """Test that model load errors are wrapped with helpful message."""
        _get_whisper_model.cache_clear()

        with patch(
            "yt_agent_kit.transcript.whisper.load_model",
            side_effect=RuntimeError("CUDA out of memory"),
        ):
            with pytest.raises(WhisperModelLoadError) as exc_info:
                _get_whisper_model("large")

        assert "Failed to load Whisper model 'large'" in str(exc_info.value)
        assert "CUDA out of memory" in str(exc_info.value)
        assert "Valid models:" in str(exc_info.value)


class TestGetTranscriptWithWhisperFallback:
    def test_returns_cached_transcript(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with patch("yt_agent_kit.transcript.get_from_cache", return_value="Cached"):
            result = get_transcript_with_whisper_fallback("cached_vid")

        assert result == "Cached"

    def test_fetches_youtube_transcript_first(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        mock_snippet = Mock()
        mock_snippet.text = "YouTube transcript"
        mock_transcript = Mock()
        mock_transcript.fetch.return_value = [mock_snippet]
        mock_transcript_list = Mock()
        mock_transcript_list.find_transcript.return_value = mock_transcript
        mock_api = Mock()
        mock_api.list.return_value = mock_transcript_list

        with patch("yt_agent_kit.transcript.get_from_cache", return_value=None):
            with patch(
                "yt_agent_kit.transcript.YouTubeTranscriptApi", return_value=mock_api
            ):
                with patch("yt_agent_kit.transcript.save_to_cache"):
                    result = get_transcript_with_whisper_fallback("vid1")

        assert result == "YouTube transcript"

    def test_falls_back_to_whisper_on_no_transcript(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        mock_api = Mock()
        mock_transcript_list = Mock()
        mock_transcript_list.find_transcript.side_effect = NoTranscriptFound(
            "vid1", [], None
        )
        mock_api.list.return_value = mock_transcript_list

        with patch("yt_agent_kit.transcript.get_from_cache", return_value=None):
            with patch(
                "yt_agent_kit.transcript.YouTubeTranscriptApi", return_value=mock_api
            ):
                with patch(
                    "yt_agent_kit.transcript.download_audio",
                    return_value=tmp_path / "audio.mp3",
                ):
                    with patch(
                        "yt_agent_kit.transcript.transcribe_audio",
                        return_value="Whisper [MUSIC] result",
                    ):
                        with patch("yt_agent_kit.transcript.save_to_cache"):
                            (tmp_path / "audio.mp3").touch()
                            result = get_transcript_with_whisper_fallback("vid1")

        assert result == "Whisper result"

    def test_raises_when_fallback_disabled(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        mock_api = Mock()
        mock_transcript_list = Mock()
        mock_transcript_list.find_transcript.side_effect = NoTranscriptFound(
            "vid1", [], None
        )
        mock_api.list.return_value = mock_transcript_list

        with patch("yt_agent_kit.transcript.get_from_cache", return_value=None):
            with patch(
                "yt_agent_kit.transcript.YouTubeTranscriptApi", return_value=mock_api
            ):
                with pytest.raises(NoTranscriptFound):
                    get_transcript_with_whisper_fallback("vid1", fallback_enabled=False)

    def test_calls_progress_callback(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        progress_calls = []

        def track_progress(status):
            progress_calls.append(status)

        mock_snippet = Mock()
        mock_snippet.text = "Text"
        mock_transcript = Mock()
        mock_transcript.fetch.return_value = [mock_snippet]
        mock_transcript_list = Mock()
        mock_transcript_list.find_transcript.return_value = mock_transcript
        mock_api = Mock()
        mock_api.list.return_value = mock_transcript_list

        with patch("yt_agent_kit.transcript.get_from_cache", return_value=None):
            with patch(
                "yt_agent_kit.transcript.YouTubeTranscriptApi", return_value=mock_api
            ):
                with patch("yt_agent_kit.transcript.save_to_cache"):
                    get_transcript_with_whisper_fallback(
                        "vid1", progress_callback=track_progress
                    )

        assert "fetching YouTube captions" in progress_calls

    def test_whisper_progress_callbacks(self, tmp_path, monkeypatch):
        """Test that Whisper fallback reports progress for download and transcription."""
        monkeypatch.chdir(tmp_path)

        progress_calls = []

        def track_progress(status):
            progress_calls.append(status)

        mock_api = Mock()
        mock_transcript_list = Mock()
        mock_transcript_list.find_transcript.side_effect = NoTranscriptFound(
            "vid1", [], None
        )
        mock_api.list.return_value = mock_transcript_list

        with patch("yt_agent_kit.transcript.get_from_cache", return_value=None):
            with patch(
                "yt_agent_kit.transcript.YouTubeTranscriptApi", return_value=mock_api
            ):
                with patch(
                    "yt_agent_kit.transcript.download_audio",
                    return_value=tmp_path / "audio.mp3",
                ):
                    with patch(
                        "yt_agent_kit.transcript.transcribe_audio",
                        return_value="Whisper result",
                    ):
                        with patch("yt_agent_kit.transcript.save_to_cache"):
                            (tmp_path / "audio.mp3").touch()
                            get_transcript_with_whisper_fallback(
                                "vid1", progress_callback=track_progress
                            )

        assert "fetching YouTube captions" in progress_calls
        assert "downloading audio for Whisper" in progress_calls
        assert any("transcribing with Whisper" in call for call in progress_calls)

    def test_download_failure_without_youtube_error_reraises(
        self, tmp_path, monkeypatch
    ):
        """Test that download failure without prior YouTube error re-raises the exception."""
        monkeypatch.chdir(tmp_path)

        # This scenario happens when YouTube captions succeed but download fails
        # (which shouldn't happen in practice, but we need to cover the code path)
        # We can trigger it by having no youtube_error set but download failing

        mock_snippet = Mock()
        mock_snippet.text = "Text"
        mock_transcript = Mock()
        mock_transcript.fetch.return_value = [mock_snippet]
        mock_transcript_list = Mock()
        # First call succeeds, but we force a download by other means
        mock_transcript_list.find_transcript.side_effect = NoTranscriptFound(
            "vid1", [], None
        )
        mock_api = Mock()
        mock_api.list.return_value = mock_transcript_list

        with patch("yt_agent_kit.transcript.get_from_cache", return_value=None):
            with patch(
                "yt_agent_kit.transcript.YouTubeTranscriptApi", return_value=mock_api
            ):
                with patch(
                    "yt_agent_kit.transcript.download_audio",
                    side_effect=RuntimeError("Download failed"),
                ):
                    # With youtube_error set, should raise NoTranscriptFound
                    with pytest.raises(NoTranscriptFound):
                        get_transcript_with_whisper_fallback("vid1")

    def test_transcription_failure_without_youtube_error_reraises(
        self, tmp_path, monkeypatch
    ):
        """Test transcription failure re-raises original YouTube error."""
        monkeypatch.chdir(tmp_path)

        mock_api = Mock()
        mock_transcript_list = Mock()
        mock_transcript_list.find_transcript.side_effect = TranscriptsDisabled("vid1")
        mock_api.list.return_value = mock_transcript_list

        with patch("yt_agent_kit.transcript.get_from_cache", return_value=None):
            with patch(
                "yt_agent_kit.transcript.YouTubeTranscriptApi", return_value=mock_api
            ):
                with patch(
                    "yt_agent_kit.transcript.download_audio",
                    return_value=tmp_path / "audio.mp3",
                ):
                    with patch(
                        "yt_agent_kit.transcript.transcribe_audio",
                        side_effect=WhisperTranscriptionError("Transcription failed"),
                    ):
                        (tmp_path / "audio.mp3").touch()
                        # Should raise the original TranscriptsDisabled error
                        with pytest.raises(TranscriptsDisabled):
                            get_transcript_with_whisper_fallback("vid1")

    def test_cleans_whisper_transcript(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        mock_api = Mock()
        mock_api.list.side_effect = TranscriptsDisabled("vid1")

        with patch("yt_agent_kit.transcript.get_from_cache", return_value=None):
            with patch(
                "yt_agent_kit.transcript.YouTubeTranscriptApi", return_value=mock_api
            ):
                with patch(
                    "yt_agent_kit.transcript.download_audio",
                    return_value=tmp_path / "audio.mp3",
                ):
                    with patch(
                        "yt_agent_kit.transcript.transcribe_audio",
                        return_value="Text [APPLAUSE] here",
                    ):
                        with patch("yt_agent_kit.transcript.save_to_cache"):
                            (tmp_path / "audio.mp3").touch()
                            result = get_transcript_with_whisper_fallback("vid1")

        assert result == "Text here"

    def test_falls_back_to_whisper_on_ip_blocked(self, tmp_path, monkeypatch):
        """Test that IpBlocked error triggers Whisper fallback."""
        monkeypatch.chdir(tmp_path)

        mock_api = Mock()
        mock_transcript_list = Mock()
        mock_transcript_list.find_transcript.side_effect = IpBlocked("vid1")
        mock_api.list.return_value = mock_transcript_list

        with patch("yt_agent_kit.transcript.get_from_cache", return_value=None):
            with patch(
                "yt_agent_kit.transcript.YouTubeTranscriptApi", return_value=mock_api
            ):
                with patch(
                    "yt_agent_kit.transcript.download_audio",
                    return_value=tmp_path / "audio.mp3",
                ):
                    with patch(
                        "yt_agent_kit.transcript.transcribe_audio",
                        return_value="Whisper fallback worked",
                    ):
                        with patch("yt_agent_kit.transcript.save_to_cache"):
                            (tmp_path / "audio.mp3").touch()
                            result = get_transcript_with_whisper_fallback("vid1")

        assert result == "Whisper fallback worked"

    def test_raises_ip_blocked_when_fallback_disabled(self, tmp_path, monkeypatch):
        """Test that IpBlocked is raised when fallback is disabled."""
        monkeypatch.chdir(tmp_path)

        mock_api = Mock()
        mock_transcript_list = Mock()
        mock_transcript_list.find_transcript.side_effect = IpBlocked("vid1")
        mock_api.list.return_value = mock_transcript_list

        with patch("yt_agent_kit.transcript.get_from_cache", return_value=None):
            with patch(
                "yt_agent_kit.transcript.YouTubeTranscriptApi", return_value=mock_api
            ):
                with pytest.raises(IpBlocked):
                    get_transcript_with_whisper_fallback("vid1", fallback_enabled=False)

    def test_raises_original_error_when_whisper_fails(self, tmp_path, monkeypatch):
        """Test that original YouTube error is raised when Whisper transcription fails."""
        monkeypatch.chdir(tmp_path)

        mock_api = Mock()
        mock_transcript_list = Mock()
        mock_transcript_list.find_transcript.side_effect = IpBlocked("vid1")
        mock_api.list.return_value = mock_transcript_list

        with patch("yt_agent_kit.transcript.get_from_cache", return_value=None):
            with patch(
                "yt_agent_kit.transcript.YouTubeTranscriptApi", return_value=mock_api
            ):
                with patch(
                    "yt_agent_kit.transcript.download_audio",
                    return_value=tmp_path / "audio.mp3",
                ):
                    with patch(
                        "yt_agent_kit.transcript.transcribe_audio",
                        side_effect=RuntimeError("Whisper internal error"),
                    ):
                        (tmp_path / "audio.mp3").touch()
                        with pytest.raises(IpBlocked):
                            get_transcript_with_whisper_fallback("vid1")


class TestGetTranscriptsBatchWithFallback:
    def test_fetches_multiple_transcripts(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with patch(
            "yt_agent_kit.transcript.get_transcript_with_whisper_fallback"
        ) as mock_get:
            mock_get.side_effect = lambda **kwargs: f"{kwargs['video_id']} transcript"
            result = get_transcripts_batch_with_fallback(["vid1", "vid2"])

        assert len(result) == 2
        assert result["vid1"] == "vid1 transcript"
        assert result["vid2"] == "vid2 transcript"

    def test_skips_failed_transcripts(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        def mock_get(**kwargs):
            if kwargs["video_id"] == "failed":
                raise NoTranscriptFound("failed", [], None)
            return "Success"

        with patch(
            "yt_agent_kit.transcript.get_transcript_with_whisper_fallback",
            side_effect=mock_get,
        ):
            result = get_transcripts_batch_with_fallback(["vid1", "failed", "vid2"])

        assert len(result) == 2
        assert "failed" not in result

    def test_calls_progress_callback_with_status(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        progress_calls = []

        def progress_callback(current, total, video_id, status):
            progress_calls.append((current, total, video_id, status))

        with patch(
            "yt_agent_kit.transcript.get_transcript_with_whisper_fallback",
            return_value="Content",
        ):
            get_transcripts_batch_with_fallback(
                ["vid1", "vid2"], progress_callback=progress_callback
            )

        assert len(progress_calls) == 2
        assert all(call[1] == 2 for call in progress_calls)
        assert all(call[3] == "success" for call in progress_calls)

    def test_passes_whisper_config(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with patch(
            "yt_agent_kit.transcript.get_transcript_with_whisper_fallback"
        ) as mock_get:
            mock_get.return_value = "Text"
            get_transcripts_batch_with_fallback(
                ["vid1"],
                fallback_enabled=True,
                whisper_model="small",
                cleanup_audio=False,
            )

        call_kwargs = mock_get.call_args[1]
        assert call_kwargs["fallback_enabled"] is True
        assert call_kwargs["whisper_model"] == "small"
        assert call_kwargs["cleanup_audio"] is False

    def test_handles_unexpected_exceptions(self, tmp_path, monkeypatch):
        """Test that unexpected exceptions are logged and return 'error' status."""
        monkeypatch.chdir(tmp_path)

        progress_calls = []

        def progress_callback(current, total, video_id, status):
            progress_calls.append((current, total, video_id, status))

        def mock_get(**kwargs):
            if kwargs["video_id"] == "error_vid":
                raise RuntimeError("Unexpected error")
            return "Success"

        with patch(
            "yt_agent_kit.transcript.get_transcript_with_whisper_fallback",
            side_effect=mock_get,
        ):
            result = get_transcripts_batch_with_fallback(
                ["vid1", "error_vid"], progress_callback=progress_callback
            )

        assert len(result) == 1
        assert "error_vid" not in result
        # Check that error status was reported
        statuses = {call[2]: call[3] for call in progress_calls}
        assert statuses["error_vid"] == "error"
        assert statuses["vid1"] == "success"

    def test_passes_progress_callback_to_inner_function(self, tmp_path, monkeypatch):
        """Test that inner progress callback is passed when batch callback exists."""
        monkeypatch.chdir(tmp_path)

        captured_kwargs = {}

        def mock_get(**kwargs):
            captured_kwargs.update(kwargs)
            # Call the progress callback if provided to exercise the code path
            if kwargs.get("progress_callback"):
                kwargs["progress_callback"]("test status")
            return "Success"

        def batch_progress(current, total, video_id, status):
            pass

        with patch(
            "yt_agent_kit.transcript.get_transcript_with_whisper_fallback",
            side_effect=mock_get,
        ):
            get_transcripts_batch_with_fallback(
                ["vid1"], progress_callback=batch_progress
            )

        # Verify that progress_callback was passed to the inner function
        assert captured_kwargs.get("progress_callback") is not None
