"""Video management endpoints with session persistence."""

import asyncio
import logging
import time
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlmodel import Session, select

from app.api_v1.schemas import (
    TaskResponse,
    TaskStatus,
    Video,
    VideoCreate,
    VideoList,
    VideoStatus,
)
from app.db.database import get_engine, get_session
from app.db.models import Session as DBSession
from app.db.models import SessionVideo, utc_now
from app.services.cache import get_cache_service
from app.services.rag import has_rag_data, process_transcript_for_rag
from app.services.youtube import YouTubeService

logger = logging.getLogger(__name__)
router = APIRouter()

youtube_service = YouTubeService()
cache_service = get_cache_service()

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

        cached_video = cache_service.load_video(video_id)
        if cached_video:
            task_progress[task_id]["current_step"] = "cache"
            task_progress[task_id]["message"] = "Loading from cache..."
            task_progress[task_id]["progress"] = 50.0

            video = Video(**cached_video)
            task_progress[task_id]["videos_added"].append(video_id)
            task_progress[task_id]["current_video"] = (
                video.title[:50] + "..." if len(video.title) > 50 else video.title
            )

            if video.transcript and not has_rag_data(video_id):
                task_progress[task_id]["current_step"] = "rag"
                task_progress[task_id]["message"] = "Processing for search..."
                task_progress[task_id]["progress"] = 75.0
                await asyncio.to_thread(
                    process_transcript_for_rag, video_id, video.transcript
                )

            await save_video_to_session(session_id, video)

            task_progress[task_id]["status"] = TaskStatus.COMPLETED
            task_progress[task_id]["progress"] = 100.0
            task_progress[task_id]["message"] = f"Loaded from cache: {video.title}"
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

        video = Video(
            id=video_id,
            title=video_info["title"],
            channel_id=video_info["channel_id"],
            channel_title=video_info["channel_title"],
            duration=video_info["duration"],
            published_at=video_info["published_at"],
            status=VideoStatus.PROCESSING,
            transcript="",
            description=video_info.get("description", ""),
            view_count=video_info.get("view_count", 0),
            like_count=video_info.get("like_count", 0),
        )

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

        transcript, source = await asyncio.to_thread(
            youtube_service.get_transcript, video_id, None, whisper_progress
        )

        if transcript:
            video.transcript = transcript
            video.transcript_source = source
            video.status = VideoStatus.READY
            task_progress[task_id]["progress"] = 85.0

            if source == "whisper":
                task_progress[task_id]["message"] = "Transcribed with Whisper"
            else:
                task_progress[task_id]["message"] = "Got YouTube captions"

            cache_service.save_video(video.model_dump())

            task_progress[task_id]["current_step"] = "rag"
            task_progress[task_id]["message"] = "Processing for search..."
            task_progress[task_id]["progress"] = 90.0
            await asyncio.to_thread(process_transcript_for_rag, video_id, transcript)
        else:
            video.status = VideoStatus.ERROR
            video.transcript_source = "none"
            logger.warning(f"No transcript available for {video.title}")
            cache_service.save_video(video.model_dump())

        await save_video_to_session(session_id, video)

        task_progress[task_id]["status"] = TaskStatus.COMPLETED
        task_progress[task_id]["progress"] = 100.0
        task_progress[task_id]["processed"] = 1
        task_progress[task_id]["elapsed_time"] = int(
            time.time() - task_progress[task_id]["start_time"]
        )

        if video.status == VideoStatus.READY:
            task_progress[task_id]["message"] = f"Loaded: {video.title}"
        else:
            task_progress[task_id]["message"] = f"Loaded (no transcript): {video.title}"

    except Exception as e:
        task_progress[task_id]["status"] = TaskStatus.FAILED
        task_progress[task_id]["message"] = f"Error: {e!s}"
        logger.error(f"Error processing video: {e}")


async def save_video_to_session(session_id: str, video: Video):
    """Save video to database session."""
    with Session(get_engine()) as db:
        session = db.get(DBSession, session_id)
        if not session:
            return

        existing = db.exec(
            select(SessionVideo)
            .where(SessionVideo.session_id == session_id)
            .where(SessionVideo.video_id == video.id)
        ).first()

        if existing:
            existing.transcript = video.transcript
            existing.transcript_source = video.transcript_source
            db.add(existing)
        else:
            session_video = SessionVideo(
                session_id=session_id,
                video_id=video.id,
                title=video.title,
                channel_title=video.channel_title,
                transcript=video.transcript,
                transcript_source=video.transcript_source,
            )
            db.add(session_video)

        session.updated_at = utc_now()
        db.add(session)
        db.commit()


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
        cached = cache_service.load_video(sv.video_id)
        if cached:
            videos.append(Video(**cached))
        else:
            videos.append(
                Video(
                    id=sv.video_id,
                    title=sv.title,
                    channel_id="",
                    channel_title=sv.channel_title,
                    duration="",
                    published_at=sv.added_at,
                    status=VideoStatus.READY if sv.transcript else VideoStatus.ERROR,
                    transcript=sv.transcript,
                    transcript_source=sv.transcript_source,
                )
            )

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


@router.get("/cache/load")
async def load_from_cache():
    """List all cached videos (for debugging)."""
    cached_ids = cache_service.list_cached_videos()
    return {
        "success": True,
        "cached_videos": len(cached_ids),
        "video_ids": cached_ids,
    }


@router.get("", response_model=VideoList)
async def list_videos():
    """List all cached videos."""
    cached_ids = cache_service.list_cached_videos()
    videos = []
    for video_id in cached_ids:
        cached = cache_service.load_video(video_id)
        if cached:
            videos.append(Video(**cached))
    return VideoList(videos=videos, total=len(videos))


@router.get("/{video_id}", response_model=Video)
async def get_video(video_id: str):
    """Get a specific video by ID from cache."""
    cached = cache_service.load_video(video_id)
    if not cached:
        raise HTTPException(status_code=404, detail="Video not found")
    return Video(**cached)


@router.delete("/{video_id}")
async def delete_video(video_id: str):
    """Remove a video from cache (not from sessions)."""
    if not cache_service.has_video(video_id):
        raise HTTPException(status_code=404, detail="Video not found")

    return {"success": True, "message": "Video removed from cache"}


@router.delete("/cache/clear")
async def clear_cache():
    """Clear all video cache."""
    task_progress.clear()
    disk_count = cache_service.clear_cache()

    try:
        from app.services.whisper import WhisperService

        whisper_service = WhisperService()
        whisper_service.model = None
    except Exception as e:
        logger.debug(f"Could not clear Whisper model: {e}")

    return {
        "success": True,
        "message": "Cache cleared",
        "disk_videos_cleared": disk_count,
    }
