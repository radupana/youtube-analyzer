from typing import Any

import litellm
from fastapi import HTTPException
from litellm.exceptions import APIError, AuthenticationError, NotFoundError

from app.core.llm_config import get_current_provider
from app.services.rag import has_rag_data, retrieve_context_for_query

SYSTEM_PROMPT = """You are an AI assistant analyzing YouTube video content.
You have been given relevant excerpts from video transcripts that the user has loaded.
Timestamps in [MM:SS] format indicate when content appears in the video.
Please provide helpful responses based on the video content available.
If the question cannot be answered from the available excerpts, say so clearly."""


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


async def chat_with_context(
    message: str, video_transcripts: list[dict[str, Any]]
) -> str:
    provider = get_current_provider()
    if not provider:
        raise HTTPException(
            status_code=503,
            detail="No LLM provider configured. Check config.yaml and API keys.",
        )

    context = build_context_with_rag(message, video_transcripts)
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"{context}\n\nUser question: {message}"},
    ]

    try:
        response = await litellm.acompletion(
            model=provider.model,
            messages=messages,
            api_key=provider.api_key,
        )
        content = response.choices[0].message.content
        return content if content else ""
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
