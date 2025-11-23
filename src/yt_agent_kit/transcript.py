"""YouTube transcript fetching and cleaning with Whisper fallback."""

import logging
import re
import tempfile
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from functools import lru_cache
from pathlib import Path
from typing import Any, cast

import whisper
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import (
    IpBlocked,
    NoTranscriptFound,
    TranscriptsDisabled,
    VideoUnavailable,
)

from .cache import get_from_cache, save_to_cache

logger = logging.getLogger(__name__)

NOISE_PATTERNS = [
    r"\[MUSIC\]",
    r"\[APPLAUSE\]",
    r"\[LAUGHTER\]",
    r"\[INAUDIBLE\]",
    r"\[.*?\]",
]


VALID_VIDEO_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{11}$")


class WhisperModelLoadError(Exception):
    """Raised when Whisper model fails to load."""

    pass


@lru_cache(maxsize=4)
def _get_whisper_model(model_name: str) -> Any:
    """Get or load a Whisper model, caching it for reuse.

    Uses lru_cache for thread-safe caching of expensive model loads.

    Raises:
        WhisperModelLoadError: If model loading fails (invalid name, OOM, etc.)
    """
    try:
        return whisper.load_model(model_name)
    except Exception as e:
        raise WhisperModelLoadError(
            f"Failed to load Whisper model '{model_name}': {e}. "
            f"Valid models: tiny, base, small, medium, large, turbo"
        ) from e


def download_audio(video_id: str, output_dir: Path) -> Path:
    """
    Download audio from a YouTube video using yt-dlp.

    Args:
        video_id: YouTube video ID
        output_dir: Directory to save the audio file

    Returns:
        Path to the downloaded audio file

    Raises:
        ValueError: If video_id format is invalid
        yt_dlp.utils.DownloadError: If download fails
    """
    if not VALID_VIDEO_ID_PATTERN.match(video_id):
        raise ValueError(f"Invalid YouTube video ID format: {video_id}")

    url = f"https://www.youtube.com/watch?v={video_id}"
    output_template = str(output_dir / f"{video_id}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio/best",
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "outtmpl": output_template,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.download([url])

    return output_dir / f"{video_id}.mp3"


class WhisperTranscriptionError(Exception):
    """Raised when Whisper fails to transcribe audio."""

    pass


MIN_AUDIO_SIZE_BYTES = 10000  # ~10KB minimum for valid audio


def transcribe_audio(audio_path: Path, model_name: str = "base") -> str:
    """
    Transcribe audio file using Whisper.

    Args:
        audio_path: Path to audio file
        model_name: Whisper model to use (tiny, base, small, medium, large, turbo)

    Returns:
        Transcribed text

    Raises:
        WhisperTranscriptionError: If audio is too short/empty or transcription fails
    """
    if not audio_path.exists():
        raise WhisperTranscriptionError(f"Audio file not found: {audio_path}")

    file_size = audio_path.stat().st_size
    if file_size < MIN_AUDIO_SIZE_BYTES:
        raise WhisperTranscriptionError(
            f"Audio file too small ({file_size} bytes) - likely empty or corrupt"
        )

    model = _get_whisper_model(model_name)
    try:
        result = model.transcribe(str(audio_path))
    except RuntimeError as e:
        # Whisper crashes on very short/empty audio with tensor reshape errors
        raise WhisperTranscriptionError(f"Whisper failed: {e}") from e

    text = result.get("text", "")
    if not text or not text.strip():
        raise WhisperTranscriptionError("Whisper produced empty transcript")

    return cast(str, text)


def get_transcript_with_whisper_fallback(
    video_id: str,
    languages: list[str] | None = None,
    fallback_enabled: bool = True,
    whisper_model: str = "base",
    cleanup_audio: bool = True,
    progress_callback: Callable[[str], None] | None = None,
) -> str:
    """
    Get transcript for a YouTube video with Whisper fallback.

    Tries YouTube captions first. If unavailable and fallback is enabled,
    downloads audio and transcribes with Whisper.

    Args:
        video_id: YouTube video ID
        languages: Language codes to try for YouTube captions (default: ["en"])
        fallback_enabled: Whether to use Whisper fallback
        whisper_model: Whisper model to use for fallback
        cleanup_audio: Whether to delete audio after transcription
        progress_callback: Optional callback to report progress status

    Returns:
        Cleaned transcript text

    Raises:
        NoTranscriptFound: If no transcript available and fallback disabled/failed
        TranscriptsDisabled: If transcripts disabled and fallback disabled/failed
        VideoUnavailable: If video does not exist
    """
    if languages is None:
        languages = ["en"]

    cache_key = f"transcript_{video_id}"
    cached = get_from_cache(cache_key)
    if cached:
        return cast(str, cached)

    youtube_error: Exception | None = None

    try:
        if progress_callback:
            progress_callback("fetching YouTube captions")
        ytt_api = YouTubeTranscriptApi()
        transcript_list = ytt_api.list(video_id)
        transcript = transcript_list.find_transcript(languages)
        transcript_data = transcript.fetch()

        raw_text = " ".join(entry.text for entry in transcript_data)
        cleaned_text = clean_transcript(raw_text)

        save_to_cache(cache_key, cleaned_text)
        return cleaned_text

    except (NoTranscriptFound, TranscriptsDisabled, IpBlocked) as e:
        youtube_error = e
        if not fallback_enabled:
            raise

    if progress_callback:
        progress_callback("downloading audio for Whisper")

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_path = Path(tmp_dir)

        try:
            audio_path = download_audio(video_id, tmp_path)
        except Exception as e:
            if youtube_error:
                raise youtube_error from e
            raise

        if progress_callback:
            progress_callback(f"transcribing with Whisper ({whisper_model})")

        try:
            raw_text = transcribe_audio(audio_path, whisper_model)
        except Exception as e:
            logger.warning(
                "Whisper transcription failed for %s: %s: %s",
                video_id,
                type(e).__name__,
                e,
            )
            if youtube_error:
                raise youtube_error from e
            raise

        cleaned_text = clean_transcript(raw_text)

        if cleanup_audio and audio_path.exists():
            audio_path.unlink()

        save_to_cache(cache_key, cleaned_text)
        return cleaned_text


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
        except IpBlocked:
            logger.warning(
                "IP blocked by YouTube for video %s - consider using Whisper fallback",
                video_id,
            )
            return (video_id, None)
        except (NoTranscriptFound, TranscriptsDisabled, VideoUnavailable):
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


def get_transcripts_batch_with_fallback(
    video_ids: list[str],
    languages: list[str] | None = None,
    progress_callback: Callable[[int, int, str, str], None] | None = None,
    fallback_enabled: bool = True,
    whisper_model: str = "base",
    cleanup_audio: bool = True,
    max_workers: int = 3,
    delay_seconds: float = 0.1,
) -> dict[str, str]:
    """
    Get transcripts for multiple videos with Whisper fallback support.

    Args:
        video_ids: List of YouTube video IDs
        languages: Language codes to try (default: ["en"])
        progress_callback: Optional callback(current, total, video_id, status)
        fallback_enabled: Whether to use Whisper fallback
        whisper_model: Whisper model to use for fallback
        cleanup_audio: Whether to delete audio after transcription
        max_workers: Number of parallel workers (default: 3)
        delay_seconds: Delay between requests to avoid rate limiting

    Returns:
        Dictionary mapping video_id to transcript text (only successful fetches)
    """
    if languages is None:
        languages = ["en"]

    transcripts: dict[str, str] = {}
    total = len(video_ids)
    completed = 0

    def fetch_one(video_id: str) -> tuple[str, str | None, str]:
        """Fetch a single transcript with fallback."""
        time.sleep(delay_seconds)
        status = "success"

        # Create inner progress callback that updates the batch callback
        def inner_progress(step_status: str) -> None:
            nonlocal status
            status = step_status

        try:
            transcript = get_transcript_with_whisper_fallback(
                video_id=video_id,
                languages=languages,
                fallback_enabled=fallback_enabled,
                whisper_model=whisper_model,
                cleanup_audio=cleanup_audio,
                progress_callback=inner_progress if progress_callback else None,
            )
            status = "success"  # Reset to success after completion
            return (video_id, transcript, status)
        except (
            NoTranscriptFound,
            TranscriptsDisabled,
            VideoUnavailable,
            IpBlocked,
        ) as e:
            logger.warning(
                "Transcript failed for %s: %s: %s", video_id, type(e).__name__, e
            )
            return (video_id, None, "failed")
        except Exception as e:
            logger.error(
                "Unexpected error for %s: %s: %s",
                video_id,
                type(e).__name__,
                e,
                exc_info=True,
            )
            return (video_id, None, "error")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_video = {executor.submit(fetch_one, vid): vid for vid in video_ids}

        for future in as_completed(future_to_video):
            completed += 1
            video_id, transcript, status = future.result()

            if progress_callback:
                progress_callback(completed, total, video_id, status)

            if transcript:
                transcripts[video_id] = transcript

    return transcripts
