"""Whisper service for audio transcription fallback with memory management."""

import gc
import logging
import os
import subprocess
import tempfile
import threading
import time
from typing import Any

import yt_dlp

try:
    import whisper
except ImportError:
    whisper = None

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]

try:
    from pytube import YouTube
except ImportError:
    YouTube = None

from app.core.llm_config import get_whisper_config

logger = logging.getLogger(__name__)

_model: Any = None
_model_name: str | None = None
_last_used: float = 0.0
_lock = threading.Lock()
_unload_timer: threading.Timer | None = None


def _get_model() -> Any:
    """Get or load the Whisper model."""
    global _model, _model_name, _last_used

    config = get_whisper_config()

    with _lock:
        if _model is None or _model_name != config.model:
            if whisper is None:
                raise RuntimeError(
                    "Whisper is not installed. Install with: pip install openai-whisper"
                )

            if _model is not None:
                logger.info(f"Switching model from {_model_name} to {config.model}")
                _unload_model_internal()

            logger.info(f"Loading Whisper model: {config.model}")
            _model = whisper.load_model(config.model)
            _model_name = config.model
            logger.info(f"Whisper model {config.model} loaded")

        _last_used = time.time()
        _schedule_unload()

        return _model


def _unload_model_internal() -> None:
    """Internal unload without lock (caller must hold lock)."""
    global _model, _model_name

    if _model is not None:
        logger.info(f"Unloading Whisper model: {_model_name}")
        del _model
        _model = None
        _model_name = None

        if torch is not None and torch.cuda.is_available():
            torch.cuda.empty_cache()
            logger.info("Cleared CUDA cache")

        gc.collect()
        logger.info("Whisper model unloaded")


def unload_model() -> None:
    """Unload Whisper model and free memory."""
    global _unload_timer

    with _lock:
        if _unload_timer is not None:
            _unload_timer.cancel()
            _unload_timer = None
        _unload_model_internal()


def _scheduled_unload() -> None:
    """Called by timer to unload model after timeout."""
    global _last_used

    config = get_whisper_config()

    with _lock:
        if _model is not None:
            idle_time = time.time() - _last_used
            if idle_time >= config.unload_timeout:
                logger.info(f"Auto-unloading Whisper model after {idle_time:.0f}s idle")
                _unload_model_internal()
            else:
                _schedule_unload()


def _schedule_unload() -> None:
    """Schedule model unload after timeout (caller must hold lock)."""
    global _unload_timer

    config = get_whisper_config()

    if _unload_timer is not None:
        _unload_timer.cancel()
        _unload_timer = None

    if config.unload_timeout > 0 and _model is not None:
        _unload_timer = threading.Timer(config.unload_timeout, _scheduled_unload)
        _unload_timer.daemon = True
        _unload_timer.start()


def is_model_loaded() -> bool:
    """Check if Whisper model is currently loaded."""
    return _model is not None


def get_model_info() -> dict[str, Any]:
    """Get current model status for health endpoint."""
    return {
        "loaded": _model is not None,
        "model_name": _model_name,
        "last_used": _last_used if _last_used > 0 else None,
        "idle_seconds": int(time.time() - _last_used) if _last_used > 0 else None,
    }


def _transcribe_audio(audio_path: str) -> str | None:
    """Transcribe audio using Whisper."""
    try:
        model = _get_model()
        logger.info(f"Transcribing audio: {audio_path}")

        result = model.transcribe(
            audio_path,
            language="en",
            task="transcribe",
            verbose=False,
            fp16=False,
        )

        return result.get("text", "").strip()

    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        return None


def _download_with_ytdlp(video_id: str, temp_dir: str) -> str | None:
    """Try downloading with yt-dlp."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    audio_path = os.path.join(temp_dir, f"{video_id}.mp3")

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(temp_dir, f"{video_id}.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192",
            }
        ],
        "user-agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "referer": "https://www.youtube.com/",
        "extractor-args": "youtube:player_client=android,web_creator,ios",
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Sec-Fetch-Mode": "navigate",
        },
        "geo_bypass": True,
        "nocheckcertificate": True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        if os.path.exists(audio_path):
            return audio_path
    except Exception as e:
        logger.warning(f"yt-dlp failed: {e}")
    return None


def _download_with_pytube(video_id: str, temp_dir: str) -> str | None:
    """Try downloading with pytube as fallback."""
    if YouTube is None:
        return None

    try:
        url = f"https://www.youtube.com/watch?v={video_id}"
        audio_path = os.path.join(temp_dir, f"{video_id}.mp3")

        yt = YouTube(url, use_oauth=False, allow_oauth_cache=False)
        audio_stream = yt.streams.filter(only_audio=True).first()

        if audio_stream:
            temp_file = audio_stream.download(
                output_path=temp_dir, filename=f"{video_id}.mp4"
            )
            subprocess.run(
                [
                    "ffmpeg",
                    "-i",
                    temp_file,
                    "-vn",
                    "-ar",
                    "44100",
                    "-ac",
                    "2",
                    "-b:a",
                    "192k",
                    audio_path,
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            os.remove(temp_file)

            if os.path.exists(audio_path):
                logger.info(f"Downloaded with pytube for {video_id}")
                return audio_path
    except Exception as e:
        logger.warning(f"pytube failed: {e}")
    return None


def _download_with_ytdlp_update(video_id: str, temp_dir: str) -> str | None:
    """Try updating yt-dlp and downloading again."""
    try:
        logger.info("Updating yt-dlp to latest version...")
        subprocess.run(
            ["pip", "install", "-U", "yt-dlp"], capture_output=True, text=True
        )
        return _download_with_ytdlp(video_id, temp_dir)
    except Exception as e:
        logger.warning(f"yt-dlp update and retry failed: {e}")
    return None


def get_whisper_transcript(video_id: str, progress_callback: Any = None) -> str | None:
    """Get transcript using Whisper (download audio + transcribe)."""
    try:
        logger.info(f"Using Whisper fallback for video {video_id}")

        if progress_callback:
            progress_callback("whisper_downloading", "Starting audio download...")

        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = None

            logger.info(f"Attempting to download audio for {video_id}...")

            if progress_callback:
                progress_callback("whisper_downloading", "Downloading audio...")
            audio_path = _download_with_ytdlp(video_id, temp_dir)

            if not audio_path:
                logger.info("Trying pytube fallback...")
                if progress_callback:
                    progress_callback("whisper_downloading", "Retrying download...")
                audio_path = _download_with_pytube(video_id, temp_dir)

            if not audio_path:
                logger.info("Trying yt-dlp update and retry...")
                if progress_callback:
                    progress_callback("whisper_downloading", "Retrying download...")
                audio_path = _download_with_ytdlp_update(video_id, temp_dir)

            if not audio_path:
                logger.error(f"All download methods failed for {video_id}")
                return None

            if progress_callback:
                progress_callback("whisper_downloading", "Audio downloaded")

            if progress_callback:
                if is_model_loaded():
                    progress_callback("whisper_loading", "Whisper model ready")
                else:
                    progress_callback(
                        "whisper_loading",
                        "Loading speech recognition model...",
                    )

            duration_msg = ""
            try:
                result = subprocess.run(
                    [
                        "ffprobe",
                        "-v",
                        "error",
                        "-show_entries",
                        "format=duration",
                        "-of",
                        "default=noprint_wrappers=1:nokey=1",
                        audio_path,
                    ],
                    capture_output=True,
                    text=True,
                )
                audio_duration = float(result.stdout.strip()) if result.stdout else 0
                if audio_duration > 0:
                    duration_msg = f" (~{int(audio_duration)}s audio)"
            except Exception:
                pass

            if progress_callback:
                progress_callback(
                    "whisper_transcribing",
                    f"Transcribing audio{duration_msg}...",
                )

            config = get_whisper_config()
            logger.info(f"Transcribing with Whisper model {config.model}...")
            transcript = _transcribe_audio(audio_path)

            if transcript:
                logger.info(f"Successfully transcribed {video_id} with Whisper")
                if progress_callback:
                    progress_callback("whisper_complete", "Transcription complete")

            return transcript

    except Exception as e:
        logger.error(f"Error in Whisper transcription for {video_id}: {e}")
        return None
