"""Video management endpoints with session persistence."""

import asyncio
import logging
from datetime import timedelta
from enum import Enum

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.api_v1.schemas import (
    AddVideoResponse,
    SessionScopedVideo,
    SessionScopedVideoList,
    TranscriptResponse,
    TranscriptSegmentSchema,
    VideoCreate,
    VideoList,
    VideoStatus,
)
from app.api_v1.schemas import Video as VideoSchema
from app.db.database import get_engine, get_session
from app.db.models import Chunk, PatternResult, SessionVideo, Video, utc_now
from app.db.models import Session as DBSession
from app.services.embeddings import clear_model
from app.services.export import export_json, export_markdown, export_srt, export_txt
from app.services.rag import process_transcript_for_rag
from app.services.youtube import YouTubeService


class ExportFormat(str, Enum):
    TXT = "txt"
    MARKDOWN = "md"
    SRT = "srt"
    JSON = "json"


logger = logging.getLogger(__name__)
router = APIRouter()

youtube_service = YouTubeService()

UNSUPPORTED_URL_ERROR = (
    "Only single video URLs are supported. "
    "Please provide a URL in the format https://www.youtube.com/watch?v=..."
)

STALE_PROCESSING_TIMEOUT = timedelta(minutes=15)


def _update_session_video_progress(
    session_video_id: str,
    status: str,
    progress: float,
    message: str,
    error: str | None = None,
):
    with Session(get_engine()) as db:
        sv = db.get(SessionVideo, session_video_id)
        if sv:
            sv.status = status
            sv.progress = progress
            sv.progress_message = message
            sv.updated_at = utc_now()
            if error:
                sv.error_message = error
            db.add(sv)
            db.commit()


@router.post("/add", response_model=AddVideoResponse)
async def add_video(
    video_request: VideoCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
):
    url = video_request.url
    session_id = video_request.session_id

    session = db.get(DBSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if youtube_service.is_channel_url(url):
        raise HTTPException(status_code=400, detail=UNSUPPORTED_URL_ERROR)

    if youtube_service.is_playlist_url(url):
        raise HTTPException(status_code=400, detail=UNSUPPORTED_URL_ERROR)

    video_id = youtube_service.extract_video_id(url)
    if not video_id:
        raise HTTPException(status_code=400, detail=UNSUPPORTED_URL_ERROR)

    existing_link = db.exec(
        select(SessionVideo)
        .where(SessionVideo.session_id == session_id)
        .where(SessionVideo.video_id == video_id)
    ).first()

    if existing_link:
        if existing_link.status in ("pending", "processing"):
            raise HTTPException(
                status_code=409,
                detail="Video is already being processed in this session",
            )
        if existing_link.status == "ready":
            return AddVideoResponse(
                video_id=video_id,
                status="ready",
                message="Video already added",
            )
        if existing_link.status == "error":
            existing_link.status = "pending"
            existing_link.progress = 0.0
            existing_link.progress_message = "Retrying..."
            existing_link.error_message = None
            existing_link.updated_at = utc_now()
            db.add(existing_link)
            db.commit()
            db.refresh(existing_link)
            background_tasks.add_task(
                process_video_for_session,
                existing_link.id,
                video_id,
                session_id,
            )
            return AddVideoResponse(
                video_id=video_id,
                session_video_id=existing_link.id,
                status="pending",
            )

    session_video = SessionVideo(
        session_id=session_id,
        video_id=video_id,
        status="pending",
        progress=0.0,
        progress_message="Queued...",
    )

    try:
        db.add(session_video)
        db.commit()
        db.refresh(session_video)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="Video is already being added to this session",
        ) from None

    background_tasks.add_task(
        process_video_for_session,
        session_video.id,
        video_id,
        session_id,
    )

    return AddVideoResponse(
        video_id=video_id,
        session_video_id=session_video.id,
        status="pending",
    )


async def process_video_for_session(
    session_video_id: str,
    video_id: str,
    session_id: str,
):
    try:
        _update_session_video_progress(
            session_video_id, "processing", 10.0, "Loading video..."
        )

        with Session(get_engine()) as db:
            existing_video = db.get(Video, video_id)

        if existing_video and existing_video.transcript:
            _update_session_video_progress(
                session_video_id, "processing", 50.0, "Loading from cache..."
            )

            _update_session_video_progress(
                session_video_id, "processing", 75.0, "Processing for search..."
            )
            await asyncio.to_thread(
                process_transcript_for_rag, video_id, existing_video.transcript
            )

            _update_session_video_progress(session_video_id, "ready", 100.0, "Ready")
            return

        _update_session_video_progress(
            session_video_id, "processing", 20.0, "Fetching metadata..."
        )
        video_info = await asyncio.to_thread(youtube_service.get_video_info, video_id)

        if not video_info:
            _update_session_video_progress(
                session_video_id,
                "error",
                0.0,
                "Video not found",
                error="Video not found or unavailable",
            )
            return

        # Save Video record early so title is available during processing
        with Session(get_engine()) as db:
            existing = db.get(Video, video_id)
            if not existing:
                db_video = Video(
                    id=video_id,
                    title=video_info["title"],
                    channel_id=video_info["channel_id"],
                    channel_title=video_info["channel_title"],
                    description=video_info.get("description", ""),
                    duration=video_info["duration"],
                    published_at=video_info["published_at"],
                    view_count=video_info.get("view_count", 0),
                    like_count=video_info.get("like_count", 0),
                    transcript=None,
                    transcript_source=None,
                )
                db.add(db_video)
                db.commit()

        _update_session_video_progress(
            session_video_id, "processing", 40.0, "Fetching transcript..."
        )

        def whisper_progress(step: str, message: str):
            progress_map = {
                "whisper_downloading": 50.0,
                "whisper_loading": 60.0,
                "whisper_transcribing": 70.0,
            }
            _update_session_video_progress(
                session_video_id,
                "processing",
                progress_map.get(step, 45.0),
                message,
            )

        transcript, source, segments = await asyncio.to_thread(
            youtube_service.get_transcript, video_id, None, whisper_progress
        )

        # Update transcript in existing Video record (created earlier with metadata)
        with Session(get_engine()) as db:
            existing = db.get(Video, video_id)
            if existing and transcript and not existing.transcript:
                existing.transcript = transcript
                existing.transcript_source = source
                db.add(existing)
                db.commit()

        if transcript:
            _update_session_video_progress(
                session_video_id, "processing", 85.0, "Processing for search..."
            )
            await asyncio.to_thread(
                process_transcript_for_rag, video_id, transcript, segments
            )
            _update_session_video_progress(session_video_id, "ready", 100.0, "Ready")
        else:
            _update_session_video_progress(
                session_video_id,
                "error",
                100.0,
                "No transcript available",
                error="No captions or Whisper transcription available",
            )

    except Exception as e:
        logger.exception("Error processing video")
        _update_session_video_progress(
            session_video_id,
            "error",
            0.0,
            f"Error: {e!s}",
            error=str(e),
        )


def _video_to_schema(video: Video) -> VideoSchema:
    return VideoSchema(
        id=video.id,
        title=video.title,
        channel_id=video.channel_id,
        channel_title=video.channel_title,
        duration=video.duration,
        published_at=video.published_at,
        status=VideoStatus.READY if video.transcript else VideoStatus.ERROR,
        transcript=video.transcript,
        transcript_source=video.transcript_source,
        description=video.description,
        view_count=video.view_count,
        like_count=video.like_count,
    )


@router.get("/session/{session_id}", response_model=SessionScopedVideoList)
async def list_session_videos(
    session_id: str,
    db: Session = Depends(get_session),
):
    session = db.get(DBSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session_videos = db.exec(
        select(SessionVideo).where(SessionVideo.session_id == session_id)
    ).all()

    now = utc_now()
    videos = []
    stale_updated = False

    for sv in session_videos:
        if sv.status == "processing":
            updated_at = sv.updated_at
            if updated_at.tzinfo is None:
                from datetime import UTC

                updated_at = updated_at.replace(tzinfo=UTC)
            elapsed = now - updated_at
            if elapsed > STALE_PROCESSING_TIMEOUT:
                sv.status = "error"
                sv.error_message = "Processing timed out - please retry"
                sv.progress_message = "Timed out"
                db.add(sv)
                stale_updated = True

        video = db.get(Video, sv.video_id)
        if video:
            videos.append(
                SessionScopedVideo(
                    id=video.id,
                    title=video.title,
                    channel_id=video.channel_id,
                    channel_title=video.channel_title,
                    duration=video.duration,
                    published_at=video.published_at,
                    transcript_source=video.transcript_source,
                    status=sv.status,
                    progress=sv.progress,
                    progress_message=sv.progress_message,
                    error_message=sv.error_message,
                )
            )
        else:
            videos.append(
                SessionScopedVideo(
                    id=sv.video_id,
                    title=f"Loading... ({sv.video_id})",
                    channel_id="",
                    channel_title="",
                    duration="",
                    published_at=now,
                    transcript_source=None,
                    status=sv.status,
                    progress=sv.progress,
                    progress_message=sv.progress_message,
                    error_message=sv.error_message,
                )
            )

    if stale_updated:
        db.commit()

    return SessionScopedVideoList(videos=videos, total=len(videos))


@router.delete("/session/{session_id}/video/{video_id}")
async def remove_video_from_session(
    session_id: str,
    video_id: str,
    db: Session = Depends(get_session),
):
    session_video = db.exec(
        select(SessionVideo)
        .where(SessionVideo.session_id == session_id)
        .where(SessionVideo.video_id == video_id)
    ).first()

    if not session_video:
        raise HTTPException(status_code=404, detail="Video not found in session")

    db.delete(session_video)
    db.commit()

    return {"success": True}


@router.get("", response_model=VideoList)
async def list_videos(db: Session = Depends(get_session)):
    videos = db.exec(select(Video)).all()
    return VideoList(
        videos=[_video_to_schema(v) for v in videos],
        total=len(videos),
    )


@router.get("/{video_id}/export")
async def export_transcript(
    video_id: str,
    format: ExportFormat = ExportFormat.TXT,
    db: Session = Depends(get_session),
):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if not video.transcript:
        raise HTTPException(
            status_code=400,
            detail="No transcript available for this video",
        )

    safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in video.title)[
        :50
    ]
    filename = f"{safe_title}_{video_id}.{format.value}"

    if format == ExportFormat.TXT:
        content = export_txt(video)
        return PlainTextResponse(
            content,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            media_type="text/plain; charset=utf-8",
        )

    if format == ExportFormat.MARKDOWN:
        content = export_markdown(video)
        return PlainTextResponse(
            content,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            media_type="text/markdown; charset=utf-8",
        )

    if format == ExportFormat.SRT:
        chunks = db.exec(
            select(Chunk).where(Chunk.video_id == video_id).order_by(Chunk.start_time)  # type: ignore[arg-type]
        ).all()

        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="SRT export requires timestamp data (not available)",
            )

        content = export_srt(list(chunks))
        return PlainTextResponse(
            content,
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            media_type="text/srt; charset=utf-8",
        )

    if format == ExportFormat.JSON:
        chunks = db.exec(
            select(Chunk).where(Chunk.video_id == video_id).order_by(Chunk.start_time)  # type: ignore[arg-type]
        ).all()

    pattern_results = db.exec(
        select(PatternResult).where(PatternResult.video_id == video_id)
    ).all()

    data = export_json(
        video, list(chunks) if chunks else None, list(pattern_results) or None
    )
    return JSONResponse(
        data,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{video_id}/transcript", response_model=TranscriptResponse)
async def get_transcript(video_id: str, db: Session = Depends(get_session)):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    if not video.transcript:
        raise HTTPException(
            status_code=400,
            detail="No transcript available for this video",
        )

    chunks = db.exec(
        select(Chunk).where(Chunk.video_id == video_id).order_by(Chunk.start_time)  # type: ignore[arg-type]
    ).all()

    segments = [
        TranscriptSegmentSchema(
            text=chunk.text,
            start_time=chunk.start_time,
            end_time=chunk.end_time,
        )
        for chunk in chunks
    ]

    has_timestamps = any(s.start_time > 0 or s.end_time > 0 for s in segments)

    return TranscriptResponse(
        video_id=video_id,
        video_title=video.title,
        full_text=video.transcript,
        segments=segments,
        has_timestamps=has_timestamps,
    )


@router.get("/{video_id}", response_model=VideoSchema)
async def get_video(video_id: str, db: Session = Depends(get_session)):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return _video_to_schema(video)


@router.delete("/{video_id}")
async def delete_video(video_id: str, db: Session = Depends(get_session)):
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")

    for sv in db.exec(
        select(SessionVideo).where(SessionVideo.video_id == video_id)
    ).all():
        db.delete(sv)

    db.delete(video)
    db.commit()

    return {"success": True, "message": "Video deleted"}


@router.delete("/cache/clear")
async def clear_cache(db: Session = Depends(get_session)):
    clear_model()

    chunks = db.exec(select(Chunk)).all()
    for chunk in chunks:
        db.delete(chunk)

    videos = db.exec(select(Video)).all()
    video_count = len(videos)
    for video in videos:
        db.delete(video)

    db.commit()

    return {
        "success": True,
        "message": "All videos cleared",
        "videos_cleared": video_count,
    }
