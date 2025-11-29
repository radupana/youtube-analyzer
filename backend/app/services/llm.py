import logging
from collections.abc import AsyncIterator
from typing import Any

import litellm
from fastapi import HTTPException
from litellm.exceptions import APIError, AuthenticationError, NotFoundError

from app.core.llm_config import get_current_provider
from app.services.rag import has_rag_data, retrieve_context_for_query

logger = logging.getLogger(__name__)

# Context window threshold (70% of model capacity)
CONTEXT_THRESHOLD_RATIO = 0.70

# Conservative fallback for unknown models (128K tokens like GPT-4o)
DEFAULT_CONTEXT_WINDOW = 128000

SYSTEM_PROMPT_FULL = """You are an AI assistant analyzing YouTube video content.
You have access to the COMPLETE transcripts of all videos the user has loaded.
Timestamps in [MM:SS] format indicate when content appears in the video.
Please provide helpful responses based on the full video content available."""

SYSTEM_PROMPT_RAG = """You are an AI assistant analyzing YouTube video content.
You have been given RELEVANT EXCERPTS (not full transcripts) from video transcripts.
Timestamps in [MM:SS] format indicate when content appears in the video.
Please provide helpful responses based on the excerpts available.
If the question cannot be answered from the available excerpts, say so clearly."""


def get_model_context_window(model: str) -> int:
    """Get context window size for a model using LiteLLM's model info."""
    try:
        max_tokens = litellm.get_max_tokens(model)
        if max_tokens and max_tokens > 0:
            return max_tokens
    except Exception as e:
        logger.warning(f"Could not get context window for {model}: {e}")
    return DEFAULT_CONTEXT_WINDOW


def estimate_tokens(text: str) -> int:
    """Estimate token count. ~4 chars per token is a reasonable approximation."""
    return len(text) // 4


def _build_full_transcript_context(video_transcripts: list[dict[str, Any]]) -> str:
    """Build context with complete transcripts for all videos."""
    parts = ["Complete transcripts from loaded videos:\n"]
    for video in video_transcripts:
        title = video.get("title", "Unknown")
        channel = video.get("channel_title", "Unknown")
        parts.append(f"\n## {title} by {channel}\n")
        transcript = video.get("transcript")
        if transcript:
            parts.append(transcript)
        else:
            parts.append("(Transcript not available)")
    return "\n".join(parts)


def build_context_with_rag(
    query: str,
    video_transcripts: list[dict[str, Any]],
    top_k: int = 10,
    max_tokens: int = 4000,
) -> str:
    """Build context using RAG retrieval for relevant chunks."""
    if not video_transcripts:
        return "No videos have been loaded yet."

    video_ids = []
    video_info = {}
    for video in video_transcripts:
        vid = video.get("video_id")
        if vid:
            video_ids.append(vid)
            video_info[vid] = {
                "title": video.get("title", "Unknown"),
                "channel_title": video.get("channel_title", "Unknown"),
            }

    videos_with_rag = [vid for vid in video_ids if has_rag_data(vid)]

    if not videos_with_rag:
        return _build_context_fallback(video_transcripts)

    retrieved_context = retrieve_context_for_query(
        query, videos_with_rag, top_k=top_k, max_tokens=max_tokens
    )

    if not retrieved_context:
        return _build_context_fallback(video_transcripts)

    parts = ["Relevant excerpts from loaded videos:\n"]
    for vid in videos_with_rag:
        info = video_info.get(vid, {})
        title = info.get("title", "Unknown")
        channel = info.get("channel_title", "Unknown")
        parts.append(f"**{title}** by {channel}")
    parts.append("\n" + retrieved_context)

    return "\n".join(parts)


def _build_context_fallback(video_transcripts: list[dict[str, Any]]) -> str:
    """Fallback to truncated transcripts when RAG data unavailable."""
    parts = ["You have access to the following video transcripts:\n"]
    for video in video_transcripts:
        title = video.get("title", "Unknown")
        channel = video.get("channel_title", "Unknown")
        parts.append(f"**{title}** by {channel}")
        transcript = video.get("transcript")
        if transcript:
            if len(transcript) > 5000:
                transcript = transcript[:5000] + "... (truncated)"
            parts.append(f"Transcript: {transcript}\n")
        else:
            parts.append("Transcript: Not available\n")
    return "\n".join(parts)


def build_context(
    query: str,
    video_transcripts: list[dict[str, Any]],
    model: str,
) -> tuple[str, str]:
    """
    Build context for LLM, preferring full transcripts when they fit.

    Returns:
        tuple of (context_string, system_prompt_to_use)
    """
    if not video_transcripts:
        return "No videos have been loaded yet.", SYSTEM_PROMPT_FULL

    # Calculate total transcript size and estimate tokens
    total_chars = sum(len(v.get("transcript") or "") for v in video_transcripts)
    estimated_tokens = total_chars // 4  # ~4 chars per token

    # Get model context window
    context_window = get_model_context_window(model)
    token_threshold = int(context_window * CONTEXT_THRESHOLD_RATIO)

    logger.info(
        f"Context decision: {estimated_tokens} estimated tokens, "
        f"threshold {token_threshold} (70% of {context_window})"
    )

    # If transcripts fit within 70% of context, use full transcripts
    if estimated_tokens < token_threshold:
        logger.info("Using full transcripts (under 70% capacity)")
        return _build_full_transcript_context(video_transcripts), SYSTEM_PROMPT_FULL

    # Otherwise, use RAG for relevant excerpts
    logger.info("Using RAG excerpts (over 70% capacity)")
    context = build_context_with_rag(query, video_transcripts)
    return context, SYSTEM_PROMPT_RAG


def _prepare_chat_messages(
    message: str, video_transcripts: list[dict[str, Any]], model: str
) -> tuple[list[dict[str, str]], str]:
    """Prepare messages for LLM chat. Returns (messages, system_prompt)."""
    context, system_prompt = build_context(message, video_transcripts, model)
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"{context}\n\nUser question: {message}"},
    ]
    return messages, system_prompt


async def chat_with_context_stream(
    message: str, video_transcripts: list[dict[str, Any]]
) -> AsyncIterator[str]:
    """Stream chat response token by token."""
    provider = get_current_provider()
    if not provider:
        raise HTTPException(
            status_code=503,
            detail="No LLM provider configured. Check config.yaml and API keys.",
        )

    messages, _ = _prepare_chat_messages(message, video_transcripts, provider.model)

    try:
        response = await litellm.acompletion(
            model=provider.model,
            messages=messages,
            api_key=provider.api_key,
            stream=True,
        )
        async for chunk in response:
            content = chunk.choices[0].delta.content
            if content:
                yield content
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
