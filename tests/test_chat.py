from unittest.mock import patch

import pytest

from yt_agent_kit.chat import MAX_HISTORY_MESSAGES, SYSTEM_PROMPT, ChatSession
from yt_agent_kit.config import LLMConfig, SearchConfig
from yt_agent_kit.embeddings import Chunk
from yt_agent_kit.llm import Message


@pytest.fixture
def llm_config():
    return LLMConfig(
        provider="gemini",
        api_key="test-api-key-that-is-long-enough",
        model="gemini-2.5-flash",
    )


@pytest.fixture
def search_config():
    return SearchConfig(top_k=5)


@pytest.fixture
def chat_session(llm_config, search_config):
    return ChatSession(
        collection_id="test_collection",
        llm_config=llm_config,
        search_config=search_config,
    )


class TestChatSessionInit:
    def test_creates_with_required_params(self, llm_config):
        session = ChatSession(collection_id="test", llm_config=llm_config)
        assert session.collection_id == "test"
        assert session.llm_config == llm_config
        assert session.history == []

    def test_creates_with_custom_search_config(self, llm_config, search_config):
        session = ChatSession(
            collection_id="test",
            llm_config=llm_config,
            search_config=search_config,
        )
        assert session.search_config.top_k == 5


class TestFormatContext:
    def test_empty_chunks_returns_no_context(self, chat_session):
        result = chat_session._format_context([])
        assert result == "No relevant context found."

    def test_single_chunk_formatted(self, chat_session):
        chunks = [
            Chunk(
                content="Test content here",
                video_id="vid1",
                video_title="Test Video",
                chunk_index=0,
            )
        ]
        result = chat_session._format_context(chunks)
        assert '[Video: "Test Video"]' in result
        assert '"Test content here"' in result

    def test_multiple_chunks_separated(self, chat_session):
        chunks = [
            Chunk(
                content="First content",
                video_id="vid1",
                video_title="Video One",
                chunk_index=0,
            ),
            Chunk(
                content="Second content",
                video_id="vid2",
                video_title="Video Two",
                chunk_index=0,
            ),
        ]
        result = chat_session._format_context(chunks)
        assert '[Video: "Video One"]' in result
        assert '[Video: "Video Two"]' in result
        assert "---" in result


class TestBuildMessages:
    def test_includes_system_prompt(self, chat_session):
        messages = chat_session._build_messages("question", "context")
        assert messages[0].role == "system"
        assert messages[0].content == SYSTEM_PROMPT

    def test_includes_question_with_context(self, chat_session):
        messages = chat_session._build_messages("What is X?", "X is Y")
        user_message = messages[-1]
        assert user_message.role == "user"
        assert "What is X?" in user_message.content
        assert "X is Y" in user_message.content

    def test_includes_history(self, chat_session):
        chat_session.history = [
            Message(role="user", content="Previous Q"),
            Message(role="assistant", content="Previous A"),
        ]
        messages = chat_session._build_messages("New Q", "context")
        assert len(messages) == 4
        assert messages[1].content == "Previous Q"
        assert messages[2].content == "Previous A"

    def test_truncates_long_history(self, chat_session):
        chat_session.history = [
            Message(role="user", content=f"Q{i}")
            for i in range(MAX_HISTORY_MESSAGES + 10)
        ]
        messages = chat_session._build_messages("New Q", "context")
        history_in_messages = [m for m in messages if m.role != "system"][:-1]
        assert len(history_in_messages) == MAX_HISTORY_MESSAGES


class TestAsk:
    def test_searches_and_calls_llm(self, chat_session):
        with (
            patch("yt_agent_kit.chat.search") as mock_search,
            patch("yt_agent_kit.chat.call_llm") as mock_llm,
        ):
            mock_search.return_value = [
                Chunk(
                    content="Relevant info",
                    video_id="vid1",
                    video_title="Source Video",
                    chunk_index=0,
                )
            ]
            mock_llm.return_value = "The answer is X"

            result = chat_session.ask("What is X?")

            assert result == "The answer is X"
            mock_search.assert_called_once_with("test_collection", "What is X?", k=5)
            mock_llm.assert_called_once()

    def test_updates_history(self, chat_session):
        with (
            patch("yt_agent_kit.chat.search") as mock_search,
            patch("yt_agent_kit.chat.call_llm") as mock_llm,
        ):
            mock_search.return_value = []
            mock_llm.return_value = "Response"

            chat_session.ask("Question")

            assert len(chat_session.history) == 2
            assert chat_session.history[0].role == "user"
            assert chat_session.history[0].content == "Question"
            assert chat_session.history[1].role == "assistant"
            assert chat_session.history[1].content == "Response"

    def test_uses_search_config_top_k(self, llm_config):
        session = ChatSession(
            collection_id="test",
            llm_config=llm_config,
            search_config=SearchConfig(top_k=10),
        )
        with (
            patch("yt_agent_kit.chat.search") as mock_search,
            patch("yt_agent_kit.chat.call_llm") as mock_llm,
        ):
            mock_search.return_value = []
            mock_llm.return_value = "Response"

            session.ask("Question")

            mock_search.assert_called_once_with("test", "Question", k=10)


class TestClearHistory:
    def test_clears_all_history(self, chat_session):
        chat_session.history = [
            Message(role="user", content="Q1"),
            Message(role="assistant", content="A1"),
        ]

        chat_session.clear_history()

        assert chat_session.history == []
