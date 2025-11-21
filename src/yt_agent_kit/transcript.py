"""YouTube transcript fetching and cleaning."""

import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import cast

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    IpBlocked,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from .cache import get_from_cache, save_to_cache

NOISE_PATTERNS = [
    r"\[MUSIC\]",
    r"\[APPLAUSE\]",
    r"\[LAUGHTER\]",
    r"\[INAUDIBLE\]",
    r"\[.*?\]",
]


def clean_transcript(text: str) -> str:
    """
    Clean transcript text by removing noise markers and normalizing whitespace.

    Args:
        text: Raw transcript text

    Returns:
        Cleaned transcript text
    """
    cleaned = text
    for pattern in NOISE_PATTERNS:
        cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def get_transcript(video_id: str, languages: list[str] | None = None) -> str:
    """
    Get transcript for a YouTube video.

    Args:
        video_id: YouTube video ID
        languages: Language codes to try (default: ["en"])

    Returns:
        Cleaned transcript text

    Raises:
        NoTranscriptFound: If no transcript available
        TranscriptsDisabled: If transcripts disabled for video
        VideoUnavailable: If video does not exist
    """
    if languages is None:
        languages = ["en"]

    cache_key = f"transcript_{video_id}"
    cached = get_from_cache(cache_key)
    if cached:
        return cast(str, cached)

    ytt_api = YouTubeTranscriptApi()
    transcript_list = ytt_api.list(video_id)
    transcript = transcript_list.find_transcript(languages)
    transcript_data = transcript.fetch()

    raw_text = " ".join(entry.text for entry in transcript_data)
    cleaned_text = clean_transcript(raw_text)

    save_to_cache(cache_key, cleaned_text)
    return cleaned_text


def get_transcripts_batch(
    video_ids: list[str],
    languages: list[str] | None = None,
    progress_callback: Callable[[int, int, str], None] | None = None,
    max_workers: int = 3,
    delay_seconds: float = 0.1,
) -> dict[str, str]:
    """
    Get transcripts for multiple videos with rate-limited parallel fetching.

    Args:
        video_ids: List of YouTube video IDs
        languages: Language codes to try (default: ["en"])
        progress_callback: Optional callback(current, total, video_id)
        max_workers: Number of parallel workers (default: 3, max recommended: 5)
        delay_seconds: Delay between requests to avoid rate limiting (default: 0.1s)

    Returns:
        Dictionary mapping video_id to transcript text (only successful fetches)
    """
    if languages is None:
        languages = ["en"]

    transcripts = {}
    total = len(video_ids)
    completed = 0

    def fetch_one(video_id: str) -> tuple[str, str | None]:
        """Fetch a single transcript with rate limiting."""
        time.sleep(delay_seconds)  # Rate limiting
        try:
            return (video_id, get_transcript(video_id, languages))
        except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable, IpBlocked):
            return (video_id, None)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_video = {executor.submit(fetch_one, vid): vid for vid in video_ids}

        for future in as_completed(future_to_video):
            completed += 1
            video_id, transcript = future.result()

            if progress_callback:
                progress_callback(completed, total, video_id)

            if transcript:
                transcripts[video_id] = transcript

    return transcripts
