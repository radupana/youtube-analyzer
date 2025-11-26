"""YouTube API service for fetching video metadata and transcripts."""

import logging
import re
from datetime import datetime
from typing import Any

from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class YouTubeService:
    def __init__(self):
        self.settings = get_settings()
        self.youtube = build(
            "youtube", "v3", developerKey=self.settings.youtube_api_key
        )

    def extract_video_id(self, url: str) -> str | None:
        """Extract video ID from various YouTube URL formats."""
        patterns = [
            r"(?:v=|\/)([0-9A-Za-z_-]{11}).*",
            r"(?:embed\/)([0-9A-Za-z_-]{11})",
            r"(?:youtu\.be\/)([0-9A-Za-z_-]{11})",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def is_channel_url(self, url: str) -> bool:
        """Check if URL is a channel URL (not supported)."""
        channel_patterns = [
            r"/@[^/\s]+",  # @username format
            r"/channel/[^/]+",  # /channel/UC... format
            r"/c/[^/]+",  # /c/username format
            r"/user/[^/]+",  # /user/username format
        ]
        return any(re.search(pattern, url) for pattern in channel_patterns)

    def is_playlist_url(self, url: str) -> bool:
        """Check if URL is a playlist-only URL (not supported)."""
        # Only reject if it's a playlist page without a video
        # URLs like watch?v=xxx&list=yyy are fine (we extract the video)
        if "list=" in url and "watch?v=" not in url and "/watch?" not in url:
            return True
        if "/playlist?" in url:
            return True
        return False

    def get_video_info(self, video_id: str) -> dict[str, Any] | None:
        """Fetch video metadata from YouTube API."""
        try:
            response = (
                self.youtube.videos()
                .list(part="snippet,contentDetails,statistics", id=video_id)
                .execute()
            )

            if not response.get("items"):
                return None

            video = response["items"][0]
            return {
                "id": video_id,
                "title": video["snippet"]["title"],
                "channel_id": video["snippet"]["channelId"],
                "channel_title": video["snippet"]["channelTitle"],
                "description": video["snippet"]["description"],
                "duration": video["contentDetails"]["duration"],
                "published_at": datetime.fromisoformat(
                    video["snippet"]["publishedAt"].replace("Z", "+00:00")
                ),
                "view_count": int(video["statistics"].get("viewCount", 0)),
                "like_count": int(video["statistics"].get("likeCount", 0)),
            }
        except Exception as e:
            logger.error(f"Error fetching video info: {e}")
            return None

    def get_transcript(
        self,
        video_id: str,
        use_whisper_fallback: bool | None = None,
        progress_callback: Any = None,
    ) -> tuple[str | None, str]:
        """
        Get transcript for a video (YouTube captions or Whisper fallback).
        Returns: (transcript_text, source) where source is 'youtube' or 'whisper'
        """
        try:
            # Try YouTube transcript API first (v1.x API)
            logger.info(f"Attempting to fetch YouTube transcript for {video_id}")
            ytt_api = YouTubeTranscriptApi()

            # Try English first, then fall back to any available language
            try:
                transcript = ytt_api.fetch(video_id, languages=["en"])
                logger.info("Found English transcript")
            except Exception:
                # Try to get any transcript (will get first available)
                transcript = ytt_api.fetch(video_id)
                logger.info("Using auto-detected language transcript")

            # Combine all text - transcript is iterable with text/start/duration
            text_parts = [entry.text for entry in transcript]
            result = " ".join(text_parts)
            logger.info(f"Transcript fetched successfully ({len(result)} chars)")
            return result, "youtube"

        except Exception as e:
            logger.error(f"YouTube transcript not available: {e}")
            logger.exception("Full traceback:")

            # Check if Whisper fallback is enabled
            if use_whisper_fallback is None:
                use_whisper_fallback = self.settings.enable_whisper_fallback

            # Fallback to Whisper if enabled
            if use_whisper_fallback:
                try:
                    from app.services.whisper import WhisperService

                    whisper_service = WhisperService()
                    whisper_transcript = whisper_service.get_whisper_transcript(
                        video_id, progress_callback
                    )
                    if whisper_transcript:
                        return whisper_transcript, "whisper"
                except Exception as whisper_error:
                    logger.error(f"Whisper fallback also failed: {whisper_error}")

            return None, "none"
