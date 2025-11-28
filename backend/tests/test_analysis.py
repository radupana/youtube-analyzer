"""Tests for video analysis service."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.services.analysis import (
    AnalysisOutput,
    build_analysis_context,
    generate_analysis,
)


class TestBuildAnalysisContext:
    def test_builds_context_with_transcript(self):
        video_info = {
            "video_id": "test123",
            "title": "Test Video",
            "channel_title": "Test Channel",
            "duration": "PT10M30S",
        }
        transcript = "This is the test transcript content."

        with patch("app.services.analysis.has_rag_data", return_value=False):
            context = build_analysis_context(video_info, transcript)

        assert "Test Video" in context
        assert "Test Channel" in context
        assert "PT10M30S" in context
        assert "This is the test transcript content." in context

    def test_truncates_long_transcript(self):
        video_info = {
            "video_id": "test",
            "title": "T",
            "channel_title": "C",
            "duration": "PT1M",
        }
        long_transcript = "x" * 20000

        with patch("app.services.analysis.has_rag_data", return_value=False):
            context = build_analysis_context(video_info, long_transcript)

        assert "[Transcript truncated...]" in context
        assert len(context) < 20000

    def test_uses_rag_when_available(self):
        video_info = {
            "video_id": "test123",
            "title": "T",
            "channel_title": "C",
            "duration": "PT1M",
        }
        transcript = "Full transcript here"

        with patch("app.services.analysis.has_rag_data", return_value=True):
            with patch(
                "app.services.analysis.retrieve_context_for_query",
                return_value="RAG excerpts",
            ):
                context = build_analysis_context(video_info, transcript)

        assert "RAG excerpts" in context
        assert "Full transcript here" not in context

    def test_handles_missing_transcript(self):
        video_info = {
            "video_id": "test",
            "title": "T",
            "channel_title": "C",
            "duration": "PT1M",
        }

        with patch("app.services.analysis.has_rag_data", return_value=False):
            context = build_analysis_context(video_info, None)

        assert "(No transcript available)" in context


class TestGenerateAnalysis:
    @pytest.mark.asyncio
    async def test_generate_analysis_success(self):
        video_info = {
            "video_id": "test123",
            "title": "Test Video",
            "channel_title": "Test Channel",
            "duration": "PT10M",
        }
        transcript = "This is a test transcript about machine learning."

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(
            {
                "summary": "This video covers machine learning basics.",
                "key_takeaways": ["ML is powerful", "Start with basics"],
                "main_topics": ["Machine Learning", "AI"],
                "notable_quotes": ["AI will change everything"],
            }
        )

        with patch("app.services.analysis.get_current_provider") as mock_provider:
            mock_provider.return_value = MagicMock(
                model="gemini/gemini-2.5-flash",
                api_key="test-key",
                name="Gemini",
            )
            with patch("app.services.analysis.has_rag_data", return_value=False):
                with patch(
                    "litellm.acompletion",
                    new_callable=AsyncMock,
                    return_value=mock_response,
                ):
                    result = await generate_analysis(video_info, transcript)

        assert isinstance(result, AnalysisOutput)
        assert "machine learning" in result.summary.lower()
        assert len(result.key_takeaways) == 2
        assert len(result.main_topics) == 2

    @pytest.mark.asyncio
    async def test_generate_analysis_no_provider(self):
        with patch("app.services.analysis.get_current_provider", return_value=None):
            with pytest.raises(HTTPException) as exc:
                await generate_analysis({"video_id": "test"}, "transcript")

        assert exc.value.status_code == 503
        assert "No LLM provider" in exc.value.detail

    @pytest.mark.asyncio
    async def test_generate_analysis_no_transcript(self):
        with patch("app.services.analysis.get_current_provider") as mock_provider:
            mock_provider.return_value = MagicMock()
            with pytest.raises(HTTPException) as exc:
                await generate_analysis({"video_id": "test"}, None)

        assert exc.value.status_code == 400
        assert "without transcript" in exc.value.detail

    @pytest.mark.asyncio
    async def test_generate_analysis_invalid_json(self):
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "not valid json"

        with patch("app.services.analysis.get_current_provider") as mock_provider:
            mock_provider.return_value = MagicMock(
                model="test", api_key="key", name="Test"
            )
            with patch("app.services.analysis.has_rag_data", return_value=False):
                with patch(
                    "litellm.acompletion",
                    new_callable=AsyncMock,
                    return_value=mock_response,
                ):
                    with pytest.raises(HTTPException) as exc:
                        await generate_analysis({"video_id": "t"}, "transcript")

        assert exc.value.status_code == 502
        assert "invalid JSON" in exc.value.detail


class TestAnalysisOutput:
    def test_valid_analysis_output(self):
        output = AnalysisOutput(
            summary="Test summary",
            key_takeaways=["Point 1", "Point 2"],
            main_topics=["Topic A"],
            notable_quotes=[],
        )
        assert output.summary == "Test summary"
        assert len(output.key_takeaways) == 2

    def test_analysis_output_from_json(self):
        data = {
            "summary": "Summary text",
            "key_takeaways": ["A", "B", "C"],
            "main_topics": ["X", "Y"],
            "notable_quotes": ["Quote 1"],
        }
        output = AnalysisOutput(**data)
        assert output.summary == "Summary text"
        assert output.key_takeaways == ["A", "B", "C"]
