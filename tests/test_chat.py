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
        messages = chat_session._build_messages("user content here")
        assert messages[0].role == "system"
        assert messages[0].content == SYSTEM_PROMPT

    def test_includes_user_content(self, chat_session):
        user_content = "Context: X is Y\n\nQuestion: What is X?"
        messages = chat_session._build_messages(user_content)
        user_message = messages[-1]
        assert user_message.role == "user"
        assert user_message.content == user_content

    def test_includes_history(self, chat_session):
        chat_session.history = [
            Message(role="user", content="Previous Q"),
            Message(role="assistant", content="Previous A"),
        ]
        messages = chat_session._build_messages("New content")
        assert len(messages) == 4
        assert messages[1].content == "Previous Q"
        assert messages[2].content == "Previous A"

    def test_truncates_long_history(self, chat_session):
        chat_session.history = [
            Message(role="user", content=f"Q{i}")
            for i in range(MAX_HISTORY_MESSAGES + 10)
        ]
        messages = chat_session._build_messages("New content")
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
            # History now stores full context-augmented message for consistency
            assert "Question" in chat_session.history[0].content
            assert "Context from videos" in chat_session.history[0].content
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


class TestChatSessionIntegration:
    """Integration tests for multi-turn conversation flow."""

    def test_multi_turn_conversation_accumulates_history(self, llm_config):
        """Test that multiple ask() calls properly accumulate conversation history."""
        session = ChatSession(
            collection_id="integration_test",
            llm_config=llm_config,
        )
        with (
            patch("yt_agent_kit.chat.search") as mock_search,
            patch("yt_agent_kit.chat.call_llm") as mock_llm,
        ):
            mock_search.return_value = [
                Chunk(
                    content="Video content about topic A",
                    video_id="vid1",
                    video_title="Video One",
                    chunk_index=0,
                )
            ]
            mock_llm.side_effect = ["Answer to Q1", "Answer to Q2", "Answer to Q3"]

            # First question
            r1 = session.ask("First question?")
            assert r1 == "Answer to Q1"
            assert len(session.history) == 2  # user + assistant

            # Second question - should have history from first
            r2 = session.ask("Second question?")
            assert r2 == "Answer to Q2"
            assert len(session.history) == 4  # 2 + 2

            # Third question - history should continue growing
            r3 = session.ask("Third question?")
            assert r3 == "Answer to Q3"
            assert len(session.history) == 6  # 4 + 2

            # Verify search was called each time with the question
            assert mock_search.call_count == 3
            assert mock_llm.call_count == 3

    def test_context_included_in_llm_call(self, llm_config):
        """Test that video context is properly included when calling the LLM."""
        session = ChatSession(
            collection_id="context_test",
            llm_config=llm_config,
        )
        with (
            patch("yt_agent_kit.chat.search") as mock_search,
            patch("yt_agent_kit.chat.call_llm") as mock_llm,
        ):
            mock_search.return_value = [
                Chunk(
                    content="Important video content",
                    video_id="vid1",
                    video_title="Source Video",
                    chunk_index=0,
                )
            ]
            mock_llm.return_value = "Response based on context"

            session.ask("What does the video say?")

            # Verify the LLM received messages with context
            call_args = mock_llm.call_args
            messages = call_args[0][0]  # First positional arg

            # Should have system + user message
            assert len(messages) >= 2
            assert messages[0].role == "system"

            # User message should contain both context and question
            user_msg = messages[-1]
            assert "Important video content" in user_msg.content
            assert "Source Video" in user_msg.content
            assert "What does the video say?" in user_msg.content

    def test_history_truncation_preserves_recent(self, llm_config):
        """Test that old history is dropped but recent turns are preserved."""
        session = ChatSession(
            collection_id="truncation_test",
            llm_config=llm_config,
        )
        # Pre-populate with lots of history
        for i in range(MAX_HISTORY_MESSAGES + 10):
            session.history.append(Message(role="user", content=f"Old Q{i}"))
            session.history.append(Message(role="assistant", content=f"Old A{i}"))

        with (
            patch("yt_agent_kit.chat.search") as mock_search,
            patch("yt_agent_kit.chat.call_llm") as mock_llm,
        ):
            mock_search.return_value = []
            mock_llm.return_value = "New response"

            session.ask("New question?")

            # Verify LLM got truncated history
            call_args = mock_llm.call_args
            messages = call_args[0][0]
            # Should have: system + MAX_HISTORY_MESSAGES + new user message
            # But only MAX_HISTORY_MESSAGES from history
            history_msgs = [m for m in messages if m.role != "system"][:-1]
            assert len(history_msgs) == MAX_HISTORY_MESSAGES
