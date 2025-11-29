"""Language-related endpoints."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.api_v1.schemas import (
    AvailableTranscriptsResponse,
    LanguageInfo,
    TranscriptDefaultsResponse,
)
from app.core.llm_config import get_transcript_config
from app.db.database import get_session
from app.db.models import Video
from app.services.youtube import YouTubeService

router = APIRouter()
youtube_service = YouTubeService()


@router.get(
    "/videos/{video_id}/available-transcripts",
    response_model=AvailableTranscriptsResponse,
)
async def get_available_transcripts(
    video_id: str,
    db: Session = Depends(get_session),
):
    """Get available transcript languages for a video."""
    video = db.get(Video, video_id)
    if video and video.available_languages_json:
        try:
            cached_languages = json.loads(video.available_languages_json)
            return AvailableTranscriptsResponse(
                video_id=video_id,
                languages=[LanguageInfo(**lang) for lang in cached_languages],
                cached=True,
            )
        except json.JSONDecodeError:
            pass

    languages = youtube_service.get_available_languages(video_id)
    if not languages:
        raise HTTPException(
            status_code=404, detail="No transcripts available for this video"
        )

    return AvailableTranscriptsResponse(
        video_id=video_id,
        languages=[
            LanguageInfo(
                code=lang.code,
                name=lang.name,
                is_generated=lang.is_generated,
                is_translatable=lang.is_translatable,
            )
            for lang in languages
        ],
        cached=False,
    )


@router.get("/defaults", response_model=TranscriptDefaultsResponse)
async def get_transcript_defaults():
    """Get default transcript language preferences from server config."""
    config = get_transcript_config()
    return TranscriptDefaultsResponse(
        preferred_languages=list(config.preferred_languages),
        prefer_manual=config.prefer_manual,
    )
