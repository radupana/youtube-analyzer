from typing import Any

import litellm
from fastapi import HTTPException
from litellm.exceptions import APIError, AuthenticationError, NotFoundError

from app.core.llm_config import get_current_provider

SYSTEM_PROMPT = """You are an AI assistant analyzing YouTube video content.
You have been given transcripts of videos that the user has loaded.
Please provide helpful responses based on the video content available.
If the question cannot be answered from the available videos, say so clearly."""


def build_context(video_transcripts: list[dict[str, Any]]) -> str:
    if not video_transcripts:
        return "No videos have been loaded yet."

    parts = ["You have access to the following video transcripts:\n"]
    for video in video_transcripts:
        parts.append(f"**{video['title']}** by {video['channel_title']}")
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

    context = build_context(video_transcripts)
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
