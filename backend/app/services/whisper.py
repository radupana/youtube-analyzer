"""Whisper service for audio transcription fallback."""

import logging
import os
import subprocess
import tempfile

import whisper
import yt_dlp
import yt_dlp.utils

try:
    from pytube import YouTube
except ImportError:
    YouTube = None

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class WhisperService:
    def __init__(self):
        self.settings = get_settings()
        self.model = None
        self.model_name = self.settings.whisper_model

    def _load_model(self):
        """Lazy load Whisper model."""
        if self.model is None:
            logger.info(f"Loading Whisper model: {self.model_name}")
            self.model = whisper.load_model(self.model_name)
            logger.info("Whisper model loaded successfully")

    def download_audio(self, video_id: str) -> str | None:
        """Download audio from YouTube video."""
        try:
            url = f"https://www.youtube.com/watch?v={video_id}"

            # Create temp directory for audio
            with tempfile.TemporaryDirectory() as temp_dir:
                output_path = os.path.join(temp_dir, f"{video_id}.%(ext)s")

                ydl_opts = {
                    "format": "bestaudio/best",
                    "outtmpl": output_path,
                    "quiet": True,
                    "no_warnings": True,
                    "postprocessors": [
                        {
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }
                    ],
                }

                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                # Find the downloaded file
                audio_file = os.path.join(temp_dir, f"{video_id}.mp3")
                if os.path.exists(audio_file):
                    # Read the file and return path for processing
                    return audio_file

        except Exception as e:
            logger.error(f"Error downloading audio for {video_id}: {e}")
            return None

    def transcribe_audio(self, audio_path: str, progress_callback=None) -> str | None:
        """Transcribe audio using Whisper with progress tracking."""
        try:
            self._load_model()

            logger.info(f"Transcribing audio: {audio_path}")

            # Create a progress callback wrapper
            def whisper_progress_callback(progress):
                if progress_callback:
                    # Whisper progress is in segments, estimate percentage
                    progress_callback(
                        {
                            "step": "transcribing",
                            "progress": min(
                                progress * 100, 99
                            ),  # Cap at 99% until done
                            "message": f"Transcribing audio... {int(progress * 100)}%",
                        }
                    )

            # Use verbose=True to get progress updates
            result = self.model.transcribe(
                audio_path,
                language="en",
                task="transcribe",
                verbose=True,  # This will show progress
                fp16=False,  # Disable FP16 to avoid warning
            )

            return result.get("text", "").strip()

        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return None

    def download_with_ytdlp(self, video_id: str, temp_dir: str) -> str | None:
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
            # Aggressive options to bypass YouTube blocks
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "referer": "https://www.youtube.com/",
            "extractor-args": "youtube:player_client=android,web_creator,ios",
            "http_headers": {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
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

    def download_with_pytube(self, video_id: str, temp_dir: str) -> str | None:
        """Try downloading with pytube as fallback."""
        if YouTube is None:
            return None

        try:
            url = f"https://www.youtube.com/watch?v={video_id}"
            audio_path = os.path.join(temp_dir, f"{video_id}.mp3")

            yt = YouTube(url, use_oauth=False, allow_oauth_cache=False)
            audio_stream = yt.streams.filter(only_audio=True).first()

            if audio_stream:
                # Download as mp4 first
                temp_file = audio_stream.download(
                    output_path=temp_dir, filename=f"{video_id}.mp4"
                )
                # Convert to mp3 using ffmpeg
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
                    logger.info(f"Successfully downloaded with pytube for {video_id}")
                    return audio_path
        except Exception as e:
            logger.warning(f"pytube failed: {e}")
        return None

    def download_with_ytdlp_update(self, video_id: str, temp_dir: str) -> str | None:
        """Try updating yt-dlp and downloading again."""
        try:
            # Update yt-dlp first
            logger.info("Updating yt-dlp to latest version...")
            subprocess.run(
                ["pip", "install", "-U", "yt-dlp"], capture_output=True, text=True
            )

            # Try download again with updated version
            return self.download_with_ytdlp(video_id, temp_dir)
        except Exception as e:
            logger.warning(f"yt-dlp update and retry failed: {e}")
        return None

    def get_whisper_transcript(
        self, video_id: str, progress_callback=None
    ) -> str | None:
        """Get transcript using Whisper (download audio + transcribe)."""
        try:
            logger.info(f"Using Whisper fallback for video {video_id}")

            if progress_callback:
                progress_callback("whisper_downloading", "Starting audio download...")

            # Create a temporary directory that persists through the function
            with tempfile.TemporaryDirectory() as temp_dir:
                audio_path = None

                # Try multiple download methods in order
                logger.info(f"Attempting to download audio for {video_id}...")

                # Method 1: yt-dlp with Android client
                if progress_callback:
                    progress_callback(
                        "whisper_downloading", "⬇️ Downloading audio (method 1/3)..."
                    )
                audio_path = self.download_with_ytdlp(video_id, temp_dir)

                # Method 2: pytube as fallback
                if not audio_path:
                    logger.info("Trying pytube fallback...")
                    if progress_callback:
                        progress_callback(
                            "whisper_downloading",
                            "⬇️ Trying alternative download (method 2/3)...",
                        )
                    audio_path = self.download_with_pytube(video_id, temp_dir)

                # Method 3: Update yt-dlp and try again
                if not audio_path:
                    logger.info("Trying yt-dlp update and retry...")
                    if progress_callback:
                        progress_callback(
                            "whisper_downloading",
                            "⬇️ Updating downloader (method 3/3)...",
                        )
                    audio_path = self.download_with_ytdlp_update(video_id, temp_dir)

                if not audio_path:
                    logger.error(f"All download methods failed for {video_id}")
                    return None

                if progress_callback:
                    progress_callback(
                        "whisper_downloading", "✅ Audio downloaded successfully"
                    )

                # Loading model
                if progress_callback:
                    if self.model:
                        progress_callback(
                            "whisper_loading", "📦 Whisper model already loaded"
                        )
                    else:
                        progress_callback(
                            "whisper_loading",
                            f"📦 Loading Whisper {self.model_name} model (first time ~15s)...",
                        )

                # Ensure model is loaded
                if not self.model:
                    self._load_model()

                # Get audio duration for progress estimation
                try:
                    import subprocess

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
                    audio_duration = (
                        float(result.stdout.strip()) if result.stdout else 0
                    )
                    duration_msg = (
                        f" (~{int(audio_duration)}s audio)"
                        if audio_duration > 0
                        else ""
                    )
                except Exception:
                    duration_msg = ""

                # Transcribe audio
                if progress_callback:
                    progress_callback(
                        "whisper_transcribing",
                        f"🎤 Transcribing{duration_msg} (typically 10-30s)...",
                    )

                logger.info(f"Transcribing with Whisper model {self.model_name}...")
                transcript = self.transcribe_audio(audio_path, progress_callback)

                if transcript:
                    logger.info(f"Successfully transcribed {video_id} with Whisper")
                    if progress_callback:
                        progress_callback(
                            "whisper_complete", "✅ Transcription complete!"
                        )

                return transcript

        except Exception as e:
            logger.error(f"Error in Whisper transcription for {video_id}: {e}")
            return None
