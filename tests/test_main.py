from unittest.mock import Mock, patch

from yt_agent_kit.__main__ import main, mask_sensitive
from yt_agent_kit.config import Config, LLMConfig
from yt_agent_kit.youtube import InputType


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
                    "yt_agent_kit.transcript.get_transcripts_batch",
                    return_value={"abc123": "transcript text"},
                ):
                    with patch("yt_agent_kit.embeddings.build_index", return_value=1):
                        with patch(
                            "yt_agent_kit.embeddings.get_index_stats",
                            return_value={
                                "total_chunks": 5,
                                "total_videos": 1,
                                "index_size_mb": 0.1,
                            },
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
                        "yt_agent_kit.transcript.get_transcripts_batch",
                        return_value={"vid1": "transcript"},
                    ):
                        with patch(
                            "yt_agent_kit.embeddings.build_index", return_value=1
                        ):
                            with patch(
                                "yt_agent_kit.embeddings.get_index_stats",
                                return_value={
                                    "total_chunks": 5,
                                    "total_videos": 1,
                                    "index_size_mb": 0.1,
                                },
                            ):
                                with patch(
                                    "builtins.input", side_effect=["10", "quit"]
                                ):
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
                    "yt_agent_kit.transcript.get_transcripts_batch",
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
