"""Patterns API endpoint with caching."""

import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api_v1.schemas import (
    PatternListResponse,
    PatternResultResponse,
    PatternSummaryResponse,
)
from app.db.database import get_session
from app.db.models import PatternResult, Video
from app.services.pattern_execution import execute_pattern
from app.services.patterns import get_pattern, list_patterns, validate_inputs

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("", response_model=PatternListResponse)
async def get_patterns():
    """List all available patterns."""
    patterns = list_patterns()
    return PatternListResponse(
        patterns=[
            PatternSummaryResponse(
                id=p.id,
                name=p.name,
                description=p.description,
                icon=p.icon,
                category=p.category,
            )
            for p in patterns
        ]
    )


@router.get(
    "/videos/{video_id}/results",
    response_model=list[PatternResultResponse],
)
async def get_video_pattern_results(
    video_id: str,
    db: Session = Depends(get_session),
):
    """List all cached pattern results for a video."""
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    results = db.exec(
        select(PatternResult).where(PatternResult.video_id == video_id)
    ).all()

    response = []
    for r in results:
        pattern = get_pattern(r.pattern_id)
        pattern_name = pattern.name if pattern else r.pattern_id
        response.append(
            PatternResultResponse(
                video_id=r.video_id,
                pattern_id=r.pattern_id,
                pattern_name=pattern_name,
                result=r.result,
                model_used=r.model_used,
                created_at=r.created_at,
            )
        )

    return response


@router.get(
    "/videos/{video_id}/results/{pattern_id}",
    response_model=PatternResultResponse,
)
async def get_pattern_result(
    video_id: str,
    pattern_id: str,
    db: Session = Depends(get_session),
):
    """Get a specific cached pattern result."""
    cached = db.exec(
        select(PatternResult).where(
            PatternResult.video_id == video_id,
            PatternResult.pattern_id == pattern_id,
        )
    ).first()

    if not cached:
        raise HTTPException(status_code=404, detail="Pattern result not found")

    pattern = get_pattern(pattern_id)
    pattern_name = pattern.name if pattern else pattern_id

    return PatternResultResponse(
        video_id=cached.video_id,
        pattern_id=cached.pattern_id,
        pattern_name=pattern_name,
        result=cached.result,
        model_used=cached.model_used,
        created_at=cached.created_at,
    )


@router.post(
    "/videos/{video_id}/results/{pattern_id}",
    response_model=PatternResultResponse,
)
async def apply_pattern(
    video_id: str,
    pattern_id: str,
    db: Session = Depends(get_session),
):
    """Apply a pattern to a video. Returns cached result if exists."""
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    pattern = get_pattern(pattern_id)
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    cached = db.exec(
        select(PatternResult).where(
            PatternResult.video_id == video_id,
            PatternResult.pattern_id == pattern_id,
        )
    ).first()

    if cached:
        logger.info(f"Returning cached result for {pattern_id} on {video_id}")
        return PatternResultResponse(
            video_id=cached.video_id,
            pattern_id=cached.pattern_id,
            pattern_name=pattern.name,
            result=cached.result,
            model_used=cached.model_used,
            created_at=cached.created_at,
        )

    available = {
        "transcript": video.transcript,
        "video_title": video.title,
        "channel": video.channel_title,
    }
    missing = validate_inputs(pattern, available)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Video missing required data: {', '.join(missing)}",
        )

    logger.info(f"Executing pattern {pattern_id} on video {video_id}")
    if video.transcript is None:
        raise HTTPException(status_code=422, detail="Video transcript is missing")
    result = await execute_pattern(
        pattern=pattern,
        video_title=video.title,
        channel=video.channel_title,
        transcript=video.transcript,
        video_id=video_id,
    )

    db_result = PatternResult(
        video_id=video_id,
        pattern_id=pattern_id,
        result=result.content,
        model_used=result.model_used,
    )
    db.add(db_result)
    db.commit()
    db.refresh(db_result)

    logger.info(f"Saved pattern result for {pattern_id} on {video_id}")

    return PatternResultResponse(
        video_id=db_result.video_id,
        pattern_id=db_result.pattern_id,
        pattern_name=pattern.name,
        result=db_result.result,
        model_used=db_result.model_used,
        created_at=db_result.created_at,
    )


@router.post(
    "/videos/{video_id}/results/{pattern_id}/refresh",
    response_model=PatternResultResponse,
)
async def refresh_pattern(
    video_id: str,
    pattern_id: str,
    db: Session = Depends(get_session),
):
    """Force re-run a pattern, replacing any cached result."""
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    pattern = get_pattern(pattern_id)
    if not pattern:
        raise HTTPException(status_code=404, detail="Pattern not found")

    available = {
        "transcript": video.transcript,
        "video_title": video.title,
        "channel": video.channel_title,
    }
    missing = validate_inputs(pattern, available)
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"Video missing required data: {', '.join(missing)}",
        )

    existing = db.exec(
        select(PatternResult).where(
            PatternResult.video_id == video_id,
            PatternResult.pattern_id == pattern_id,
        )
    ).first()
    if existing:
        db.delete(existing)
        db.commit()

    logger.info(f"Refreshing pattern {pattern_id} on video {video_id}")
    if video.transcript is None:
        raise HTTPException(status_code=422, detail="Video transcript is missing")
    result = await execute_pattern(
        pattern=pattern,
        video_title=video.title,
        channel=video.channel_title,
        transcript=video.transcript,
        video_id=video_id,
    )

    db_result = PatternResult(
        video_id=video_id,
        pattern_id=pattern_id,
        result=result.content,
        model_used=result.model_used,
    )
    db.add(db_result)
    db.commit()
    db.refresh(db_result)

    return PatternResultResponse(
        video_id=db_result.video_id,
        pattern_id=db_result.pattern_id,
        pattern_name=pattern.name,
        result=db_result.result,
        model_used=db_result.model_used,
        created_at=db_result.created_at,
    )


@router.delete("/videos/{video_id}/results/{pattern_id}")
async def delete_pattern_result(
    video_id: str,
    pattern_id: str,
    db: Session = Depends(get_session),
):
    """Delete a specific pattern result."""
    cached = db.exec(
        select(PatternResult).where(
            PatternResult.video_id == video_id,
            PatternResult.pattern_id == pattern_id,
        )
    ).first()

    if not cached:
        raise HTTPException(status_code=404, detail="Pattern result not found")

    db.delete(cached)
    db.commit()

    return {"success": True}
