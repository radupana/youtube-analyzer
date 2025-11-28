"""Video analysis service using LLM structured output."""

import json
import logging
from typing import Any

import litellm
from fastapi import HTTPException
from litellm.exceptions import APIError, AuthenticationError, NotFoundError
from pydantic import BaseModel, Field

from app.core.llm_config import get_current_provider
from app.services.rag import has_rag_data, retrieve_context_for_query

logger = logging.getLogger(__name__)


class AnalysisOutput(BaseModel):
    summary: str = Field(
        description="2-3 paragraph executive summary of the video content"
    )
    key_takeaways: list[str] = Field(
        description="5-7 bullet points with the most important insights"
    )
    main_topics: list[str] = Field(description="3-5 main topics or themes discussed")
    notable_quotes: list[str] = Field(
        description="2-3 interesting or impactful quotes from the video"
    )


ANALYSIS_SYSTEM_PROMPT = """\
You are an expert content analyst. Analyze YouTube video transcripts.

Focus on:
1. SUMMARY: 2-3 paragraph overview of content, arguments, and conclusions.
2. KEY TAKEAWAYS: 5-7 actionable insights. Start each with an action verb.
3. MAIN TOPICS: 3-5 central themes discussed.
4. NOTABLE QUOTES: 2-3 impactful quotes representing key ideas.

Be concise. If transcript is partial, acknowledge limitations.
Do NOT include timestamps in quotes. If no notable quotes, return empty list."""


def build_analysis_context(
    video_info: dict[str, Any],
    transcript: str | None,
) -> str:
    parts = [
        f"Video Title: {video_info.get('title', 'Unknown')}",
        f"Channel: {video_info.get('channel_title', 'Unknown')}",
        f"Duration: {video_info.get('duration', 'Unknown')}",
        "",
    ]

    video_id = video_info.get("video_id", "")
    if video_id and has_rag_data(video_id):
        rag_context = retrieve_context_for_query(
            query="main topics key points summary important ideas",
            video_ids=[video_id],
            top_k=20,
            max_tokens=8000,
        )
        if rag_context:
            parts.append("Relevant excerpts from transcript:")
            parts.append(rag_context)
            return "\n".join(parts)

    parts.append("Full transcript:")
    if transcript:
        if len(transcript) > 15000:
            parts.append(transcript[:15000] + "\n\n[Transcript truncated...]")
        else:
            parts.append(transcript)
    else:
        parts.append("(No transcript available)")

    return "\n".join(parts)


async def generate_analysis(
    video_info: dict[str, Any],
    transcript: str | None,
) -> AnalysisOutput:
    provider = get_current_provider()
    if not provider:
        raise HTTPException(
            status_code=503,
            detail="No LLM provider configured. Check config.yaml and API keys.",
        )

    if not transcript:
        raise HTTPException(
            status_code=400,
            detail="Cannot analyze video without transcript.",
        )

    context = build_analysis_context(video_info, transcript)

    user_content = f"{context}\n\nAnalyze this video and provide structured insights."
    messages = [
        {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]

    try:
        response = await litellm.acompletion(
            model=provider.model,
            messages=messages,
            api_key=provider.api_key,
            response_format=AnalysisOutput,
        )

        content = response.choices[0].message.content
        if not content:
            raise HTTPException(status_code=502, detail="Empty response from LLM")

        try:
            data = json.loads(content)
            return AnalysisOutput(**data)
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"Failed to parse LLM response: {e}\nContent: {content[:500]}")
            raise HTTPException(
                status_code=502,
                detail="LLM returned invalid JSON response",
            ) from e

    except AuthenticationError as e:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid API key for {provider.name}",
        ) from e
    except NotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Model '{provider.model}' not found. {e.message}",
        ) from e
    except APIError as e:
        raise HTTPException(
            status_code=502,
            detail=f"{provider.name} error: {e.message}",
        ) from e
