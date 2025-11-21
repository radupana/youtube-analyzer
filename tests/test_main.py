from unittest.mock import Mock, patch

from yt_agent_kit.__main__ import main, mask_sensitive
from yt_agent_kit.config import Config, LLMConfig


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

    def test_complete_flow(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        config = Config(
            llm=LLMConfig(
                provider="gemini",
                api_key="test-api-key-1234567890",
                model="gemini-2.0-flash",
            ),
            youtube_api_key="youtube-api-key-1234567890",
        )

        mock_channel = Mock()
        mock_channel.id = "UCtest123"
        mock_channel.title = "Test Channel"
        mock_channel.video_count = 100

        mock_state = Mock()
        mock_state.channel = mock_channel
        mock_state.intent = "test intent"
        mock_state.output_format = "json"
        mock_state.max_videos = 10
        mock_state.videos = [Mock(id="vid1", title="Video 1")]
        mock_state.transcripts = {"vid1": "transcript"}

        with patch("yt_agent_kit.__main__.load_config", return_value=config):
            with patch("yt_agent_kit.agent.run_conversation", return_value=mock_state):
                with patch("yt_agent_kit.agent.ask_video_count", return_value=10):
                    with patch(
                        "yt_agent_kit.youtube.list_videos",
                        return_value=mock_state.videos,
                    ):
                        with patch(
                            "yt_agent_kit.transcript.get_transcripts_batch",
                            return_value=mock_state.transcripts,
                        ):
                            with patch("sys.argv", ["yt_agent_kit"]):
                                exit_code = main()

        assert exit_code == 0

    def test_no_channel_selected_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        config = Config(
            llm=LLMConfig(
                provider="gemini",
                api_key="test-api-key-1234567890",
                model="gemini-2.0-flash",
            ),
            youtube_api_key="youtube-api-key-1234567890",
        )

        mock_state = Mock()
        mock_state.channel = None

        with patch("yt_agent_kit.__main__.load_config", return_value=config):
            with patch("yt_agent_kit.agent.run_conversation", return_value=mock_state):
                with patch("sys.argv", ["yt_agent_kit"]):
                    exit_code = main()

        assert exit_code == 1

    def test_config_override_max_videos(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        config = Config(
            llm=LLMConfig(
                provider="gemini",
                api_key="test-api-key-1234567890",
                model="gemini-2.0-flash",
            ),
            youtube_api_key="youtube-api-key-1234567890",
            max_videos=50,
        )

        mock_channel = Mock()
        mock_channel.id = "UCtest123"
        mock_channel.title = "Test Channel"
        mock_channel.video_count = 100

        mock_state = Mock()
        mock_state.channel = mock_channel
        mock_state.intent = "test"
        mock_state.output_format = "json"
        mock_state.max_videos = 25
        mock_state.videos = []
        mock_state.transcripts = {}

        with patch("yt_agent_kit.__main__.load_config", return_value=config):
            with patch("yt_agent_kit.agent.run_conversation", return_value=mock_state):
                with patch("yt_agent_kit.agent.ask_video_count", return_value=25):
                    with patch("yt_agent_kit.youtube.list_videos", return_value=[]):
                        with patch(
                            "yt_agent_kit.transcript.get_transcripts_batch",
                            return_value={},
                        ):
                            with patch(
                                "sys.argv", ["yt_agent_kit", "--max-videos", "25"]
                            ):
                                exit_code = main()

        assert exit_code == 0

    def test_config_override_output_file(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        config = Config(
            llm=LLMConfig(
                provider="gemini",
                api_key="test-api-key-1234567890",
                model="gemini-2.0-flash",
            ),
            youtube_api_key="youtube-api-key-1234567890",
        )

        mock_channel = Mock()
        mock_channel.id = "UCtest123"
        mock_channel.title = "Test Channel"
        mock_channel.video_count = 100

        mock_state = Mock()
        mock_state.channel = mock_channel
        mock_state.intent = "test"
        mock_state.output_format = "json"
        mock_state.max_videos = 10
        mock_state.videos = []
        mock_state.transcripts = {}

        with patch("yt_agent_kit.__main__.load_config", return_value=config):
            with patch("yt_agent_kit.agent.run_conversation", return_value=mock_state):
                with patch("yt_agent_kit.agent.ask_video_count", return_value=10):
                    with patch("yt_agent_kit.youtube.list_videos", return_value=[]):
                        with patch(
                            "yt_agent_kit.transcript.get_transcripts_batch",
                            return_value={},
                        ):
                            with patch(
                                "sys.argv", ["yt_agent_kit", "--output", "custom.json"]
                            ):
                                exit_code = main()

        assert exit_code == 0

    def test_unexpected_error_returns_1(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

        with patch(
            "yt_agent_kit.__main__.load_config", side_effect=RuntimeError("Unexpected")
        ):
            with patch("sys.argv", ["yt_agent_kit"]):
                exit_code = main()

        assert exit_code == 1
