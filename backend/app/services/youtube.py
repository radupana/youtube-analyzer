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

    def extract_channel_id(self, url: str) -> str | None:
        """Extract channel ID or username from URL."""
        # Handle @username format
        if "@" in url:
            match = re.search(r"@([^/\s]+)", url)
            if match:
                return f"@{match.group(1)}"

        # Handle channel ID format
        match = re.search(r"/channel/([^/]+)", url)
        if match:
            return match.group(1)

        # Handle /c/username format
        match = re.search(r"/c/([^/]+)", url)
        if match:
            return match.group(1)

        return None

    def extract_playlist_id(self, url: str) -> str | None:
        """Extract playlist ID from URL."""
        match = re.search(r"list=([^&]+)", url)
        if match:
            return match.group(1)
        return None

    def get_video_info(self, video_id: str) -> dict[str, Any]:
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

    def get_channel_videos(
        self, channel_identifier: str, max_results: int = 50
    ) -> list[str]:
        """Get list of video IDs from a channel."""
        try:
            # If it's a @username, resolve to channel ID using forHandle
            if channel_identifier.startswith("@"):
                # Remove @ symbol for API call
                handle = channel_identifier[1:]

                try:
                    # Use forHandle parameter for precise @handle lookup
                    response = (
                        self.youtube.channels()
                        .list(part="contentDetails,snippet", forHandle=handle)
                        .execute()
                    )

                    if response.get("items"):
                        channel_id = response["items"][0]["id"]
                        channel_name = response["items"][0]["snippet"]["title"]
                        logger.info(f"Found channel: {channel_name} (ID: {channel_id})")
                    else:
                        # Fallback to search if forHandle doesn't work
                        logger.info(f"forHandle failed for {handle}, trying search...")
                        search_response = (
                            self.youtube.search()
                            .list(
                                part="snippet",
                                q=channel_identifier,
                                type="channel",
                                maxResults=5,  # Get more results to find the right one
                            )
                            .execute()
                        )

                        if not search_response.get("items"):
                            return []

                        # Try to find exact match
                        for item in search_response["items"]:
                            if handle.lower() in item["snippet"]["title"].lower():
                                channel_id = item["snippet"]["channelId"]
                                channel_name = item["snippet"]["title"]
                                logger.info(
                                    f"Found channel via search: {channel_name} (ID: {channel_id})"
                                )
                                break
                        else:
                            # Use first result as fallback
                            channel_id = search_response["items"][0]["snippet"][
                                "channelId"
                            ]
                            channel_name = search_response["items"][0]["snippet"][
                                "title"
                            ]
                            logger.info(
                                f"Warning: Using first search result: {channel_name} (ID: {channel_id})"
                            )

                except Exception as e:
                    logger.error(f"Error with forHandle, falling back to search: {e}")
                    # Fallback to search
                    search_response = (
                        self.youtube.search()
                        .list(
                            part="snippet",
                            q=channel_identifier,
                            type="channel",
                            maxResults=1,
                        )
                        .execute()
                    )

                    if not search_response.get("items"):
                        return []

                    channel_id = search_response["items"][0]["snippet"]["channelId"]
            else:
                channel_id = channel_identifier

            # Get channel's uploads playlist
            channel_response = (
                self.youtube.channels()
                .list(part="contentDetails", id=channel_id)
                .execute()
            )

            if not channel_response.get("items"):
                return []

            uploads_playlist_id = channel_response["items"][0]["contentDetails"][
                "relatedPlaylists"
            ]["uploads"]

            # Get videos from uploads playlist
            video_ids = []
            next_page_token = None

            while len(video_ids) < max_results:
                playlist_response = (
                    self.youtube.playlistItems()
                    .list(
                        part="contentDetails",
                        playlistId=uploads_playlist_id,
                        maxResults=min(50, max_results - len(video_ids)),
                        pageToken=next_page_token,
                    )
                    .execute()
                )

                for item in playlist_response.get("items", []):
                    video_ids.append(item["contentDetails"]["videoId"])

                next_page_token = playlist_response.get("nextPageToken")
                if not next_page_token:
                    break

            return video_ids[:max_results]

        except Exception as e:
            logger.error(f"Error fetching channel videos: {e}")
            return []

    def get_playlist_videos(self, playlist_id: str, max_results: int = 50) -> list[str]:
        """Get list of video IDs from a playlist."""
        try:
            video_ids = []
            next_page_token = None

            while len(video_ids) < max_results:
                response = (
                    self.youtube.playlistItems()
                    .list(
                        part="contentDetails",
                        playlistId=playlist_id,
                        maxResults=min(50, max_results - len(video_ids)),
                        pageToken=next_page_token,
                    )
                    .execute()
                )

                for item in response.get("items", []):
                    video_ids.append(item["contentDetails"]["videoId"])

                next_page_token = response.get("nextPageToken")
                if not next_page_token:
                    break

            return video_ids[:max_results]

        except Exception as e:
            logger.error(f"Error fetching playlist videos: {e}")
            return []

    def get_transcript(
        self, video_id: str, use_whisper_fallback: bool = None, progress_callback=None
    ) -> tuple[str | None, str]:
        """
        Get transcript for a video (YouTube captions or Whisper fallback).
        Returns: (transcript_text, source) where source is 'youtube' or 'whisper'
        """
        try:
            # Try YouTube transcript API first
            transcript_list = YouTubeTranscriptApi.list_transcripts(video_id)

            # Try to get English transcript
            try:
                transcript = transcript_list.find_transcript(["en"])
            except Exception:
                # Get any available transcript
                transcript = transcript_list.find_generated_transcript(["en"])

            # Combine all text
            text_parts = [entry["text"] for entry in transcript.fetch()]
            return " ".join(text_parts), "youtube"

        except Exception as e:
            logger.error(f"YouTube transcript not available: {e}")

            # Check if Whisper fallback is enabled
            if use_whisper_fallback is None:
                use_whisper_fallback = self.settings.enable_whisper_fallback

            # Fallback to Whisper if enabled
            if use_whisper_fallback:
                try:
                    from app.services.whisper import WhisperService

                    whisper_service = WhisperService()
                    transcript = whisper_service.get_whisper_transcript(
                        video_id, progress_callback
                    )
                    if transcript:
                        return transcript, "whisper"
                except Exception as whisper_error:
                    logger.error(f"Whisper fallback also failed: {whisper_error}")

            return None, "none"
