"""Tests for Whisper service memory management."""

import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from app.services import whisper as whisper_module


@pytest.fixture(autouse=True)
def reset_whisper_state():
    """Reset module state before and after each test."""
    whisper_module._model = None
    whisper_module._model_name = None
    whisper_module._last_used = 0.0
    if whisper_module._unload_timer:
        whisper_module._unload_timer.cancel()
    whisper_module._unload_timer = None
    yield
    whisper_module._model = None
    whisper_module._model_name = None
    whisper_module._last_used = 0.0
    if whisper_module._unload_timer:
        whisper_module._unload_timer.cancel()
    whisper_module._unload_timer = None


class TestWhisperModelLifecycle:
    def test_model_loads_on_first_use(self):
        mock_model = MagicMock()

        with patch.object(whisper_module, "whisper") as mock_whisper:
            mock_whisper.load_model.return_value = mock_model

            with patch("app.services.whisper.get_whisper_config") as mock_config:
                mock_config.return_value = MagicMock(
                    model="base",
                    unload_timeout=300,
                )

                model = whisper_module._get_model()

                assert model is mock_model
                assert whisper_module._model is mock_model
                mock_whisper.load_model.assert_called_once_with("base")

    def test_model_reuses_existing(self):
        mock_model = MagicMock()
        whisper_module._model = mock_model
        whisper_module._model_name = "base"

        with patch("app.services.whisper.get_whisper_config") as mock_config:
            mock_config.return_value = MagicMock(
                model="base",
                unload_timeout=300,
            )

            with patch.object(whisper_module, "whisper") as mock_whisper:
                result = whisper_module._get_model()

                assert result is mock_model
                mock_whisper.load_model.assert_not_called()

    def test_model_switches_when_config_changes(self):
        old_model = MagicMock()
        new_model = MagicMock()
        whisper_module._model = old_model
        whisper_module._model_name = "base"

        with patch.object(whisper_module, "whisper") as mock_whisper:
            mock_whisper.load_model.return_value = new_model

            with patch("app.services.whisper.get_whisper_config") as mock_config:
                mock_config.return_value = MagicMock(
                    model="large",
                    unload_timeout=300,
                )

                result = whisper_module._get_model()

                assert result is new_model
                assert whisper_module._model_name == "large"
                mock_whisper.load_model.assert_called_once_with("large")

    def test_unload_clears_model(self):
        whisper_module._model = MagicMock()
        whisper_module._model_name = "base"
        whisper_module._last_used = time.time()

        whisper_module.unload_model()

        assert whisper_module._model is None
        assert whisper_module._model_name is None

    def test_unload_when_not_loaded(self):
        whisper_module._model = None
        whisper_module.unload_model()
        assert whisper_module._model is None

    def test_is_model_loaded_false(self):
        whisper_module._model = None
        assert whisper_module.is_model_loaded() is False

    def test_is_model_loaded_true(self):
        whisper_module._model = MagicMock()
        assert whisper_module.is_model_loaded() is True

    def test_get_model_info_when_loaded(self):
        whisper_module._model = MagicMock()
        whisper_module._model_name = "base"
        whisper_module._last_used = time.time() - 60

        info = whisper_module.get_model_info()

        assert info["loaded"] is True
        assert info["model_name"] == "base"
        assert info["idle_seconds"] >= 60
        assert info["last_used"] is not None

    def test_get_model_info_when_not_loaded(self):
        info = whisper_module.get_model_info()

        assert info["loaded"] is False
        assert info["model_name"] is None
        assert info["idle_seconds"] is None
        assert info["last_used"] is None

    def test_raises_when_whisper_not_installed(self):
        with patch.object(whisper_module, "whisper", None):
            with patch("app.services.whisper.get_whisper_config") as mock_config:
                mock_config.return_value = MagicMock(
                    model="base",
                    unload_timeout=300,
                )

                with pytest.raises(RuntimeError) as exc_info:
                    whisper_module._get_model()

                assert "not installed" in str(exc_info.value)


class TestWhisperAutoUnload:
    def test_timer_scheduled_on_load(self):
        with patch.object(whisper_module, "whisper") as mock_whisper:
            mock_whisper.load_model.return_value = MagicMock()

            with patch("app.services.whisper.get_whisper_config") as mock_config:
                mock_config.return_value = MagicMock(
                    model="base",
                    unload_timeout=300,
                )

                whisper_module._get_model()

                assert whisper_module._unload_timer is not None

    def test_timer_not_scheduled_when_disabled(self):
        with patch.object(whisper_module, "whisper") as mock_whisper:
            mock_whisper.load_model.return_value = MagicMock()

            with patch("app.services.whisper.get_whisper_config") as mock_config:
                mock_config.return_value = MagicMock(
                    model="base",
                    unload_timeout=0,
                )

                whisper_module._get_model()

                assert whisper_module._unload_timer is None

    def test_auto_unload_after_timeout(self):
        with patch.object(whisper_module, "whisper") as mock_whisper:
            mock_whisper.load_model.return_value = MagicMock()

            with patch("app.services.whisper.get_whisper_config") as mock_config:
                mock_config.return_value = MagicMock(
                    model="base",
                    unload_timeout=1,
                )

                whisper_module._get_model()
                assert whisper_module._model is not None

                # Poll for model unload with timeout (more reliable than fixed sleep)
                max_wait = 3.0
                poll_interval = 0.1
                waited = 0.0
                while whisper_module._model is not None and waited < max_wait:
                    time.sleep(poll_interval)
                    waited += poll_interval

                assert (
                    whisper_module._model is None
                ), f"Model not unloaded after {max_wait}s"


class TestWhisperThreadSafety:
    def test_concurrent_loads(self):
        load_count = 0

        def mock_load(name):
            nonlocal load_count
            load_count += 1
            time.sleep(0.1)
            return MagicMock()

        with patch.object(whisper_module, "whisper") as mock_whisper:
            mock_whisper.load_model.side_effect = mock_load

            with patch("app.services.whisper.get_whisper_config") as mock_config:
                mock_config.return_value = MagicMock(
                    model="base",
                    unload_timeout=300,
                )

                threads = []
                for _ in range(5):
                    t = threading.Thread(target=whisper_module._get_model)
                    threads.append(t)
                    t.start()

                for t in threads:
                    t.join()

                assert load_count == 1


class TestTranscribeAudio:
    def test_transcribe_audio_success(self):
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {
            "text": "  Hello world  ",
            "language": "en",
        }

        with patch.object(whisper_module, "whisper") as mock_whisper:
            mock_whisper.load_model.return_value = mock_model

            with (
                patch("app.services.whisper.get_whisper_config") as mock_config,
                patch("os.path.getsize", return_value=10000),
            ):
                mock_config.return_value = MagicMock(
                    model="base",
                    unload_timeout=300,
                )

                result = whisper_module._transcribe_audio(
                    "/path/to/audio.mp3", "test_video_id"
                )

                assert result == ("Hello world", "en")
                mock_model.transcribe.assert_called_once()

    def test_transcribe_audio_error(self):
        mock_model = MagicMock()
        mock_model.transcribe.side_effect = Exception("Transcription failed")

        with patch.object(whisper_module, "whisper") as mock_whisper:
            mock_whisper.load_model.return_value = mock_model

            with (
                patch("app.services.whisper.get_whisper_config") as mock_config,
                patch("os.path.getsize", return_value=10000),
            ):
                mock_config.return_value = MagicMock(
                    model="base",
                    unload_timeout=300,
                )

                result = whisper_module._transcribe_audio(
                    "/path/to/audio.mp3", "test_video_id"
                )

                assert result is None

    def test_transcribe_audio_file_too_small(self):
        with patch("os.path.getsize", return_value=500):
            result = whisper_module._transcribe_audio(
                "/path/to/audio.mp3", "test_video_id"
            )
            assert result is None

    def test_transcribe_audio_with_progress_callback(self):
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {"text": "Hello world", "language": "en"}
        progress_calls = []

        def track_progress(step, message):
            progress_calls.append((step, message))

        with patch.object(whisper_module, "whisper") as mock_whisper:
            mock_whisper.load_model.return_value = mock_model

            with (
                patch("app.services.whisper.get_whisper_config") as mock_config,
                patch("os.path.getsize", return_value=10000),
            ):
                mock_config.return_value = MagicMock(
                    model="base",
                    unload_timeout=300,
                )

                result = whisper_module._transcribe_audio(
                    "/path/to/audio.mp3",
                    "test_video_id",
                    progress_callback=track_progress,
                    duration_msg=" (~30s audio)",
                )

                assert result == ("Hello world", "en")
                assert len(progress_calls) == 1
                assert progress_calls[0][0] == "whisper_transcribing"
                assert "~30s audio" in progress_calls[0][1]

    def test_transcribe_sets_current_video_id(self):
        mock_model = MagicMock()
        mock_model.transcribe.return_value = {"text": "Hello"}
        captured_video_id = None

        def capture_current(*args, **kwargs):
            nonlocal captured_video_id
            captured_video_id = whisper_module._current_video_id
            return {"text": "Hello"}

        mock_model.transcribe.side_effect = capture_current

        with patch.object(whisper_module, "whisper") as mock_whisper:
            mock_whisper.load_model.return_value = mock_model

            with (
                patch("app.services.whisper.get_whisper_config") as mock_config,
                patch("os.path.getsize", return_value=10000),
            ):
                mock_config.return_value = MagicMock(
                    model="base",
                    unload_timeout=300,
                )

                whisper_module._transcribe_audio("/path/to/audio.mp3", "my_video_123")

                assert captured_video_id == "my_video_123"
                # After transcription, should be cleared
                assert whisper_module._current_video_id is None


class TestTranscriptionStatus:
    def test_is_transcription_in_progress_false(self):
        whisper_module._current_video_id = None
        assert whisper_module.is_transcription_in_progress() is False

    def test_is_transcription_in_progress_true(self):
        whisper_module._current_video_id = "some_video"
        assert whisper_module.is_transcription_in_progress() is True
        whisper_module._current_video_id = None

    def test_get_current_transcription_none(self):
        whisper_module._current_video_id = None
        assert whisper_module.get_current_transcription() is None

    def test_get_current_transcription_returns_video_id(self):
        whisper_module._current_video_id = "video_abc"
        assert whisper_module.get_current_transcription() == "video_abc"
        whisper_module._current_video_id = None

    def test_get_model_info_includes_transcribing(self):
        whisper_module._current_video_id = "transcribing_video"
        info = whisper_module.get_model_info()
        assert info["transcribing"] == "transcribing_video"
        whisper_module._current_video_id = None


class TestDownloadFunctions:
    def test_download_with_ytdlp_exception(self):
        with patch("yt_dlp.YoutubeDL") as mock_ydl:
            mock_ydl.return_value.__enter__ = MagicMock(
                side_effect=Exception("Download failed")
            )
            result = whisper_module._download_with_ytdlp("test123", "/tmp")
            assert result is None

    def test_download_with_ytdlp_file_too_small(self):
        with (
            patch("yt_dlp.YoutubeDL") as mock_ydl,
            patch("os.path.exists", return_value=True),
            patch("os.path.getsize", return_value=500),
        ):
            mock_instance = MagicMock()
            mock_ydl.return_value.__enter__.return_value = mock_instance
            mock_ydl.return_value.__exit__ = MagicMock(return_value=False)

            result = whisper_module._download_with_ytdlp("test123", "/tmp")
            assert result is None


class TestGetWhisperTranscript:
    def test_get_whisper_transcript_download_fails(self):
        with patch.object(whisper_module, "_download_with_ytdlp", return_value=None):
            result = whisper_module.get_whisper_transcript("test123")
            assert result is None

    def test_get_whisper_transcript_exception(self):
        with patch.object(
            whisper_module,
            "_download_with_ytdlp",
            side_effect=Exception("Unexpected error"),
        ):
            result = whisper_module.get_whisper_transcript("test123")
            assert result is None

    def test_get_whisper_transcript_with_progress_callback(self):
        progress_calls = []

        def track_progress(step, message):
            progress_calls.append((step, message))

        with patch.object(whisper_module, "_download_with_ytdlp", return_value=None):
            whisper_module.get_whisper_transcript("test123", track_progress)

            assert any("download" in call[1].lower() for call in progress_calls)
