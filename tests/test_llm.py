from unittest.mock import MagicMock, patch

import pytest

from yt_agent_kit import llm
from yt_agent_kit.config import LLMConfig
from yt_agent_kit.llm import (
    DEFAULT_CONTEXT_LIMIT,
    LLMError,
    Message,
    call_gemini,
    call_llm,
    get_context_limit,
)


@pytest.fixture(autouse=True)
def clear_caches():
    """Clear caches before each test to ensure clean mocking."""
    llm._gemini_clients.clear()
    llm._context_limit_cache.clear()
    yield
    llm._gemini_clients.clear()
    llm._context_limit_cache.clear()


@pytest.fixture
def gemini_config():
    return LLMConfig(
        provider="gemini",
        api_key="test-api-key-that-is-long-enough",
        model="gemini-2.5-flash",
    )


class TestMessage:
    def test_message_creation(self):
        msg = Message(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_message_roles(self):
        user_msg = Message(role="user", content="Question")
        assistant_msg = Message(role="assistant", content="Answer")
        system_msg = Message(role="system", content="Instructions")

        assert user_msg.role == "user"
        assert assistant_msg.role == "assistant"
        assert system_msg.role == "system"


class TestCallGemini:
    def test_successful_response(self, gemini_config):
        with patch("yt_agent_kit.llm.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_response = MagicMock()
            mock_response.text = "Test response"
            mock_client.models.generate_content.return_value = mock_response

            messages = [Message(role="user", content="Hello")]
            result = call_gemini(messages, gemini_config)

            assert result == "Test response"
            mock_genai.Client.assert_called_once_with(
                api_key="test-api-key-that-is-long-enough"
            )

    def test_system_instruction_extracted(self, gemini_config):
        with patch("yt_agent_kit.llm.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_response = MagicMock()
            mock_response.text = "Response"
            mock_client.models.generate_content.return_value = mock_response

            messages = [
                Message(role="system", content="Be helpful"),
                Message(role="user", content="Hello"),
            ]
            call_gemini(messages, gemini_config)

            call_args = mock_client.models.generate_content.call_args
            config_arg = call_args.kwargs.get("config")
            assert config_arg.system_instruction == "Be helpful"

    def test_empty_response_raises_error(self, gemini_config):
        with patch("yt_agent_kit.llm.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_response = MagicMock()
            mock_response.text = None
            mock_client.models.generate_content.return_value = mock_response

            messages = [Message(role="user", content="Hello")]
            with pytest.raises(LLMError, match="Empty response"):
                call_gemini(messages, gemini_config)

    def test_api_error_wrapped(self, gemini_config):
        with patch("yt_agent_kit.llm.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.models.generate_content.side_effect = Exception("API failed")

            messages = [Message(role="user", content="Hello")]
            with pytest.raises(LLMError, match="Gemini API error"):
                call_gemini(messages, gemini_config)

    def test_multiple_messages_converted(self, gemini_config):
        with patch("yt_agent_kit.llm.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_response = MagicMock()
            mock_response.text = "Response"
            mock_client.models.generate_content.return_value = mock_response

            messages = [
                Message(role="user", content="First"),
                Message(role="assistant", content="Reply"),
                Message(role="user", content="Second"),
            ]
            call_gemini(messages, gemini_config)

            call_args = mock_client.models.generate_content.call_args
            contents = call_args.kwargs.get("contents")
            assert len(contents) == 3


class TestGetContextLimit:
    def test_explicit_config_returns_that_value(self):
        config = LLMConfig(
            provider="gemini",
            api_key="test-api-key-that-is-long-enough",
            model="gemini-2.5-flash",
            context_limit=50_000,
        )
        result = get_context_limit(config)
        assert result == 50_000

    def test_gemini_fetches_from_api(self):
        config = LLMConfig(
            provider="gemini",
            api_key="test-api-key-that-is-long-enough",
            model="gemini-2.5-flash",
        )
        with patch("yt_agent_kit.llm.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_model_info = MagicMock()
            mock_model_info.input_token_limit = 1_000_000
            mock_client.models.get.return_value = mock_model_info

            result = get_context_limit(config)

            assert result == 1_000_000
            mock_client.models.get.assert_called_once_with(model="gemini-2.5-flash")

    def test_caches_result(self):
        config = LLMConfig(
            provider="gemini",
            api_key="test-api-key-that-is-long-enough",
            model="gemini-2.5-flash",
        )
        with patch("yt_agent_kit.llm.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_model_info = MagicMock()
            mock_model_info.input_token_limit = 500_000
            mock_client.models.get.return_value = mock_model_info

            result1 = get_context_limit(config)
            result2 = get_context_limit(config)

            assert result1 == 500_000
            assert result2 == 500_000
            assert mock_client.models.get.call_count == 1

    def test_non_gemini_returns_default(self):
        config = LLMConfig(
            provider="openai",
            api_key="test-api-key-that-is-long-enough",
            model="gpt-4",
        )
        result = get_context_limit(config)
        assert result == DEFAULT_CONTEXT_LIMIT

    def test_api_failure_returns_default(self):
        config = LLMConfig(
            provider="gemini",
            api_key="test-api-key-that-is-long-enough",
            model="gemini-2.5-flash",
        )
        with patch("yt_agent_kit.llm.genai") as mock_genai:
            mock_client = MagicMock()
            mock_genai.Client.return_value = mock_client
            mock_client.models.get.side_effect = Exception("API error")

            result = get_context_limit(config)

            assert result == DEFAULT_CONTEXT_LIMIT


class TestCallLLM:
    def test_gemini_provider(self, gemini_config):
        with patch("yt_agent_kit.llm.call_gemini") as mock_call:
            mock_call.return_value = "Response"
            messages = [Message(role="user", content="Hello")]

            result = call_llm(messages, gemini_config)

            assert result == "Response"
            mock_call.assert_called_once_with(messages, gemini_config)

    def test_unsupported_provider_raises(self):
        config = LLMConfig(
            provider="openai",
            api_key="test-api-key-that-is-long-enough",
            model="gpt-4",
        )
        messages = [Message(role="user", content="Hello")]

        with pytest.raises(LLMError, match="Unsupported provider"):
            call_llm(messages, config)
