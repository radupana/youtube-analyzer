"""Video management endpoints with real YouTube integration."""

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


@router.post("/add", response_model=TaskResponse)
async def add_videos(video_request: VideoCreate, background_tasks: BackgroundTasks):
    """Add YouTube videos, channels, or playlists to the context."""
    task_id = str(uuid4())

    # Initialize progress tracking
    task_progress[task_id] = {
        "status": TaskStatus.PENDING,
        "progress": 0.0,
        "total": 0,
        "processed": 0,
        "message": "Starting...",
        "videos_added": [],
        "current_video": None,
        "current_step": None,
        "start_time": time.time(),
        "elapsed_time": 0,
    }

    # Process in background
    background_tasks.add_task(
        process_video_request,
        task_id,
        video_request.url,
        video_request.max_videos,
        video_request.load_transcripts,
    )

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
    return task_progress[task_id]


async def process_video_request(
    task_id: str, url: str, max_videos: int = 50, load_transcripts: bool = True
):
    """Process a YouTube URL and add videos to the context."""
    try:
        task_progress[task_id]["status"] = TaskStatus.RUNNING
        task_progress[task_id]["message"] = "Initializing..."
        task_progress[task_id]["current_step"] = "discovery"
        task_progress[task_id][
            "progress"
        ] = 5.0  # Start with 5% to show something immediately

        # Small delay to ensure UI can fetch initial progress
        await asyncio.sleep(0.1)

        task_progress[task_id]["message"] = "Fetching video list..."
        video_ids = []

        # Determine URL type and extract IDs
        if video_id := youtube_service.extract_video_id(url):
            video_ids = [video_id]
            task_progress[task_id]["message"] = "Processing single video..."
        elif channel_id := youtube_service.extract_channel_id(url):
            task_progress[task_id][
                "message"
            ] = f"Fetching channel videos (max {max_videos})..."
            video_ids = youtube_service.get_channel_videos(channel_id, max_videos)
        elif playlist_id := youtube_service.extract_playlist_id(url):
            task_progress[task_id][
                "message"
            ] = f"Fetching playlist videos (max {max_videos})..."
            video_ids = youtube_service.get_playlist_videos(playlist_id, max_videos)
        else:
            # Try to search for the URL as a channel name
            task_progress[task_id]["message"] = f"Searching for channel: {url}..."
            video_ids = youtube_service.get_channel_videos(url, max_videos)

        task_progress[task_id]["total"] = len(video_ids)
        task_progress[task_id]["progress"] = 10.0  # 10% after discovery

        if len(video_ids) == 1:
            task_progress[task_id]["message"] = "Loading video metadata..."
        else:
            task_progress[task_id][
                "message"
            ] = f"Found {len(video_ids)} videos. Loading metadata..."

        # Process videos with rate limiting
        for idx, vid_id in enumerate(video_ids):
            # Update elapsed time
            task_progress[task_id]["elapsed_time"] = int(
                time.time() - task_progress[task_id]["start_time"]
            )

            if vid_id not in loaded_videos:
                # Check cache first
                cached_video = cache_service.load_video(vid_id)

                if cached_video:
                    # Load from cache
                    task_progress[task_id]["current_step"] = "cache"
                    task_progress[task_id][
                        "message"
                    ] = f"Loading from cache: video {idx + 1}/{len(video_ids)}..."

                    video = Video(**cached_video)
                    loaded_videos[vid_id] = video
                    task_progress[task_id]["videos_added"].append(vid_id)
                    task_progress[task_id]["current_video"] = (
                        video.title[:50] + "..."
                        if len(video.title) > 50
                        else video.title
                    )

                    # Small delay to show cache loading
                    await asyncio.sleep(0.1)
                else:
                    # Not in cache, fetch from YouTube
                    task_progress[task_id]["current_step"] = "metadata"
                    task_progress[task_id][
                        "message"
                    ] = f"Loading metadata for video {idx + 1}/{len(video_ids)}..."

                    # Get video metadata
                    video_info = youtube_service.get_video_info(vid_id)
                    if video_info:
                        task_progress[task_id]["current_video"] = (
                            video_info["title"][:50] + "..."
                            if len(video_info["title"]) > 50
                            else video_info["title"]
                        )

                        # Create video with pending transcript status first
                        video = Video(
                            id=vid_id,
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

                        loaded_videos[vid_id] = video
                        task_progress[task_id]["videos_added"].append(vid_id)

                    # Only load transcripts if requested
                    if load_transcripts:
                        # Update step
                        task_progress[task_id]["current_step"] = "transcript"
                        task_progress[task_id][
                            "message"
                        ] = f"Getting transcript for video {idx + 1}/{len(video_ids)}..."

                        # Add delay to avoid rate limiting (429 errors)
                        # Use exponential backoff after failures
                        delay = 3.0 if idx < 5 else 5.0 if idx < 10 else 8.0
                        if idx > 0:
                            task_progress[task_id]["current_step"] = "rate_limit"
                            task_progress[task_id][
                                "message"
                            ] = f"Waiting {delay}s to avoid rate limits... (video {idx + 1}/{len(video_ids)})"
                            await asyncio.sleep(delay)

                        # Update status before transcript attempt
                        task_progress[task_id]["current_step"] = "transcript"

                        # Create progress callback for Whisper
                        def whisper_progress(step, message):
                            task_progress[task_id]["current_step"] = step
                            task_progress[task_id]["message"] = message
                            task_progress[task_id]["elapsed_time"] = int(
                                time.time() - task_progress[task_id]["start_time"]
                            )

                        transcript, source = youtube_service.get_transcript(
                            vid_id, progress_callback=whisper_progress
                        )

                        if transcript:
                            video.transcript = transcript
                            video.transcript_source = source
                            video.status = VideoStatus.READY

                            # Update progress message to indicate source
                            if source == "whisper":
                                task_progress[task_id]["current_step"] = "whisper"
                                task_progress[task_id][
                                    "message"
                                ] = f"Transcribed with Whisper: {task_progress[task_id]['current_video']}"
                            else:
                                task_progress[task_id][
                                    "message"
                                ] = f"Got YouTube captions for video {idx + 1}/{len(video_ids)}"

                            # Save to cache
                            cache_service.save_video(video.model_dump())
                        else:
                            # Mark as ERROR if no transcript available
                            video.status = VideoStatus.ERROR
                            video.transcript_source = "none"
                            logger.warning(f"No transcript available for {video.title}")

                            # Save to cache even without transcript
                            cache_service.save_video(video.model_dump())
                    else:
                        # Skip transcript loading - mark as ready without transcript
                        video.status = VideoStatus.READY
                        video.transcript = ""
                        video.transcript_source = "skipped"
                        task_progress[task_id][
                            "message"
                        ] = f"Loaded metadata for video {idx + 1}/{len(video_ids)} (transcripts skipped)..."

                        # Save to cache
                        cache_service.save_video(video.model_dump())

            # Update progress with more granularity
            # Base progress is from video completion (90% of total)
            # Reserve 10% for initial setup
            base_progress = 10.0  # Starting point after discovery
            video_progress = 90.0  # Remaining for video processing

            task_progress[task_id]["processed"] = idx + 1

            # Calculate progress based on videos completed plus partial progress for current video
            if task_progress[task_id]["current_step"] == "metadata":
                step_progress = 0.2  # 20% of current video
            elif task_progress[task_id]["current_step"] == "transcript":
                step_progress = 0.4  # 40% of current video
            elif task_progress[task_id]["current_step"] == "whisper_downloading":
                step_progress = 0.5  # 50% of current video
            elif task_progress[task_id]["current_step"] == "whisper_loading":
                step_progress = 0.6  # 60% of current video
            elif task_progress[task_id]["current_step"] == "whisper_transcribing":
                step_progress = 0.8  # 80% of current video
            elif task_progress[task_id]["current_step"] == "cache":
                step_progress = 0.1  # 10% of current video (fast)
            else:
                step_progress = 0.0

            # Calculate total progress
            videos_completed = idx
            current_video_progress = step_progress
            total_progress = base_progress + (
                video_progress
                * (videos_completed + current_video_progress)
                / len(video_ids)
            )

            task_progress[task_id]["progress"] = min(
                total_progress, 99.0
            )  # Cap at 99% until fully complete
            task_progress[task_id]["elapsed_time"] = int(
                time.time() - task_progress[task_id]["start_time"]
            )

        task_progress[task_id]["status"] = TaskStatus.COMPLETED
        task_progress[task_id]["progress"] = 100.0
        task_progress[task_id][
            "message"
        ] = f"Completed! Loaded {len(task_progress[task_id]['videos_added'])} videos."

    except Exception as e:
        task_progress[task_id]["status"] = TaskStatus.FAILED
        task_progress[task_id]["message"] = f"Error: {str(e)}"
        logger.error(f"Error processing videos: {e}")


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
