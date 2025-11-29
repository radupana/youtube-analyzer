"""YouTube API service for fetching video metadata and transcripts."""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled

from app.core.config import get_settings
from app.core.llm_config import get_transcript_config, get_whisper_config
from app.services.chunking import TranscriptSegment

logger = logging.getLogger(__name__)

VALID_LANGUAGE_CODES = {
    "en",
    "de",
    "fr",
    "es",
    "pt",
    "it",
    "nl",
    "pl",
    "ru",
    "uk",
    "ja",
    "ko",
    "zh",
    "ar",
    "hi",
    "bn",
    "pa",
    "ta",
    "te",
    "mr",
    "tr",
    "vi",
    "th",
    "id",
    "ms",
    "tl",
    "sv",
    "no",
    "da",
    "fi",
    "cs",
    "sk",
    "hu",
    "ro",
    "bg",
    "el",
    "he",
    "fa",
    "ur",
    "sw",
}

# Language code to name mapping for Whisper results
LANGUAGE_NAMES = {
    "en": "English",
    "de": "German",
    "fr": "French",
    "es": "Spanish",
    "pt": "Portuguese",
    "it": "Italian",
    "nl": "Dutch",
    "pl": "Polish",
    "ru": "Russian",
    "uk": "Ukrainian",
    "ja": "Japanese",
    "ko": "Korean",
    "zh": "Chinese",
    "ar": "Arabic",
    "hi": "Hindi",
    "bn": "Bengali",
    "pa": "Punjabi",
    "ta": "Tamil",
    "te": "Telugu",
    "mr": "Marathi",
    "tr": "Turkish",
    "vi": "Vietnamese",
    "th": "Thai",
    "id": "Indonesian",
    "ms": "Malay",
    "tl": "Tagalog",
    "sv": "Swedish",
    "no": "Norwegian",
    "da": "Danish",
    "fi": "Finnish",
    "cs": "Czech",
    "sk": "Slovak",
    "hu": "Hungarian",
    "ro": "Romanian",
    "bg": "Bulgarian",
    "el": "Greek",
    "he": "Hebrew",
    "fa": "Persian",
    "ur": "Urdu",
    "sw": "Swahili",
}


def validate_language_codes(codes: list[str]) -> list[str]:
    """Filter to only valid language codes, preserving order."""
    return [c.lower() for c in codes if c.lower() in VALID_LANGUAGE_CODES]


@dataclass
class LanguageInfo:
    code: str
    name: str
    is_generated: bool
    is_translatable: bool


@dataclass
class TranscriptResult:
    text: str
    source: str
    segments: list[TranscriptSegment] | None
    language: str | None = None
    language_code: str | None = None
    is_generated: bool | None = None
    available_languages: list[LanguageInfo] | None = None


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
            r"/@[^/\s]+",
            r"/channel/[^/]+",
            r"/c/[^/]+",
            r"/user/[^/]+",
        ]
        return any(re.search(pattern, url) for pattern in channel_patterns)

    def is_playlist_url(self, url: str) -> bool:
        """Check if URL is a playlist-only URL (not supported)."""
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

    def _score_transcript(
        self,
        transcript: Any,
        preferred_languages: list[str],
        prefer_manual: bool,
    ) -> int:
        """Score a transcript for selection. Higher is better."""
        score = 0
        lang_code = transcript.language_code.lower()

        if lang_code in preferred_languages:
            score += 1000 - preferred_languages.index(lang_code)

        if not transcript.is_generated and prefer_manual:
            score += 100

        if not transcript.is_generated:
            score += 10

        return score

    def _select_best_transcript(
        self,
        transcript_list: Any,
        preferred_languages: list[str],
        prefer_manual: bool,
    ) -> tuple[Any | None, list[LanguageInfo]]:
        """Select best transcript and return available languages."""
        available = list(transcript_list)

        if not available:
            return None, []

        available_languages = [
            LanguageInfo(
                code=t.language_code,
                name=t.language,
                is_generated=t.is_generated,
                is_translatable=t.is_translatable,
            )
            for t in available
        ]

        preferred_lower = [lang.lower() for lang in preferred_languages]

        scored = [
            (self._score_transcript(t, preferred_lower, prefer_manual), t)
            for t in available
        ]
        scored.sort(key=lambda x: x[0], reverse=True)

        best_transcript = scored[0][1] if scored[0][0] > 0 else available[0]
        return best_transcript, available_languages

    def get_available_languages(self, video_id: str) -> list[LanguageInfo]:
        """Get list of available transcript languages for a video."""
        try:
            ytt_api = YouTubeTranscriptApi()
            transcript_list = ytt_api.list(video_id)

            return [
                LanguageInfo(
                    code=t.language_code,
                    name=t.language,
                    is_generated=t.is_generated,
                    is_translatable=t.is_translatable,
                )
                for t in transcript_list
            ]
        except Exception as e:
            logger.error(f"Failed to list languages for {video_id}: {e}")
            return []

    def get_transcript(
        self,
        video_id: str,
        preferred_languages: list[str] | None = None,
        prefer_manual: bool | None = None,
        use_whisper_fallback: bool | None = None,
        force_whisper: bool = False,
        progress_callback: Any = None,
    ) -> TranscriptResult | None:
        """Get transcript for a video with language preferences.

        Args:
            video_id: YouTube video ID
            preferred_languages: Language codes in priority order
            prefer_manual: Prefer manual transcripts over auto-generated
            use_whisper_fallback: Use Whisper if no YouTube captions
            force_whisper: Skip YouTube API and use Whisper directly
            progress_callback: Callback for Whisper progress updates
        """
        # If force_whisper is True, skip YouTube API entirely
        if force_whisper:
            try:
                from app.services.whisper import get_whisper_transcript

                logger.info(f"Forcing Whisper for {video_id}")
                whisper_result = get_whisper_transcript(video_id, progress_callback)
                if whisper_result:
                    whisper_text, detected_lang = whisper_result
                    # Map language code to language name
                    lang_name = LANGUAGE_NAMES.get(detected_lang, detected_lang.upper())
                    return TranscriptResult(
                        text=whisper_text,
                        source="whisper",
                        segments=None,
                        language=lang_name,
                        language_code=detected_lang,
                        is_generated=True,
                        available_languages=None,
                    )
            except Exception as e:
                logger.error(f"Whisper transcription failed for {video_id}: {e}")
            return None

        config = get_transcript_config()
        if preferred_languages is None:
            preferred_languages = list(config.preferred_languages)
        if prefer_manual is None:
            prefer_manual = config.prefer_manual

        preferred_languages = validate_language_codes(preferred_languages) or ["en"]

        try:
            logger.info(
                f"Fetching transcript for {video_id}, languages={preferred_languages}"
            )
            ytt_api = YouTubeTranscriptApi()
            transcript_list = ytt_api.list(video_id)

            transcript, available_languages = self._select_best_transcript(
                transcript_list, preferred_languages, prefer_manual
            )

            if transcript:
                fetched = transcript.fetch()
                segments = [
                    TranscriptSegment(
                        text=entry.text, start=entry.start, duration=entry.duration
                    )
                    for entry in fetched
                ]
                text = " ".join(seg.text for seg in segments)

                logger.info(
                    f"Selected transcript: {transcript.language} "
                    f"({transcript.language_code}), "
                    f"is_generated={transcript.is_generated}"
                )

                return TranscriptResult(
                    text=text,
                    source="youtube",
                    segments=segments,
                    language=transcript.language,
                    language_code=transcript.language_code,
                    is_generated=transcript.is_generated,
                    available_languages=available_languages,
                )

            logger.warning(f"No transcript found for {video_id}")

        except TranscriptsDisabled:
            logger.warning(f"Transcripts disabled for {video_id}")
        except NoTranscriptFound:
            logger.warning(f"No transcripts found for {video_id}")
        except Exception as e:
            logger.error(f"Error fetching transcript for {video_id}: {e}")

        if use_whisper_fallback is None:
            use_whisper_fallback = get_whisper_config().fallback_enabled

        if use_whisper_fallback:
            try:
                from app.services.whisper import get_whisper_transcript

                logger.info(f"Falling back to Whisper for {video_id}")
                whisper_result = get_whisper_transcript(video_id, progress_callback)
                if whisper_result:
                    whisper_text, detected_lang = whisper_result
                    lang_name = LANGUAGE_NAMES.get(detected_lang, detected_lang.upper())
                    return TranscriptResult(
                        text=whisper_text,
                        source="whisper",
                        segments=None,
                        language=lang_name,
                        language_code=detected_lang,
                        is_generated=True,
                        available_languages=[],
                    )
            except Exception as whisper_error:
                logger.error(f"Whisper fallback failed for {video_id}: {whisper_error}")

        return None
