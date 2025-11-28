"""Video management endpoints with session persistence."""

import asyncio
import logging
import time
from enum import Enum
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from fastapi.responses import JSONResponse, PlainTextResponse
from sqlmodel import Session, select

from app.api_v1.schemas import (
    TaskResponse,
    TaskStatus,
    VideoCreate,
    VideoList,
    VideoStatus,
)
from app.api_v1.schemas import Video as VideoSchema
from app.db.database import get_engine, get_session
from app.db.models import Chunk, SessionVideo, Video, utc_now
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

task_progress: dict[str, dict] = {}

UNSUPPORTED_URL_ERROR = (
    "Only single video URLs are supported. "
    "Please provide a URL in the format https://www.youtube.com/watch?v=..."
)


@router.post("/add", response_model=TaskResponse)
async def add_video(
    video_request: VideoCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_session),
):
    """Add a single YouTube video to a session."""
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

    task_id = str(uuid4())

    task_progress[task_id] = {
        "status": TaskStatus.PENDING,
        "progress": 0.0,
        "total": 1,
        "processed": 0,
        "message": "Starting...",
        "videos_added": [],
        "current_video": None,
        "current_step": None,
        "start_time": time.time(),
        "elapsed_time": 0,
        "session_id": session_id,
    }

    background_tasks.add_task(process_single_video, task_id, video_id, session_id)

    return TaskResponse(
        task_id=task_id,
        status=TaskStatus.PENDING,
        progress=0.0,
    )


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of a video loading task."""
    if task_id not in task_progress:
        raise HTTPException(status_code=404, detail="Task not found")

    progress = task_progress[task_id]

    if progress["status"] not in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        progress["elapsed_time"] = int(time.time() - progress["start_time"])

    return progress


async def process_single_video(task_id: str, video_id: str, session_id: str):
    """Process a single YouTube video and save to session."""
    try:
        task_progress[task_id]["status"] = TaskStatus.RUNNING
        task_progress[task_id]["message"] = "Loading video..."
        task_progress[task_id]["progress"] = 10.0

        with Session(get_engine()) as db:
            existing_video = db.get(Video, video_id)
            if existing_video:
                cached_title = existing_video.title
                cached_transcript = existing_video.transcript

        if existing_video:
            task_progress[task_id]["current_step"] = "cache"
            task_progress[task_id]["message"] = "Loading from database..."
            task_progress[task_id]["progress"] = 50.0
            task_progress[task_id]["videos_added"].append(video_id)
            task_progress[task_id]["current_video"] = (
                cached_title[:50] + "..." if len(cached_title) > 50 else cached_title
            )

            if cached_transcript:
                task_progress[task_id]["current_step"] = "rag"
                task_progress[task_id]["message"] = "Processing for search..."
                task_progress[task_id]["progress"] = 75.0
                await asyncio.to_thread(
                    process_transcript_for_rag, video_id, cached_transcript
                )

            await _link_video_to_session(session_id, video_id)

            task_progress[task_id]["status"] = TaskStatus.COMPLETED
            task_progress[task_id]["progress"] = 100.0
            task_progress[task_id]["message"] = f"Loaded from database: {cached_title}"
            task_progress[task_id]["processed"] = 1
            return

        task_progress[task_id]["current_step"] = "metadata"
        task_progress[task_id]["message"] = "Fetching video metadata..."
        task_progress[task_id]["progress"] = 20.0

        video_info = await asyncio.to_thread(youtube_service.get_video_info, video_id)
        if not video_info:
            task_progress[task_id]["status"] = TaskStatus.FAILED
            task_progress[task_id]["message"] = "Video not found or unavailable."
            return

        task_progress[task_id]["current_video"] = (
            video_info["title"][:50] + "..."
            if len(video_info["title"]) > 50
            else video_info["title"]
        )
        task_progress[task_id]["progress"] = 30.0
        task_progress[task_id]["videos_added"].append(video_id)

        task_progress[task_id]["current_step"] = "transcript"
        task_progress[task_id]["message"] = "Fetching transcript..."
        task_progress[task_id]["progress"] = 40.0

        def whisper_progress(step: str, message: str):
            task_progress[task_id]["current_step"] = step
            task_progress[task_id]["message"] = message
            task_progress[task_id]["elapsed_time"] = int(
                time.time() - task_progress[task_id]["start_time"]
            )
            if step == "whisper_downloading":
                task_progress[task_id]["progress"] = 50.0
            elif step == "whisper_loading":
                task_progress[task_id]["progress"] = 60.0
            elif step == "whisper_transcribing":
                task_progress[task_id]["progress"] = 70.0

        transcript, source, segments = await asyncio.to_thread(
            youtube_service.get_transcript, video_id, None, whisper_progress
        )

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
            transcript=transcript,
            transcript_source=source if transcript else "none",
        )

        with Session(get_engine()) as db:
            db.add(db_video)
            db.commit()

        if transcript:
            task_progress[task_id]["progress"] = 85.0
            if source == "whisper":
                task_progress[task_id]["message"] = "Transcribed with Whisper"
            else:
                task_progress[task_id]["message"] = "Got YouTube captions"

            task_progress[task_id]["current_step"] = "rag"
            task_progress[task_id]["message"] = "Processing for search..."
            task_progress[task_id]["progress"] = 90.0
            await asyncio.to_thread(
                process_transcript_for_rag, video_id, transcript, segments
            )
        else:
            logger.warning(f"No transcript available for {video_info['title']}")

        await _link_video_to_session(session_id, video_id)

        task_progress[task_id]["status"] = TaskStatus.COMPLETED
        task_progress[task_id]["progress"] = 100.0
        task_progress[task_id]["processed"] = 1
        task_progress[task_id]["elapsed_time"] = int(
            time.time() - task_progress[task_id]["start_time"]
        )

        if transcript:
            task_progress[task_id]["message"] = f"Loaded: {video_info['title']}"
        else:
            msg = f"Loaded (no transcript): {video_info['title']}"
            task_progress[task_id]["message"] = msg

    except Exception as e:
        task_progress[task_id]["status"] = TaskStatus.FAILED
        task_progress[task_id]["message"] = f"Error: {e!s}"
        logger.error(f"Error processing video: {e}")


async def _link_video_to_session(session_id: str, video_id: str):
    """Link a video to a session (create SessionVideo if not exists)."""
    with Session(get_engine()) as db:
        session = db.get(DBSession, session_id)
        if not session:
            return

        existing = db.exec(
            select(SessionVideo)
            .where(SessionVideo.session_id == session_id)
            .where(SessionVideo.video_id == video_id)
        ).first()

        if not existing:
            session_video = SessionVideo(
                session_id=session_id,
                video_id=video_id,
            )
            db.add(session_video)

        session.updated_at = utc_now()
        db.add(session)
        db.commit()


def _video_to_schema(video: Video) -> VideoSchema:
    """Convert database Video to API schema."""
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


@router.get("/session/{session_id}", response_model=VideoList)
async def list_session_videos(
    session_id: str,
    db: Session = Depends(get_session),
):
    """List all videos in a session."""
    session = db.get(DBSession, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    session_videos = db.exec(
        select(SessionVideo).where(SessionVideo.session_id == session_id)
    ).all()

    videos = []
    for sv in session_videos:
        video = db.get(Video, sv.video_id)
        if video:
            videos.append(_video_to_schema(video))

    return VideoList(videos=videos, total=len(videos))


@router.delete("/session/{session_id}/video/{video_id}")
async def remove_video_from_session(
    session_id: str,
    video_id: str,
    db: Session = Depends(get_session),
):
    """Remove a video from a session."""
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
    """List all videos in database."""
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
    """Export video transcript in various formats."""
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

    # JSON format - reuse chunks variable from SRT check if available, otherwise query
    if format == ExportFormat.JSON:
        chunks = db.exec(
            select(Chunk).where(Chunk.video_id == video_id).order_by(Chunk.start_time)  # type: ignore[arg-type]
        ).all()

    data = export_json(video, list(chunks) if chunks else None)
    return JSONResponse(
        data,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{video_id}", response_model=VideoSchema)
async def get_video(video_id: str, db: Session = Depends(get_session)):
    """Get a specific video by ID."""
    video = db.get(Video, video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Video not found")
    return _video_to_schema(video)


@router.delete("/{video_id}")
async def delete_video(video_id: str, db: Session = Depends(get_session)):
    """Delete a video and its chunks from database."""
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
    """Clear all videos and chunks from database."""
    task_progress.clear()
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
