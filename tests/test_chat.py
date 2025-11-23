from unittest.mock import patch

import pytest

from yt_agent_kit.chat import (
    MAX_HISTORY_MESSAGES,
    SYSTEM_PROMPT,
    ChatSession,
    estimate_tokens,
)
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
def small_transcripts():
    return {"vid1": "Short transcript content"}


@pytest.fixture
def video_titles():
    return {"vid1": "Test Video One", "vid2": "Test Video Two"}


@pytest.fixture
def chat_session(llm_config, search_config, small_transcripts, video_titles):
    return ChatSession(
        collection_id="test_collection",
        llm_config=llm_config,
        transcripts=small_transcripts,
        video_titles=video_titles,
        context_limit=100_000,
        search_config=search_config,
    )


class TestEstimateTokens:
    def test_empty_string(self):
        assert estimate_tokens("") == 0

    def test_short_string(self):
        assert estimate_tokens("abcd") == 1

    def test_longer_string(self):
        assert estimate_tokens("a" * 400) == 100


class TestChatSessionInit:
    def test_creates_with_required_params(
        self, llm_config, small_transcripts, video_titles
    ):
        session = ChatSession(
            collection_id="test",
            llm_config=llm_config,
            transcripts=small_transcripts,
            video_titles=video_titles,
            context_limit=100_000,
        )
        assert session.collection_id == "test"
        assert session.llm_config == llm_config
        assert session.history == []

    def test_creates_with_custom_search_config(
        self, llm_config, search_config, small_transcripts, video_titles
    ):
        session = ChatSession(
            collection_id="test",
            llm_config=llm_config,
            transcripts=small_transcripts,
            video_titles=video_titles,
            context_limit=100_000,
            search_config=search_config,
        )
        assert session.search_config.top_k == 5

    def test_full_context_mode_enabled_for_small_transcripts(
        self, llm_config, small_transcripts, video_titles
    ):
        session = ChatSession(
            collection_id="test",
            llm_config=llm_config,
            transcripts=small_transcripts,
            video_titles=video_titles,
            context_limit=100_000,
        )
        assert session._full_context_mode is True

    def test_rag_mode_enabled_for_large_transcripts(self, llm_config, video_titles):
        large_transcripts = {"vid1": "x" * 1_000_000}
        session = ChatSession(
            collection_id="test",
            llm_config=llm_config,
            transcripts=large_transcripts,
            video_titles=video_titles,
            context_limit=100_000,
        )
        assert session._full_context_mode is False


class TestFormatChunks:
    def test_empty_chunks_returns_no_context(self, chat_session):
        result = chat_session._format_chunks([])
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
        result = chat_session._format_chunks(chunks)
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
        result = chat_session._format_chunks(chunks)
        assert '[Video: "Video One"]' in result
        assert '[Video: "Video Two"]' in result
        assert "---" in result


class TestFormatAllTranscripts:
    def test_formats_all_transcripts(self, llm_config):
        transcripts = {"vid1": "Content one", "vid2": "Content two"}
        titles = {"vid1": "Video One", "vid2": "Video Two"}
        session = ChatSession(
            collection_id="test",
            llm_config=llm_config,
            transcripts=transcripts,
            video_titles=titles,
            context_limit=100_000,
        )
        result = session._format_all_transcripts()
        assert '=== Video: "Video One" ===' in result
        assert "Content one" in result
        assert '=== Video: "Video Two" ===' in result
        assert "Content two" in result

    def test_uses_video_id_as_fallback_title(self, llm_config):
        transcripts = {"vid1": "Content one"}
        titles = {}
        session = ChatSession(
            collection_id="test",
            llm_config=llm_config,
            transcripts=transcripts,
            video_titles=titles,
            context_limit=100_000,
        )
        result = session._format_all_transcripts()
        assert '=== Video: "vid1" ===' in result


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


class TestGetContext:
    def test_uses_full_context_mode_for_small_transcripts(self, llm_config):
        transcripts = {"vid1": "Small content"}
        titles = {"vid1": "Video One"}
        session = ChatSession(
            collection_id="test",
            llm_config=llm_config,
            transcripts=transcripts,
            video_titles=titles,
            context_limit=100_000,
        )
        context = session._get_context("What is this about?")
        assert '=== Video: "Video One" ===' in context
        assert "Small content" in context

    def test_falls_back_to_rag_when_context_grows(self, llm_config):
        transcripts = {"vid1": "x" * 10000}
        titles = {"vid1": "Video One"}
        session = ChatSession(
            collection_id="test",
            llm_config=llm_config,
            transcripts=transcripts,
            video_titles=titles,
            context_limit=5000,
        )
        session._full_context_mode = True
        session.history = [Message(role="user", content="x" * 10000)]

        with (
            patch("yt_agent_kit.chat.build_index"),
            patch("yt_agent_kit.chat.search") as mock_search,
        ):
            mock_search.return_value = []
            session._get_context("question")

        assert session._full_context_mode is False
        mock_search.assert_called_once()


class TestAsk:
    def test_full_context_mode_does_not_call_search(self, llm_config):
        transcripts = {"vid1": "Video content"}
        titles = {"vid1": "Video One"}
        session = ChatSession(
            collection_id="test",
            llm_config=llm_config,
            transcripts=transcripts,
            video_titles=titles,
            context_limit=100_000,
        )
        with (
            patch("yt_agent_kit.chat.search") as mock_search,
            patch("yt_agent_kit.chat.call_llm") as mock_llm,
        ):
            mock_llm.return_value = "The answer"
            result = session.ask("What is X?")

            assert result == "The answer"
            mock_search.assert_not_called()

    def test_rag_mode_calls_search(self, llm_config):
        large_transcripts = {"vid1": "x" * 1_000_000}
        titles = {"vid1": "Video One"}
        session = ChatSession(
            collection_id="test",
            llm_config=llm_config,
            transcripts=large_transcripts,
            video_titles=titles,
            context_limit=100_000,
        )
        with (
            patch("yt_agent_kit.chat.build_index"),
            patch("yt_agent_kit.chat.search") as mock_search,
            patch("yt_agent_kit.chat.call_llm") as mock_llm,
        ):
            mock_search.return_value = [
                Chunk(
                    content="Relevant info",
                    video_id="vid1",
                    video_title="Video One",
                    chunk_index=0,
                )
            ]
            mock_llm.return_value = "The answer"

            result = session.ask("What is X?")

            assert result == "The answer"
            mock_search.assert_called_once()

    def test_updates_history(self, chat_session):
        with patch("yt_agent_kit.chat.call_llm") as mock_llm:
            mock_llm.return_value = "Response"

            chat_session.ask("Question")

            assert len(chat_session.history) == 2
            assert chat_session.history[0].role == "user"
            assert "Question" in chat_session.history[0].content
            assert "Context from videos" in chat_session.history[0].content
            assert chat_session.history[1].role == "assistant"
            assert chat_session.history[1].content == "Response"


class TestLazyEmbeddings:
    def test_embeddings_not_built_in_full_context_mode(self, llm_config):
        transcripts = {"vid1": "Small content"}
        titles = {"vid1": "Video One"}
        session = ChatSession(
            collection_id="test",
            llm_config=llm_config,
            transcripts=transcripts,
            video_titles=titles,
            context_limit=100_000,
        )
        with (
            patch("yt_agent_kit.chat.build_index") as mock_build,
            patch("yt_agent_kit.chat.call_llm") as mock_llm,
        ):
            mock_llm.return_value = "Response"
            session.ask("Question")

            mock_build.assert_not_called()

    def test_embeddings_built_lazily_in_rag_mode(self, llm_config):
        large_transcripts = {"vid1": "x" * 1_000_000}
        titles = {"vid1": "Video One"}
        session = ChatSession(
            collection_id="test",
            llm_config=llm_config,
            transcripts=large_transcripts,
            video_titles=titles,
            context_limit=100_000,
        )
        with (
            patch("yt_agent_kit.chat.build_index") as mock_build,
            patch("yt_agent_kit.chat.search") as mock_search,
            patch("yt_agent_kit.chat.call_llm") as mock_llm,
        ):
            mock_search.return_value = []
            mock_llm.return_value = "Response"

            session.ask("Question 1")
            session.ask("Question 2")

            assert mock_build.call_count == 1


class TestClearHistory:
    def test_clears_all_history(self, chat_session):
        chat_session.history = [
            Message(role="user", content="Q1"),
            Message(role="assistant", content="A1"),
        ]

        chat_session.clear_history()

        assert chat_session.history == []


class TestChatSessionIntegration:
    def test_multi_turn_conversation_accumulates_history(
        self, llm_config, small_transcripts, video_titles
    ):
        session = ChatSession(
            collection_id="integration_test",
            llm_config=llm_config,
            transcripts=small_transcripts,
            video_titles=video_titles,
            context_limit=100_000,
        )
        with patch("yt_agent_kit.chat.call_llm") as mock_llm:
            mock_llm.side_effect = ["Answer to Q1", "Answer to Q2", "Answer to Q3"]

            r1 = session.ask("First question?")
            assert r1 == "Answer to Q1"
            assert len(session.history) == 2

            r2 = session.ask("Second question?")
            assert r2 == "Answer to Q2"
            assert len(session.history) == 4

            r3 = session.ask("Third question?")
            assert r3 == "Answer to Q3"
            assert len(session.history) == 6

            assert mock_llm.call_count == 3

    def test_context_included_in_llm_call(self, llm_config):
        transcripts = {"vid1": "Important video content"}
        titles = {"vid1": "Source Video"}
        session = ChatSession(
            collection_id="context_test",
            llm_config=llm_config,
            transcripts=transcripts,
            video_titles=titles,
            context_limit=100_000,
        )
        with patch("yt_agent_kit.chat.call_llm") as mock_llm:
            mock_llm.return_value = "Response based on context"

            session.ask("What does the video say?")

            call_args = mock_llm.call_args
            messages = call_args[0][0]

            assert len(messages) >= 2
            assert messages[0].role == "system"

            user_msg = messages[-1]
            assert "Important video content" in user_msg.content
            assert "Source Video" in user_msg.content
            assert "What does the video say?" in user_msg.content
