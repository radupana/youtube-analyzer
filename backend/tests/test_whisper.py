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

                time.sleep(1.5)

                assert whisper_module._model is None


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
        mock_model.transcribe.return_value = {"text": "  Hello world  "}

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

                assert result == "Hello world"
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
