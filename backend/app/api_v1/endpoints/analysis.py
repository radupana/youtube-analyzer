"""Video analysis endpoint."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api_v1.schemas import AnalysisRequest, AnalysisResponse
from app.core.llm_config import get_current_provider
from app.db.database import get_session
from app.db.models import Video, VideoAnalysis
from app.services.analysis import generate_analysis

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/{video_id}/analyze", response_model=AnalysisResponse)
async def analyze_video(
    video_id: str,
    request: AnalysisRequest | None = None,
    db: Session = Depends(get_session),
):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if not video.transcript:
        raise HTTPException(
            status_code=400,
            detail="Cannot analyze video without transcript",
        )

    force_regenerate = request.force_regenerate if request else False

    if not force_regenerate:
        cached = db.exec(
            select(VideoAnalysis).where(VideoAnalysis.video_id == video_id)
        ).first()

        if cached:
            logger.info(f"Returning cached analysis for {video_id}")
            return AnalysisResponse(
                video_id=video_id,
                summary=cached.summary,
                key_takeaways=json.loads(cached.key_takeaways),
                main_topics=json.loads(cached.main_topics),
                notable_quotes=json.loads(cached.notable_quotes),
                model_used=cached.model_used,
                created_at=cached.created_at,
                cached=True,
            )

    video_info = {
        "video_id": video.id,
        "title": video.title,
        "channel_title": video.channel_title,
        "duration": video.duration,
    }

    provider = get_current_provider()
    model_used = provider.model if provider else "unknown"

    logger.info(f"Generating analysis for {video_id} using {model_used}")
    analysis_output = await generate_analysis(video_info, video.transcript)

    if force_regenerate:
        existing = db.exec(
            select(VideoAnalysis).where(VideoAnalysis.video_id == video_id)
        ).first()
        if existing:
            db.delete(existing)
            db.commit()

    db_analysis = VideoAnalysis(
        video_id=video_id,
        summary=analysis_output.summary,
        key_takeaways=json.dumps(analysis_output.key_takeaways),
        main_topics=json.dumps(analysis_output.main_topics),
        notable_quotes=json.dumps(analysis_output.notable_quotes),
        model_used=model_used,
    )
    db.add(db_analysis)
    db.commit()
    db.refresh(db_analysis)

    logger.info(f"Analysis saved for {video_id}")

    return AnalysisResponse(
        video_id=video_id,
        summary=analysis_output.summary,
        key_takeaways=analysis_output.key_takeaways,
        main_topics=analysis_output.main_topics,
        notable_quotes=analysis_output.notable_quotes,
        model_used=model_used,
        created_at=db_analysis.created_at,
        cached=False,
    )


@router.get("/{video_id}/analysis", response_model=AnalysisResponse)
async def get_analysis(
    video_id: str,
    db: Session = Depends(get_session),
):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    cached = db.exec(
        select(VideoAnalysis).where(VideoAnalysis.video_id == video_id)
    ).first()

    if not cached:
        raise HTTPException(
            status_code=404,
            detail="No analysis found. Use POST to generate.",
        )

    return AnalysisResponse(
        video_id=video_id,
        summary=cached.summary,
        key_takeaways=json.loads(cached.key_takeaways),
        main_topics=json.loads(cached.main_topics),
        notable_quotes=json.loads(cached.notable_quotes),
        model_used=cached.model_used,
        created_at=cached.created_at,
        cached=True,
    )


@router.delete("/{video_id}/analysis")
async def delete_analysis(
    video_id: str,
    db: Session = Depends(get_session),
):
    cached = db.exec(
        select(VideoAnalysis).where(VideoAnalysis.video_id == video_id)
    ).first()

    if not cached:
        raise HTTPException(status_code=404, detail="No analysis found")

    db.delete(cached)
    db.commit()

    return {"success": True, "message": "Analysis deleted"}
