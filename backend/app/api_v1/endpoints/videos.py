"""Video management endpoints - single video only."""

import asyncio
import logging
import time
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException

from app.api_v1.schemas import (
    TaskResponse,
    TaskStatus,
    Video,
    VideoCreate,
    VideoList,
    VideoStatus,
)
from app.services.cache import get_cache_service
from app.services.youtube import YouTubeService

logger = logging.getLogger(__name__)
router = APIRouter()

# In-memory storage (would use database in production)
loaded_videos: dict[str, Video] = {}
youtube_service = YouTubeService()
cache_service = get_cache_service()

# Progress tracking
task_progress: dict[str, dict] = {}

# Error message for unsupported URL types
UNSUPPORTED_URL_ERROR = (
    "Only single video URLs are supported. "
    "Please provide a URL in the format https://www.youtube.com/watch?v=..."
)


@router.post("/add", response_model=TaskResponse)
async def add_video(video_request: VideoCreate, background_tasks: BackgroundTasks):
    """Add a single YouTube video to the context."""
    url = video_request.url

    # Validate URL type - reject channels and playlists
    if youtube_service.is_channel_url(url):
        raise HTTPException(status_code=400, detail=UNSUPPORTED_URL_ERROR)

    if youtube_service.is_playlist_url(url):
        raise HTTPException(status_code=400, detail=UNSUPPORTED_URL_ERROR)

    # Extract video ID
    video_id = youtube_service.extract_video_id(url)
    if not video_id:
        raise HTTPException(status_code=400, detail=UNSUPPORTED_URL_ERROR)

    task_id = str(uuid4())

    # Initialize progress tracking
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
    }

    # Process in background
    background_tasks.add_task(process_single_video, task_id, video_id)

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

    # Always compute fresh elapsed time for smooth timer updates
    if progress["status"] not in (TaskStatus.COMPLETED, TaskStatus.FAILED):
        progress["elapsed_time"] = int(time.time() - progress["start_time"])

    return progress


async def process_single_video(task_id: str, video_id: str):
    """Process a single YouTube video."""
    try:
        task_progress[task_id]["status"] = TaskStatus.RUNNING
        task_progress[task_id]["message"] = "Loading video..."
        task_progress[task_id]["progress"] = 10.0

        # Small delay to ensure UI can fetch initial progress
        await asyncio.sleep(0.1)

        # Check if already loaded
        if video_id in loaded_videos:
            task_progress[task_id]["status"] = TaskStatus.COMPLETED
            task_progress[task_id]["progress"] = 100.0
            task_progress[task_id]["message"] = "Video already loaded."
            task_progress[task_id]["videos_added"].append(video_id)
            return

        # Check cache first
        cached_video = cache_service.load_video(video_id)
        if cached_video:
            task_progress[task_id]["current_step"] = "cache"
            task_progress[task_id]["message"] = "Loading from cache..."
            task_progress[task_id]["progress"] = 50.0

            video = Video(**cached_video)
            loaded_videos[video_id] = video
            task_progress[task_id]["videos_added"].append(video_id)
            task_progress[task_id]["current_video"] = (
                video.title[:50] + "..." if len(video.title) > 50 else video.title
            )

            task_progress[task_id]["status"] = TaskStatus.COMPLETED
            task_progress[task_id]["progress"] = 100.0
            task_progress[task_id]["message"] = f"Loaded from cache: {video.title}"
            task_progress[task_id]["processed"] = 1
            return

        # Fetch from YouTube
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

        # Create video object
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

        loaded_videos[video_id] = video
        task_progress[task_id]["videos_added"].append(video_id)

        # Get transcript
        task_progress[task_id]["current_step"] = "transcript"
        task_progress[task_id]["message"] = "Fetching transcript..."
        task_progress[task_id]["progress"] = 40.0

        # Create progress callback for Whisper
        def whisper_progress(step: str, message: str):
            task_progress[task_id]["current_step"] = step
            task_progress[task_id]["message"] = message
            task_progress[task_id]["elapsed_time"] = int(
                time.time() - task_progress[task_id]["start_time"]
            )
            # Update progress based on whisper step
            if step == "whisper_downloading":
                task_progress[task_id]["progress"] = 50.0
            elif step == "whisper_loading":
                task_progress[task_id]["progress"] = 60.0
            elif step == "whisper_transcribing":
                task_progress[task_id]["progress"] = 70.0

        # Run the blocking transcript fetch in a thread to not block the event loop
        # This allows progress polling to work during Whisper transcription
        transcript, source = await asyncio.to_thread(
            youtube_service.get_transcript, video_id, None, whisper_progress
        )

        if transcript:
            video.transcript = transcript
            video.transcript_source = source
            video.status = VideoStatus.READY
            task_progress[task_id]["progress"] = 90.0

            if source == "whisper":
                task_progress[task_id]["message"] = "Transcribed with Whisper"
            else:
                task_progress[task_id]["message"] = "Got YouTube captions"

            # Save to cache
            cache_service.save_video(video.model_dump())
        else:
            video.status = VideoStatus.ERROR
            video.transcript_source = "none"
            logger.warning(f"No transcript available for {video.title}")
            cache_service.save_video(video.model_dump())

        # Complete
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
        task_progress[task_id]["message"] = f"Error: {str(e)}"
        logger.error(f"Error processing video: {e}")


@router.get("/cache/load")
async def load_from_cache():
    """Load all cached videos into memory on startup."""
    cached_ids = cache_service.list_cached_videos()
    loaded_count = 0

    for video_id in cached_ids:
        if video_id not in loaded_videos:
            cached_video = cache_service.load_video(video_id)
            if cached_video:
                video = Video(**cached_video)
                loaded_videos[video_id] = video
                loaded_count += 1

    return {
        "success": True,
        "cached_videos": len(cached_ids),
        "loaded_videos": loaded_count,
        "message": f"Loaded {loaded_count} videos from cache",
    }


@router.get("", response_model=VideoList)
async def list_videos(
    skip: int = 0,
    limit: int = 100,
    status: VideoStatus | None = None,
):
    """List all loaded videos."""
    videos = list(loaded_videos.values())

    if status:
        videos = [v for v in videos if v.status == status]

    return VideoList(
        videos=videos[skip : skip + limit],
        total=len(videos),
    )


@router.get("/{video_id}", response_model=Video)
async def get_video(video_id: str):
    """Get a specific video by ID."""
    if video_id not in loaded_videos:
        raise HTTPException(status_code=404, detail="Video not found")
    return loaded_videos[video_id]


@router.delete("/{video_id}")
async def delete_video(video_id: str):
    """Remove a video from the context."""
    if video_id not in loaded_videos:
        raise HTTPException(status_code=404, detail="Video not found")

    del loaded_videos[video_id]
    return {"success": True, "message": "Video removed from context"}


@router.delete("/cache/clear")
async def clear_cache():
    """Clear all loaded videos and cache."""
    # Clear memory
    memory_count = len(loaded_videos)
    loaded_videos.clear()
    task_progress.clear()

    # Clear disk cache
    disk_count = cache_service.clear_cache()

    # Also clear Whisper model cache to free memory
    try:
        from app.services.whisper import WhisperService

        whisper_service = WhisperService()
        whisper_service.model = None
    except Exception:
        pass

    return {
        "success": True,
        "message": "Cache cleared",
        "memory_videos_cleared": memory_count,
        "disk_videos_cleared": disk_count,
    }
