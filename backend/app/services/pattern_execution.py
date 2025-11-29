"""Execute patterns against video transcripts using LLM."""

import logging
from dataclasses import dataclass
from datetime import datetime

import litellm
from fastapi import HTTPException
from litellm.exceptions import APIError, AuthenticationError, RateLimitError

from app.core.llm_config import get_current_provider
from app.db.models import utc_now
from app.services.patterns import Pattern, format_pattern_prompt
from app.services.rag import has_rag_data, retrieve_context_for_query

logger = logging.getLogger(__name__)

MAX_TRANSCRIPT_LENGTH = 15000


@dataclass
class PatternResult:
    content: str
    model_used: str
    created_at: datetime


def _prepare_context(
    transcript: str,
    pattern: Pattern,
    video_id: str | None,
) -> str:
    """Prepare transcript context, using RAG if available."""
    if video_id and has_rag_data(video_id):
        rag_context = retrieve_context_for_query(
            query=pattern.description,
            video_ids=[video_id],
            top_k=20,
            max_tokens=8000,
        )
        if rag_context:
            logger.info(f"Using RAG context for pattern {pattern.id}")
            return rag_context

    if len(transcript) > MAX_TRANSCRIPT_LENGTH:
        logger.warning(f"Transcript truncated for video {video_id}")
        return transcript[:MAX_TRANSCRIPT_LENGTH] + "\n\n[Transcript truncated...]"

    return transcript


async def execute_pattern(
    pattern: Pattern,
    video_title: str,
    channel: str,
    transcript: str,
    video_id: str | None = None,
) -> PatternResult:
    """Execute a pattern against video content."""
    provider = get_current_provider()
    if not provider:
        raise HTTPException(status_code=503, detail="No LLM provider configured")

    context = _prepare_context(transcript, pattern, video_id)

    user_prompt = format_pattern_prompt(
        pattern=pattern,
        video_title=video_title,
        channel=channel,
        transcript=context,
    )

    messages = [
        {"role": "system", "content": pattern.system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    try:
        response = await litellm.acompletion(
            model=provider.model,
            messages=messages,
            api_key=provider.api_key,
        )
    except RateLimitError as e:
        logger.error(f"Rate limit hit: {e}")
        raise HTTPException(
            status_code=429,
            detail="LLM rate limit exceeded. Please try again later.",
        ) from e
    except AuthenticationError as e:
        logger.error(f"Auth error: {e}")
        raise HTTPException(
            status_code=401,
            detail=f"Invalid API key for {provider.name}",
        ) from e
    except APIError as e:
        logger.error(f"API error: {e}")
        raise HTTPException(
            status_code=502,
            detail=f"LLM provider error: {e.message}",
        ) from e

    content = response.choices[0].message.content
    if not content:
        raise HTTPException(status_code=502, detail="Empty response from LLM")

    return PatternResult(
        content=content,
        model_used=provider.model,
        created_at=utc_now(),
    )
