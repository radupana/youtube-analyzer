from unittest.mock import Mock, patch

import pytest

from yt_agent_kit.agent import (
    ConversationState,
    ask_channel,
    ask_intent,
    ask_output_format,
    run_conversation,
)
from yt_agent_kit.config import Config, LLMConfig


@pytest.fixture
def config():
    return Config(
        channel="test",
        llm=LLMConfig(
            provider="gemini",
            api_key="test-api-key-1234567890",
            model="gemini-2.0-flash",
        ),
        youtube_api_key="youtube-api-key-1234567890",
        extractor="test",
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


class TestConversationState:
    def test_default_values(self):
        state = ConversationState()
        assert state.channel is None
        assert state.intent is None
        assert state.output_format == "human"

    def test_with_values(self):
        mock_channel = Mock()
        state = ConversationState(
            channel=mock_channel, intent="test", output_format="json"
        )
        assert state.channel == mock_channel
        assert state.intent == "test"
        assert state.output_format == "json"
