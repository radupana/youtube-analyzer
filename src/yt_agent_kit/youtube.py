"""YouTube API integration for channel discovery and video listing."""

import hashlib
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any

from googleapiclient.discovery import build

from .cache import get_from_cache, save_to_cache

MAX_RESULTS_PER_PAGE = 50

VIDEO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{11}$")
VIDEO_URL_PATTERN = re.compile(
    r"(?:youtube\.com/watch\?v=|youtu\.be/|youtube\.com/embed/)([a-zA-Z0-9_-]{11})"
)
PLAYLIST_URL_PATTERN = re.compile(r"youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)")
PLAYLIST_ID_PATTERN = re.compile(r"^(PL|UU|LL|WL|FL|RD)[a-zA-Z0-9_-]+$")
CHANNEL_URL_PATTERN = re.compile(r"youtube\.com/channel/([\w-]+)")
CHANNEL_ID_PATTERN = re.compile(r"^UC[\w-]{22}$")
HANDLE_PATTERN = re.compile(r"^@[\w.-]+$")
HANDLE_URL_PATTERN = re.compile(r"youtube\.com/@([\w.-]+)")


class InputType(Enum):
    VIDEO = "video"
    CHANNEL = "channel"
    PLAYLIST = "playlist"


@dataclass
class ChannelInfo:
    """YouTube channel metadata."""

    id: str
    title: str
    description: str
    subscriber_count: int
    video_count: int
    custom_url: str | None


@dataclass
class VideoInfo:
    """YouTube video metadata."""

    id: str
    title: str
    description: str
    published_at: str
    duration: str


def find_channel_id(query: str, api_key: str) -> ChannelInfo:
    """
    Find YouTube channel by name, URL, or handle.

    Supports:
    - Channel names: "Jeff Nippard"
    - @handles: "@JeffNippard"
    - Full URLs: "https://youtube.com/@JeffNippard"
    - Channel IDs: "UCqjwF8rxRsotnojGl4gM0Zw"

    Args:
        query: Channel name, URL, @handle, or ID
        api_key: YouTube Data API key

    Returns:
        ChannelInfo with channel metadata

    Raises:
        ValueError: If channel not found
    """
    cache_key = f"channel_{hashlib.sha256(query.encode()).hexdigest()}"
    cached = get_from_cache(cache_key)
    if cached:
        return ChannelInfo(**cached)

    channel_id = _extract_channel_id(query)

    youtube = build("youtube", "v3", developerKey=api_key)

    if channel_id:
        request = youtube.channels().list(part="snippet,statistics", id=channel_id)
    else:
        clean_query = query.lstrip("@")
        request = youtube.search().list(
            part="snippet", q=clean_query, type="channel", maxResults=1
        )

    response = request.execute()

    if not response.get("items"):
        raise ValueError(f"Channel not found: {query}")

    if channel_id:
        item = response["items"][0]
    else:
        search_item = response["items"][0]
        channel_id = search_item["id"]["channelId"]
        channel_request = youtube.channels().list(
            part="snippet,statistics", id=channel_id
        )
        channel_response = channel_request.execute()
        item = channel_response["items"][0]

    snippet = item["snippet"]
    statistics = item["statistics"]

    channel_info = ChannelInfo(
        id=item["id"],
        title=snippet["title"],
        description=snippet["description"],
        subscriber_count=int(statistics.get("subscriberCount", 0)),
        video_count=int(statistics.get("videoCount", 0)),
        custom_url=snippet.get("customUrl"),
    )

    save_to_cache(cache_key, channel_info.__dict__)
    return channel_info


def list_videos(
    channel_id: str, api_key: str, max_results: int = MAX_RESULTS_PER_PAGE
) -> list[VideoInfo]:
    """
    List videos from channel sorted by view count (most viewed first).

    Args:
        channel_id: YouTube channel ID
        api_key: YouTube Data API key
        max_results: Maximum number of videos to return

    Returns:
        List of VideoInfo objects sorted by view count descending
    """

    cache_key = f"videos_{channel_id}_{max_results}"
    cached = get_from_cache(cache_key)
    if cached:
        return [VideoInfo(**v) for v in cached]

    youtube = build("youtube", "v3", developerKey=api_key)

    search_request = youtube.search().list(
        part="id",
        channelId=channel_id,
        type="video",
        order="viewCount",  # Sort by most viewed first
        maxResults=min(max_results, MAX_RESULTS_PER_PAGE),
    )

    videos: list[VideoInfo] = []
    video_ids: list[str] = []

    while search_request and len(video_ids) < max_results:
        search_response = search_request.execute()

        for item in search_response.get("items", []):
            video_ids.append(item["id"]["videoId"])
            if len(video_ids) >= max_results:
                break

        if len(video_ids) >= max_results:
            break

        search_request = youtube.search().list_next(search_request, search_response)

    # Fetch video details in batches of 50 (API limit)
    if video_ids:
        BATCH_SIZE = 50
        for i in range(0, len(video_ids), BATCH_SIZE):
            batch = video_ids[i : i + BATCH_SIZE]
            video_request = youtube.videos().list(
                part="snippet,contentDetails", id=",".join(batch)
            )
            video_response = video_request.execute()

            for item in video_response.get("items", []):
                snippet = item["snippet"]
                content_details = item["contentDetails"]

                videos.append(
                    VideoInfo(
                        id=item["id"],
                        title=snippet["title"],
                        description=snippet["description"],
                        published_at=snippet["publishedAt"],
                        duration=content_details["duration"],
                    )
                )

    video_dicts = [v.__dict__ for v in videos]
    save_to_cache(cache_key, video_dicts)

    return videos


def _extract_channel_id(query: str) -> str | None:
    match = CHANNEL_URL_PATTERN.search(query)
    if match:
        return match.group(1)
    if CHANNEL_ID_PATTERN.match(query):
        return query
    return None


def detect_input_type(user_input: str) -> tuple[InputType, str]:
    user_input = user_input.strip()

    match = VIDEO_URL_PATTERN.search(user_input)
    if match:
        return InputType.VIDEO, match.group(1)

    match = PLAYLIST_URL_PATTERN.search(user_input)
    if match:
        return InputType.PLAYLIST, match.group(1)

    if PLAYLIST_ID_PATTERN.match(user_input):
        return InputType.PLAYLIST, user_input

    match = HANDLE_URL_PATTERN.search(user_input)
    if match:
        return InputType.CHANNEL, f"@{match.group(1)}"

    match = CHANNEL_URL_PATTERN.search(user_input)
    if match:
        return InputType.CHANNEL, match.group(1)

    if VIDEO_ID_PATTERN.match(user_input):
        return InputType.VIDEO, user_input

    if CHANNEL_ID_PATTERN.match(user_input):
        return InputType.CHANNEL, user_input

    if HANDLE_PATTERN.match(user_input):
        return InputType.CHANNEL, user_input

    return InputType.CHANNEL, user_input


def get_playlist_video_ids(
    playlist_id: str, api_key: str, max_results: int = 500
) -> list[str]:
    cache_key = f"playlist_videos_{playlist_id}_{max_results}"
    cached = get_from_cache(cache_key)
    if cached is not None:
        return list(cached)

    youtube = build("youtube", "v3", developerKey=api_key)
    video_ids: list[str] = []

    request = youtube.playlistItems().list(
        part="contentDetails",
        playlistId=playlist_id,
        maxResults=min(max_results, MAX_RESULTS_PER_PAGE),
    )

    while request and len(video_ids) < max_results:
        response = request.execute()

        for item in response.get("items", []):
            video_id = item.get("contentDetails", {}).get("videoId")
            if video_id:
                video_ids.append(video_id)
                if len(video_ids) >= max_results:
                    break

        if len(video_ids) >= max_results:
            break

        request = youtube.playlistItems().list_next(request, response)

    save_to_cache(cache_key, video_ids)
    return video_ids


def get_playlist_info(playlist_id: str, api_key: str) -> dict[str, Any]:
    cache_key = f"playlist_info_{playlist_id}"
    cached = get_from_cache(cache_key)
    if cached is not None:
        return dict(cached)

    youtube = build("youtube", "v3", developerKey=api_key)
    request = youtube.playlists().list(part="snippet", id=playlist_id)
    response = request.execute()

    if not response.get("items"):
        raise ValueError(f"Playlist not found: {playlist_id}")

    item = response["items"][0]
    info = {
        "id": item["id"],
        "title": item["snippet"]["title"],
        "description": item["snippet"].get("description", ""),
        "channel_title": item["snippet"].get("channelTitle", ""),
    }

    save_to_cache(cache_key, info)
    return info


def get_video_info(video_id: str, api_key: str) -> VideoInfo:
    cache_key = f"video_info_{video_id}"
    cached = get_from_cache(cache_key)
    if cached:
        return VideoInfo(**cached)

    youtube = build("youtube", "v3", developerKey=api_key)
    request = youtube.videos().list(part="snippet,contentDetails", id=video_id)
    response = request.execute()

    if not response.get("items"):
        raise ValueError(f"Video not found: {video_id}")

    item = response["items"][0]
    snippet = item["snippet"]
    content_details = item["contentDetails"]

    video = VideoInfo(
        id=item["id"],
        title=snippet["title"],
        description=snippet.get("description", ""),
        published_at=snippet["publishedAt"],
        duration=content_details["duration"],
    )

    save_to_cache(cache_key, video.__dict__)
    return video
