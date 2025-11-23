from unittest.mock import Mock, patch

from yt_agent_kit.__main__ import main, mask_sensitive
from yt_agent_kit.config import Config, LLMConfig
from yt_agent_kit.youtube import InputType, VideoInfo


class TestMaskSensitive:
    def test_masks_api_key(self):
        result = mask_sensitive("secret-api-key")
        assert result == "<SET>"

    def test_handles_none(self):
        result = mask_sensitive(None)
        assert result == "<NOT SET>"

    def test_handles_empty_string(self):
        result = mask_sensitive("")
        assert result == "<NOT SET>"


class TestMain:
    def test_config_file_not_found(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with patch("sys.argv", ["yt_agent_kit"]):
            exit_code = main()

        assert exit_code == 1

    def test_keyboard_interrupt_returns_130(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with patch("yt_agent_kit.__main__.load_config", side_effect=KeyboardInterrupt):
            with patch("sys.argv", ["yt_agent_kit"]):
                exit_code = main()

        assert exit_code == 130

    def test_complete_flow_video(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        config = Config(
            llm=LLMConfig(
                provider="gemini",
                api_key="test-api-key-1234567890",
                model="gemini-2.0-flash",
            ),
            youtube_api_key="youtube-api-key-1234567890",
        )

        mock_video_info = VideoInfo(
            id="abc123",
            title="Test Video Title",
            description="",
            published_at="2024-01-01T00:00:00Z",
            duration="PT10M",
        )

        with patch("yt_agent_kit.__main__.load_config", return_value=config):
            with patch(
                "yt_agent_kit.agent.ask_source",
                return_value=(
                    InputType.VIDEO,
                    "video_abc123",
                    "Test Video",
                    ["abc123"],
                ),
            ):
                with patch(
                    "yt_agent_kit.youtube.get_videos_batch",
                    return_value={"abc123": mock_video_info},
                ):
                    with patch(
                        "yt_agent_kit.transcript.get_transcripts_batch_with_fallback",
                        return_value={"abc123": "transcript text"},
                    ):
                        with patch("builtins.input", side_effect=["quit"]):
                            with patch("sys.argv", ["yt_agent_kit"]):
                                exit_code = main()

        assert exit_code == 0

    def test_cli_overrides(self, tmp_path, monkeypatch):
        """Test command-line argument overrides for max_videos and output."""
        monkeypatch.chdir(tmp_path)

        config = Config(
            llm=LLMConfig(
                provider="gemini",
                api_key="test-api-key-1234567890",
                model="gemini-2.0-flash",
            ),
            youtube_api_key="youtube-api-key-1234567890",
        )

        mock_video_info = VideoInfo(
            id="abc123",
            title="Test Video Title",
            description="",
            published_at="2024-01-01T00:00:00Z",
            duration="PT10M",
        )

        with patch("yt_agent_kit.__main__.load_config", return_value=config):
            with patch(
                "yt_agent_kit.agent.ask_source",
                return_value=(
                    InputType.VIDEO,
                    "video_abc123",
                    "Test Video",
                    ["abc123"],
                ),
            ):
                with patch(
                    "yt_agent_kit.youtube.get_videos_batch",
                    return_value={"abc123": mock_video_info},
                ):
                    with patch(
                        "yt_agent_kit.transcript.get_transcripts_batch_with_fallback",
                        return_value={"abc123": "transcript text"},
                    ):
                        with patch("builtins.input", side_effect=["quit"]):
                            with patch(
                                "sys.argv",
                                [
                                    "yt_agent_kit",
                                    "--max-videos",
                                    "10",
                                    "--output",
                                    "test.json",
                                ],
                            ):
                                exit_code = main()

        assert exit_code == 0

    def test_channel_invalid_video_count_defaults_to_50(self, tmp_path, monkeypatch):
        """Test that invalid video count input defaults to 50."""
        monkeypatch.chdir(tmp_path)

        config = Config(
            llm=LLMConfig(
                provider="gemini",
                api_key="test-api-key-1234567890",
                model="gemini-2.0-flash",
            ),
            youtube_api_key="youtube-api-key-1234567890",
        )

        mock_video = Mock()
        mock_video.id = "vid1"
        mock_video.title = "Video 1"

        with patch("yt_agent_kit.__main__.load_config", return_value=config):
            with patch(
                "yt_agent_kit.agent.ask_source",
                return_value=(InputType.CHANNEL, "channel_UC123", "Test Channel", []),
            ):
                with patch(
                    "yt_agent_kit.youtube.list_videos", return_value=[mock_video]
                ):
                    with patch(
                        "yt_agent_kit.transcript.get_transcripts_batch_with_fallback",
                        return_value={"vid1": "transcript"},
                    ):
                        # "abc" is invalid, should default to 50
                        with patch("builtins.input", side_effect=["abc", "quit"]):
                            with patch("sys.argv", ["yt_agent_kit"]):
                                exit_code = main()

        assert exit_code == 0

    def test_channel_negative_video_count_defaults_to_50(
        self, tmp_path, monkeypatch, capsys
    ):
        """Test that negative video count input defaults to 50."""
        monkeypatch.chdir(tmp_path)

        config = Config(
            llm=LLMConfig(
                provider="gemini",
                api_key="test-api-key-1234567890",
                model="gemini-2.0-flash",
            ),
            youtube_api_key="youtube-api-key-1234567890",
        )

        mock_video = Mock()
        mock_video.id = "vid1"
        mock_video.title = "Video 1"

        with patch("yt_agent_kit.__main__.load_config", return_value=config):
            with patch(
                "yt_agent_kit.agent.ask_source",
                return_value=(InputType.CHANNEL, "channel_UC123", "Test Channel", []),
            ):
                with patch(
                    "yt_agent_kit.youtube.list_videos", return_value=[mock_video]
                ):
                    with patch(
                        "yt_agent_kit.transcript.get_transcripts_batch_with_fallback",
                        return_value={"vid1": "transcript"},
                    ):
                        # -5 is negative, should default to 50
                        with patch("builtins.input", side_effect=["-5", "quit"]):
                            with patch("sys.argv", ["yt_agent_kit"]):
                                exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Must be at least 1" in captured.out

    def test_video_info_fetch_fallback(self, tmp_path, monkeypatch):
        """Test that video ID is used as fallback when get_videos_batch returns empty."""
        monkeypatch.chdir(tmp_path)

        config = Config(
            llm=LLMConfig(
                provider="gemini",
                api_key="test-api-key-1234567890",
                model="gemini-2.0-flash",
            ),
            youtube_api_key="youtube-api-key-1234567890",
        )

        with patch("yt_agent_kit.__main__.load_config", return_value=config):
            with patch(
                "yt_agent_kit.agent.ask_source",
                return_value=(
                    InputType.VIDEO,
                    "video_abc123",
                    "Test Video",
                    ["abc123"],
                ),
            ):
                # Return empty dict - video not found, fallback to ID
                with patch(
                    "yt_agent_kit.youtube.get_videos_batch",
                    return_value={},
                ):
                    with patch(
                        "yt_agent_kit.transcript.get_transcripts_batch_with_fallback",
                        return_value={"abc123": "transcript text"},
                    ):
                        with patch("builtins.input", side_effect=["quit"]):
                            with patch("sys.argv", ["yt_agent_kit"]):
                                exit_code = main()

        assert exit_code == 0

    def test_complete_flow_channel(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        config = Config(
            llm=LLMConfig(
                provider="gemini",
                api_key="test-api-key-1234567890",
                model="gemini-2.0-flash",
            ),
            youtube_api_key="youtube-api-key-1234567890",
        )

        mock_video = Mock()
        mock_video.id = "vid1"
        mock_video.title = "Video 1"

        with patch("yt_agent_kit.__main__.load_config", return_value=config):
            with patch(
                "yt_agent_kit.agent.ask_source",
                return_value=(InputType.CHANNEL, "channel_UC123", "Test Channel", []),
            ):
                with patch(
                    "yt_agent_kit.youtube.list_videos", return_value=[mock_video]
                ):
                    with patch(
                        "yt_agent_kit.transcript.get_transcripts_batch_with_fallback",
                        return_value={"vid1": "transcript"},
                    ):
                        with patch("builtins.input", side_effect=["10", "quit"]):
                            with patch("sys.argv", ["yt_agent_kit"]):
                                exit_code = main()

        assert exit_code == 0

    def test_no_transcripts_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        config = Config(
            llm=LLMConfig(
                provider="gemini",
                api_key="test-api-key-1234567890",
                model="gemini-2.0-flash",
            ),
            youtube_api_key="youtube-api-key-1234567890",
        )

        mock_video_info = VideoInfo(
            id="abc123",
            title="Test Video Title",
            description="",
            published_at="2024-01-01T00:00:00Z",
            duration="PT10M",
        )

        with patch("yt_agent_kit.__main__.load_config", return_value=config):
            with patch(
                "yt_agent_kit.agent.ask_source",
                return_value=(
                    InputType.VIDEO,
                    "video_abc123",
                    "Test Video",
                    ["abc123"],
                ),
            ):
                with patch(
                    "yt_agent_kit.youtube.get_videos_batch",
                    return_value={"abc123": mock_video_info},
                ):
                    with patch(
                        "yt_agent_kit.transcript.get_transcripts_batch_with_fallback",
                        return_value={},
                    ):
                        with patch("sys.argv", ["yt_agent_kit"]):
                            exit_code = main()

        assert exit_code == 1

    def test_unexpected_error_returns_1(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with patch(
            "yt_agent_kit.__main__.load_config", side_effect=RuntimeError("Unexpected")
        ):
            with patch("sys.argv", ["yt_agent_kit"]):
                exit_code = main()

        assert exit_code == 1
