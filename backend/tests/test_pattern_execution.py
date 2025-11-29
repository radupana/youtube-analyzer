"""Tests for pattern execution service."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from litellm.exceptions import APIError, AuthenticationError, RateLimitError

from app.services.pattern_execution import (
    PatternResult,
    _prepare_context,
    execute_pattern,
)
from app.services.patterns import Pattern


def make_pattern(**kwargs) -> Pattern:
    defaults = {
        "id": "test",
        "name": "Test Pattern",
        "description": "Test description",
        "icon": "🧪",
        "category": "test",
        "system_prompt": "You are helpful.",
        "user_prompt": "Analyze: {video_title} - {channel}\n{transcript}",
    }
    defaults.update(kwargs)
    return Pattern(**defaults)


class TestPrepareContext:
    def test_returns_transcript_when_short(self):
        pattern = make_pattern()
        transcript = "Short transcript"

        with patch("app.services.pattern_execution.has_rag_data", return_value=False):
            result = _prepare_context(transcript, pattern, "video123")

        assert result == "Short transcript"

    def test_truncates_long_transcript(self):
        pattern = make_pattern()
        long_transcript = "x" * 20000

        with patch("app.services.pattern_execution.has_rag_data", return_value=False):
            result = _prepare_context(long_transcript, pattern, "video123")

        assert len(result) < 20000
        assert "[Transcript truncated...]" in result

    def test_uses_rag_when_available(self):
        pattern = make_pattern()
        transcript = "Original transcript"

        with patch("app.services.pattern_execution.has_rag_data", return_value=True):
            with patch(
                "app.services.pattern_execution.retrieve_context_for_query",
                return_value="RAG context",
            ):
                result = _prepare_context(transcript, pattern, "video123")

        assert result == "RAG context"

    def test_falls_back_to_transcript_when_rag_returns_empty(self):
        pattern = make_pattern()
        transcript = "Original transcript"

        with patch("app.services.pattern_execution.has_rag_data", return_value=True):
            with patch(
                "app.services.pattern_execution.retrieve_context_for_query",
                return_value="",
            ):
                result = _prepare_context(transcript, pattern, "video123")

        assert result == "Original transcript"


class TestExecutePattern:
    @pytest.mark.asyncio
    async def test_success(self):
        pattern = make_pattern()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "# Analysis\nThis is the result."

        with patch(
            "app.services.pattern_execution.get_current_provider"
        ) as mock_provider:
            mock_provider.return_value = MagicMock(
                model="test-model",
                api_key="test-key",
                name="Test",
            )
            with patch(
                "app.services.pattern_execution.has_rag_data", return_value=False
            ):
                with patch(
                    "litellm.acompletion",
                    new_callable=AsyncMock,
                    return_value=mock_response,
                ):
                    result = await execute_pattern(
                        pattern=pattern,
                        video_title="Test Video",
                        channel="Test Channel",
                        transcript="This is the transcript.",
                    )

        assert isinstance(result, PatternResult)
        assert "Analysis" in result.content
        assert result.model_used == "test-model"
        assert isinstance(result.created_at, datetime)

    @pytest.mark.asyncio
    async def test_no_provider_raises_503(self):
        pattern = make_pattern()

        with patch(
            "app.services.pattern_execution.get_current_provider", return_value=None
        ):
            with pytest.raises(HTTPException) as exc:
                await execute_pattern(pattern, "title", "channel", "transcript")

        assert exc.value.status_code == 503
        assert "No LLM provider" in exc.value.detail

    @pytest.mark.asyncio
    async def test_rate_limit_raises_429(self):
        pattern = make_pattern()

        with patch(
            "app.services.pattern_execution.get_current_provider"
        ) as mock_provider:
            mock_provider.return_value = MagicMock(model="m", api_key="k", name="N")
            with patch(
                "app.services.pattern_execution.has_rag_data", return_value=False
            ):
                with patch(
                    "litellm.acompletion",
                    new_callable=AsyncMock,
                    side_effect=RateLimitError(
                        message="Rate limited",
                        model="test",
                        llm_provider="test",
                    ),
                ):
                    with pytest.raises(HTTPException) as exc:
                        await execute_pattern(pattern, "T", "C", "transcript")

        assert exc.value.status_code == 429
        assert "rate limit" in exc.value.detail.lower()

    @pytest.mark.asyncio
    async def test_auth_error_raises_401(self):
        pattern = make_pattern()

        with patch(
            "app.services.pattern_execution.get_current_provider"
        ) as mock_provider:
            mock_provider.return_value = MagicMock(
                model="m", api_key="k", name="TestProvider"
            )
            with patch(
                "app.services.pattern_execution.has_rag_data", return_value=False
            ):
                with patch(
                    "litellm.acompletion",
                    new_callable=AsyncMock,
                    side_effect=AuthenticationError(
                        message="Invalid key",
                        model="test",
                        llm_provider="test",
                    ),
                ):
                    with pytest.raises(HTTPException) as exc:
                        await execute_pattern(pattern, "T", "C", "transcript")

        assert exc.value.status_code == 401
        assert "Invalid API key" in exc.value.detail

    @pytest.mark.asyncio
    async def test_api_error_raises_502(self):
        pattern = make_pattern()

        with patch(
            "app.services.pattern_execution.get_current_provider"
        ) as mock_provider:
            mock_provider.return_value = MagicMock(model="m", api_key="k", name="N")
            with patch(
                "app.services.pattern_execution.has_rag_data", return_value=False
            ):
                with patch(
                    "litellm.acompletion",
                    new_callable=AsyncMock,
                    side_effect=APIError(
                        message="Server error",
                        model="test",
                        llm_provider="test",
                        status_code=500,
                    ),
                ):
                    with pytest.raises(HTTPException) as exc:
                        await execute_pattern(pattern, "T", "C", "transcript")

        assert exc.value.status_code == 502
        assert "LLM provider error" in exc.value.detail

    @pytest.mark.asyncio
    async def test_empty_response_raises_502(self):
        pattern = make_pattern()

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None

        with patch(
            "app.services.pattern_execution.get_current_provider"
        ) as mock_provider:
            mock_provider.return_value = MagicMock(model="m", api_key="k", name="N")
            with patch(
                "app.services.pattern_execution.has_rag_data", return_value=False
            ):
                with patch(
                    "litellm.acompletion",
                    new_callable=AsyncMock,
                    return_value=mock_response,
                ):
                    with pytest.raises(HTTPException) as exc:
                        await execute_pattern(pattern, "T", "C", "transcript")

        assert exc.value.status_code == 502
        assert "Empty response" in exc.value.detail

    @pytest.mark.asyncio
    async def test_prompt_contains_video_info(self):
        pattern = make_pattern(
            user_prompt="Title: {video_title}, Channel: {channel}, Text: {transcript}"
        )

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Result"

        with patch(
            "app.services.pattern_execution.get_current_provider"
        ) as mock_provider:
            mock_provider.return_value = MagicMock(model="m", api_key="k", name="N")
            with patch(
                "app.services.pattern_execution.has_rag_data", return_value=False
            ):
                with patch(
                    "litellm.acompletion",
                    new_callable=AsyncMock,
                    return_value=mock_response,
                ) as mock_llm:
                    await execute_pattern(
                        pattern,
                        video_title="My Video Title",
                        channel="My Channel",
                        transcript="Content here",
                    )

                    call_kwargs = mock_llm.call_args.kwargs
                    user_message = call_kwargs["messages"][1]["content"]
                    assert "My Video Title" in user_message
                    assert "My Channel" in user_message
                    assert "Content here" in user_message
