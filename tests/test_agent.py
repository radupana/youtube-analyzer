from unittest.mock import Mock, patch

import pytest

from yt_agent_kit.agent import (
    ConversationState,
    ask_channel,
    ask_intent,
    ask_output_format,
    ask_source,
    ask_video_count,
    parse_video_count,
    run_conversation,
)
from yt_agent_kit.config import Config, LLMConfig
from yt_agent_kit.youtube import InputType, VideoInfo


@pytest.fixture
def config():
    return Config(
        llm=LLMConfig(
            provider="gemini",
            api_key="test-api-key-1234567890",
            model="gemini-2.0-flash",
        ),
        youtube_api_key="youtube-api-key-1234567890",
    )


class TestAskChannel:
    def test_valid_channel_input(self, config, capsys):
        mock_channel = Mock()
        mock_channel.title = "Test Channel"
        mock_channel.subscriber_count = 1000000
        mock_channel.video_count = 500
        mock_channel.custom_url = "@test"
        mock_channel.description = "Test description"

        with patch("builtins.input", return_value="@testchannel"):
            with patch("yt_agent_kit.agent.find_channel_id", return_value=mock_channel):
                result = ask_channel(config)

        assert result.title == "Test Channel"
        captured = capsys.readouterr()
        assert "Test Channel" in captured.out
        assert "1,000,000" in captured.out

    def test_long_description_truncated(self, config, capsys):
        mock_channel = Mock()
        mock_channel.title = "Long Desc Channel"
        mock_channel.subscriber_count = 5000
        mock_channel.video_count = 100
        mock_channel.custom_url = None
        mock_channel.description = "a" * 200

        with patch("builtins.input", return_value="test"):
            with patch("yt_agent_kit.agent.find_channel_id", return_value=mock_channel):
                ask_channel(config)

        captured = capsys.readouterr()
        assert "..." in captured.out
        assert "a" * 200 not in captured.out

    def test_empty_channel_input(self, config):
        with patch("builtins.input", return_value=""):
            with pytest.raises(ValueError, match="Channel cannot be empty"):
                ask_channel(config)

    def test_channel_not_found(self, config):
        with patch("builtins.input", return_value="nonexistent"):
            with patch(
                "yt_agent_kit.agent.find_channel_id",
                side_effect=ValueError("Channel not found"),
            ):
                with pytest.raises(ValueError, match="Channel not found"):
                    ask_channel(config)

    def test_channel_input_too_long(self, config):
        long_input = "a" * 1001  # Exceeds MAX_INPUT_LENGTH (1000)
        with patch("builtins.input", return_value=long_input):
            with pytest.raises(ValueError, match="Input too long"):
                ask_channel(config)


class TestAskIntent:
    def test_valid_intent(self, capsys):
        with patch("builtins.input", return_value="summarize key advice"):
            result = ask_intent()

        assert result == "summarize key advice"
        captured = capsys.readouterr()
        assert "What are you looking to get out of the analysis?" in captured.out

    def test_empty_intent(self):
        with patch("builtins.input", return_value=""):
            with pytest.raises(ValueError, match="Intent cannot be empty"):
                ask_intent()

    def test_whitespace_only_intent(self):
        with patch("builtins.input", return_value="   "):
            with pytest.raises(ValueError, match="Intent cannot be empty"):
                ask_intent()

    def test_intent_input_too_long(self):
        long_input = "a" * 1001  # Exceeds MAX_INPUT_LENGTH (1000)
        with patch("builtins.input", return_value=long_input):
            with pytest.raises(ValueError, match="Input too long"):
                ask_intent()


class TestAskOutputFormat:
    def test_default_format(self):
        with patch("builtins.input", return_value=""):
            result = ask_output_format()
        assert result == "human"

    def test_human_format(self):
        with patch("builtins.input", return_value="1"):
            result = ask_output_format()
        assert result == "human"

    def test_json_format(self):
        with patch("builtins.input", return_value="2"):
            result = ask_output_format()
        assert result == "json"

    def test_markdown_format(self):
        with patch("builtins.input", return_value="3"):
            result = ask_output_format()
        assert result == "markdown"

    def test_invalid_format_defaults_to_human(self):
        with patch("builtins.input", return_value="99"):
            result = ask_output_format()
        assert result == "human"


class TestParseVideoCount:
    def test_empty_input_returns_default(self):
        result = parse_video_count("", max_allowed=100)
        assert result == 50

    def test_whitespace_input_returns_default(self):
        result = parse_video_count("   ", max_allowed=100)
        assert result == 50

    def test_valid_number(self):
        result = parse_video_count("25", max_allowed=100)
        assert result == 25

    def test_caps_at_max_allowed(self):
        result = parse_video_count("200", max_allowed=100)
        assert result == 100

    def test_negative_returns_default(self, capsys):
        result = parse_video_count("-5", max_allowed=100)
        assert result == 50
        captured = capsys.readouterr()
        assert "Must be at least 1" in captured.out

    def test_zero_returns_default(self, capsys):
        result = parse_video_count("0", max_allowed=100)
        assert result == 50
        captured = capsys.readouterr()
        assert "Must be at least 1" in captured.out

    def test_invalid_string_returns_default(self):
        result = parse_video_count("abc", max_allowed=100)
        assert result == 50

    def test_custom_default(self):
        result = parse_video_count("", max_allowed=100, default=25)
        assert result == 25

    def test_default_capped_at_max(self):
        result = parse_video_count("", max_allowed=30, default=50)
        assert result == 30


class TestAskVideoCount:
    def test_default_count(self):
        mock_channel = Mock()
        mock_channel.video_count = 100

        with patch("builtins.input", return_value=""):
            result = ask_video_count(mock_channel, max_videos=100)
        assert result == 50

    def test_custom_count(self):
        mock_channel = Mock()
        mock_channel.video_count = 100

        with patch("builtins.input", return_value="25"):
            result = ask_video_count(mock_channel, max_videos=100)
        assert result == 25

    def test_respects_channel_limit(self):
        mock_channel = Mock()
        mock_channel.video_count = 30

        with patch("builtins.input", return_value=""):
            result = ask_video_count(mock_channel, max_videos=100)
        assert result == 30

    def test_respects_config_limit(self):
        mock_channel = Mock()
        mock_channel.video_count = 200

        with patch("builtins.input", return_value=""):
            result = ask_video_count(mock_channel, max_videos=75)
        assert result == 50

    def test_retries_count_exceeding_maximum(self, capsys):
        mock_channel = Mock()
        mock_channel.video_count = 50

        with patch("builtins.input", side_effect=["100", "25"]):
            result = ask_video_count(mock_channel, max_videos=100)

        assert result == 25
        captured = capsys.readouterr()
        assert "Cannot exceed 50" in captured.out

    def test_retries_zero_count(self, capsys):
        mock_channel = Mock()
        mock_channel.video_count = 100

        with patch("builtins.input", side_effect=["0", "10"]):
            result = ask_video_count(mock_channel, max_videos=100)

        assert result == 10
        captured = capsys.readouterr()
        assert "Must be at least 1" in captured.out

    def test_retries_negative_count(self, capsys):
        mock_channel = Mock()
        mock_channel.video_count = 100

        with patch("builtins.input", side_effect=["-5", "10"]):
            result = ask_video_count(mock_channel, max_videos=100)

        assert result == 10
        captured = capsys.readouterr()
        assert "Must be at least 1" in captured.out

    def test_retries_non_numeric_input(self, capsys):
        mock_channel = Mock()
        mock_channel.video_count = 100

        with patch("builtins.input", side_effect=["abc", "10"]):
            result = ask_video_count(mock_channel, max_videos=100)

        assert result == 10
        captured = capsys.readouterr()
        assert "valid number" in captured.out


class TestRunConversation:
    def test_complete_conversation(self, config, capsys):
        mock_channel = Mock()
        mock_channel.title = "Complete Test"
        mock_channel.subscriber_count = 100000
        mock_channel.video_count = 200
        mock_channel.custom_url = "@complete"
        mock_channel.description = "Complete test channel"

        inputs = ["@complete", "test intent", "2"]

        with patch("builtins.input", side_effect=inputs):
            with patch("yt_agent_kit.agent.find_channel_id", return_value=mock_channel):
                state = run_conversation(config)

        assert state.channel.title == "Complete Test"
        assert state.intent == "test intent"
        assert state.output_format == "json"

        captured = capsys.readouterr()
        assert "Perfect! I have all the information I need." in captured.out
        assert "Complete Test" in captured.out
        assert "test intent" in captured.out
        assert "json" in captured.out

    def test_conversation_with_defaults(self, config):
        mock_channel = Mock()
        mock_channel.title = "Default Test"
        mock_channel.subscriber_count = 50000
        mock_channel.video_count = 150
        mock_channel.custom_url = None
        mock_channel.description = "Default test"

        inputs = ["test channel", "default intent", ""]

        with patch("builtins.input", side_effect=inputs):
            with patch("yt_agent_kit.agent.find_channel_id", return_value=mock_channel):
                state = run_conversation(config)

        assert state.channel.title == "Default Test"
        assert state.intent == "default intent"
        assert state.output_format == "human"


class TestAskSource:
    def test_video_url_input(self, config, capsys):
        mock_video = VideoInfo(
            id="abc123",
            title="Test Video Title",
            description="",
            published_at="2024-01-01T00:00:00Z",
            duration="PT10M",
        )

        with patch("builtins.input", return_value="https://youtube.com/watch?v=abc123"):
            with patch(
                "yt_agent_kit.agent.detect_input_type",
                return_value=(InputType.VIDEO, "abc123"),
            ):
                with patch(
                    "yt_agent_kit.agent.get_video_info", return_value=mock_video
                ):
                    input_type, collection_id, title, video_ids = ask_source(config)

        assert input_type == InputType.VIDEO
        assert collection_id == "video_abc123"
        assert title == "Test Video Title"
        assert video_ids == ["abc123"]

        captured = capsys.readouterr()
        assert "Found video: Test Video Title" in captured.out

    def test_playlist_url_input(self, config, capsys):
        mock_playlist = {"title": "Test Playlist", "id": "PLtest123"}

        with patch(
            "builtins.input",
            return_value="https://youtube.com/playlist?list=PLtest123",
        ):
            with patch(
                "yt_agent_kit.agent.detect_input_type",
                return_value=(InputType.PLAYLIST, "PLtest123"),
            ):
                with patch(
                    "yt_agent_kit.agent.get_playlist_info", return_value=mock_playlist
                ):
                    with patch(
                        "yt_agent_kit.agent.get_playlist_video_ids",
                        return_value=["vid1", "vid2", "vid3"],
                    ):
                        input_type, collection_id, title, video_ids = ask_source(config)

        assert input_type == InputType.PLAYLIST
        assert collection_id == "playlist_PLtest123"
        assert title == "Test Playlist"
        assert video_ids == ["vid1", "vid2", "vid3"]

        captured = capsys.readouterr()
        assert "Found playlist: Test Playlist (3 videos)" in captured.out

    def test_channel_handle_input(self, config, capsys):
        mock_channel = Mock()
        mock_channel.id = "UC123abc"
        mock_channel.title = "Test Channel"
        mock_channel.subscriber_count = 1000000
        mock_channel.video_count = 500

        with patch("builtins.input", return_value="@testchannel"):
            with patch(
                "yt_agent_kit.agent.detect_input_type",
                return_value=(InputType.CHANNEL, "@testchannel"),
            ):
                with patch(
                    "yt_agent_kit.agent.find_channel_id", return_value=mock_channel
                ):
                    input_type, collection_id, title, video_ids = ask_source(config)

        assert input_type == InputType.CHANNEL
        assert collection_id == "channel_UC123abc"
        assert title == "Test Channel"
        assert video_ids == []

        captured = capsys.readouterr()
        assert "Found channel: Test Channel" in captured.out
        assert "Subscribers: 1,000,000" in captured.out

    def test_empty_input_raises_error(self, config):
        with patch("builtins.input", return_value=""):
            with pytest.raises(ValueError, match="Input cannot be empty"):
                ask_source(config)

    def test_input_too_long_raises_error(self, config):
        long_input = "a" * 1001
        with patch("builtins.input", return_value=long_input):
            with pytest.raises(ValueError, match="Input too long"):
                ask_source(config)


class TestConversationState:
    def test_default_values(self):
        state = ConversationState()
        assert state.channel is None
        assert state.intent is None
        assert state.output_format == "human"
        assert state.max_videos == 50
        assert state.videos == []
        assert state.transcripts == {}

    def test_with_values(self):
        mock_channel = Mock()
        mock_video = Mock()
        state = ConversationState(
            channel=mock_channel,
            intent="test",
            output_format="json",
            max_videos=100,
            videos=[mock_video],
            transcripts={"vid1": "transcript"},
        )
        assert state.channel == mock_channel
        assert state.intent == "test"
        assert state.output_format == "json"
        assert state.max_videos == 100
        assert state.videos == [mock_video]
        assert state.transcripts == {"vid1": "transcript"}
