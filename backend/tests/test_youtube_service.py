"""Tests for YouTube service language functionality."""

from unittest.mock import MagicMock, patch

import pytest

import app.services.youtube as youtube_module
from app.services.youtube import (
    LanguageInfo,
    TranscriptResult,
    YouTubeService,
    validate_language_codes,
)


@pytest.fixture(autouse=True)
def reset_transcript_api_cache():
    """Reset the cached transcript API instance before each test."""
    youtube_module._transcript_api = None
    yield
    youtube_module._transcript_api = None


class TestValidateLanguageCodes:
    def test_valid_codes_preserved(self):
        result = validate_language_codes(["en", "de", "fr"])
        assert result == ["en", "de", "fr"]

    def test_invalid_codes_filtered(self):
        result = validate_language_codes(["en", "invalid", "de", "xyz"])
        assert result == ["en", "de"]

    def test_codes_lowercased(self):
        result = validate_language_codes(["EN", "DE", "Fr"])
        assert result == ["en", "de", "fr"]

    def test_empty_list(self):
        result = validate_language_codes([])
        assert result == []

    def test_all_invalid(self):
        result = validate_language_codes(["invalid", "xyz", "abc"])
        assert result == []

    def test_order_preserved(self):
        result = validate_language_codes(["ja", "ko", "zh", "en"])
        assert result == ["ja", "ko", "zh", "en"]


class MockTranscript:
    def __init__(
        self,
        language_code: str,
        language: str,
        is_generated: bool,
        is_translatable: bool = True,
    ):
        self.language_code = language_code
        self.language = language
        self.is_generated = is_generated
        self.is_translatable = is_translatable


class TestScoreTranscript:
    @pytest.fixture
    def service(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
        return YouTubeService()

    def test_language_priority_scoring(self, service):
        transcript = MockTranscript("de", "German", is_generated=True)
        preferred = ["en", "de", "fr"]

        score = service._score_transcript(transcript, preferred, prefer_manual=False)

        assert score == 1000 - 1  # de is at index 1

    def test_first_language_highest_score(self, service):
        transcript = MockTranscript("en", "English", is_generated=True)
        preferred = ["en", "de", "fr"]

        score = service._score_transcript(transcript, preferred, prefer_manual=False)

        assert score == 1000  # en is at index 0

    def test_manual_transcript_bonus(self, service):
        manual = MockTranscript("en", "English", is_generated=False)
        auto = MockTranscript("en", "English", is_generated=True)
        preferred = ["en"]

        manual_score = service._score_transcript(manual, preferred, prefer_manual=True)
        auto_score = service._score_transcript(auto, preferred, prefer_manual=True)

        assert manual_score > auto_score
        assert (
            manual_score == 1000 + 100 + 10
        )  # language + prefer_manual + always_manual_bonus
        assert auto_score == 1000

    def test_manual_bonus_disabled(self, service):
        manual = MockTranscript("en", "English", is_generated=False)
        auto = MockTranscript("en", "English", is_generated=True)
        preferred = ["en"]

        manual_score = service._score_transcript(manual, preferred, prefer_manual=False)
        auto_score = service._score_transcript(auto, preferred, prefer_manual=False)

        # Still slight preference for manual (10 point tie-breaker)
        assert manual_score == 1000 + 10
        assert auto_score == 1000

    def test_unlisted_language_no_language_bonus(self, service):
        transcript = MockTranscript("pt", "Portuguese", is_generated=False)
        preferred = ["en", "de"]

        score = service._score_transcript(transcript, preferred, prefer_manual=True)

        # No language bonus, just manual bonuses
        assert score == 110


class TestSelectBestTranscript:
    @pytest.fixture
    def service(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
        return YouTubeService()

    def test_selects_preferred_language(self, service):
        transcripts = [
            MockTranscript("en", "English", is_generated=True),
            MockTranscript("de", "German", is_generated=True),
            MockTranscript("fr", "French", is_generated=True),
        ]

        best, languages = service._select_best_transcript(
            transcripts, ["de", "en"], prefer_manual=False
        )

        assert best.language_code == "de"
        assert len(languages) == 3

    def test_prefers_manual_over_auto_same_language(self, service):
        transcripts = [
            MockTranscript("en", "English", is_generated=True),
            MockTranscript("en", "English", is_generated=False),
        ]

        best, _ = service._select_best_transcript(
            transcripts, ["en"], prefer_manual=True
        )

        assert best.is_generated is False

    def test_prefers_first_language_with_manual_bonus(self, service):
        transcripts = [
            MockTranscript("en", "English (auto)", is_generated=True),
            MockTranscript("de", "German", is_generated=False),
        ]

        # With prefer_manual=True, de manual (1000-1+100+10=1109) vs en auto (1000)
        # en is first preference so gets 1000, de is second so gets 999
        # de manual: 999 + 110 = 1109
        # en auto: 1000
        best, _ = service._select_best_transcript(
            transcripts, ["en", "de"], prefer_manual=True
        )

        # German manual should win because manual bonus outweighs second position
        assert best.language_code == "de"

    def test_returns_available_languages(self, service):
        transcripts = [
            MockTranscript("en", "English", is_generated=True, is_translatable=True),
            MockTranscript("de", "German", is_generated=False, is_translatable=False),
        ]

        _, languages = service._select_best_transcript(
            transcripts, ["en"], prefer_manual=False
        )

        assert len(languages) == 2
        assert languages[0].code == "en"
        assert languages[0].is_generated is True
        assert languages[1].code == "de"
        assert languages[1].is_generated is False

    def test_empty_list(self, service):
        best, languages = service._select_best_transcript(
            [], ["en"], prefer_manual=True
        )

        assert best is None
        assert languages == []

    def test_falls_back_to_first_available(self, service):
        transcripts = [
            MockTranscript("pt", "Portuguese", is_generated=True),
            MockTranscript("it", "Italian", is_generated=True),
        ]

        best, _ = service._select_best_transcript(
            transcripts, ["en", "de"], prefer_manual=False
        )

        # Neither language in preferences, but score is 0 for both
        # Should return first available
        assert best.language_code == "pt"


class TestLanguageInfo:
    def test_dataclass_creation(self):
        lang = LanguageInfo(
            code="en", name="English", is_generated=True, is_translatable=True
        )

        assert lang.code == "en"
        assert lang.name == "English"
        assert lang.is_generated is True
        assert lang.is_translatable is True


class TestTranscriptResult:
    def test_dataclass_creation(self):
        result = TranscriptResult(
            text="Hello world",
            source="youtube",
            segments=None,
            language="English",
            language_code="en",
            is_generated=False,
            available_languages=[],
        )

        assert result.text == "Hello world"
        assert result.source == "youtube"
        assert result.language == "English"
        assert result.language_code == "en"
        assert result.is_generated is False

    def test_optional_fields(self):
        result = TranscriptResult(text="test", source="whisper", segments=None)

        assert result.language is None
        assert result.language_code is None
        assert result.is_generated is None
        assert result.available_languages is None


class TestYouTubeServiceURLParsing:
    @pytest.fixture
    def service(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
        return YouTubeService()

    def test_extract_video_id_standard_url(self, service):
        url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        assert service.extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_video_id_short_url(self, service):
        url = "https://youtu.be/dQw4w9WgXcQ"
        assert service.extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_video_id_embed_url(self, service):
        url = "https://www.youtube.com/embed/dQw4w9WgXcQ"
        assert service.extract_video_id(url) == "dQw4w9WgXcQ"

    def test_extract_video_id_invalid_url(self, service):
        url = "https://example.com/video"
        assert service.extract_video_id(url) is None

    def test_is_channel_url_handle(self, service):
        assert service.is_channel_url("https://youtube.com/@username") is True

    def test_is_channel_url_channel_id(self, service):
        assert service.is_channel_url("https://youtube.com/channel/UC123") is True

    def test_is_channel_url_custom(self, service):
        assert service.is_channel_url("https://youtube.com/c/customname") is True

    def test_is_channel_url_user(self, service):
        assert service.is_channel_url("https://youtube.com/user/username") is True

    def test_is_channel_url_video(self, service):
        assert service.is_channel_url("https://youtube.com/watch?v=abc123") is False

    def test_is_playlist_url_true(self, service):
        assert (
            service.is_playlist_url("https://youtube.com/playlist?list=PL123") is True
        )
        assert service.is_playlist_url("https://youtube.com/?list=PL123") is True

    def test_is_playlist_url_video_in_playlist(self, service):
        # Video in playlist is allowed (we extract the video)
        assert (
            service.is_playlist_url("https://youtube.com/watch?v=abc&list=PL123")
            is False
        )

    def test_is_playlist_url_regular_video(self, service):
        assert service.is_playlist_url("https://youtube.com/watch?v=abc123") is False


class TestYouTubeServiceGetVideoInfo:
    @pytest.fixture
    def service(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
        return YouTubeService()

    def test_get_video_info_success(self, service):
        mock_response = {
            "items": [
                {
                    "snippet": {
                        "title": "Test Video",
                        "channelId": "UC123",
                        "channelTitle": "Test Channel",
                        "description": "A test video",
                        "publishedAt": "2024-01-15T10:00:00Z",
                    },
                    "contentDetails": {"duration": "PT10M30S"},
                    "statistics": {"viewCount": "1000", "likeCount": "100"},
                }
            ]
        }

        mock_videos = MagicMock()
        mock_videos.list.return_value.execute.return_value = mock_response
        service.youtube.videos = MagicMock(return_value=mock_videos)

        result = service.get_video_info("test123")

        assert result is not None
        assert result["title"] == "Test Video"
        assert result["channel_id"] == "UC123"
        assert result["view_count"] == 1000

    def test_get_video_info_not_found(self, service):
        mock_response = {"items": []}

        mock_videos = MagicMock()
        mock_videos.list.return_value.execute.return_value = mock_response
        service.youtube.videos = MagicMock(return_value=mock_videos)

        result = service.get_video_info("nonexistent")

        assert result is None

    def test_get_video_info_api_error(self, service):
        mock_videos = MagicMock()
        mock_videos.list.return_value.execute.side_effect = Exception("API Error")
        service.youtube.videos = MagicMock(return_value=mock_videos)

        result = service.get_video_info("test123")

        assert result is None


class TestYouTubeServiceGetAvailableLanguages:
    @pytest.fixture
    def service(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
        return YouTubeService()

    def test_get_available_languages_success(self, service):
        mock_transcripts = [
            MockTranscript("en", "English", is_generated=False),
            MockTranscript("de", "German", is_generated=True),
        ]

        with patch("app.services.youtube.YouTubeTranscriptApi") as mock_api:
            mock_api.return_value.list.return_value = mock_transcripts
            result = service.get_available_languages("test123")

        assert len(result) == 2
        assert result[0].code == "en"
        assert result[1].code == "de"

    def test_get_available_languages_error(self, service):
        with patch("app.services.youtube.YouTubeTranscriptApi") as mock_api:
            mock_api.return_value.list.side_effect = Exception("API Error")
            result = service.get_available_languages("test123")

        assert result == []


class TestYouTubeServiceGetTranscript:
    @pytest.fixture
    def service(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
        return YouTubeService()

    def test_get_transcript_force_whisper(self, service):
        with patch("app.services.whisper.get_whisper_transcript") as mock_whisper:
            mock_whisper.return_value = ("Transcribed text", "en")
            result = service.get_transcript("test123", force_whisper=True)

        assert result is not None
        assert result.text == "Transcribed text"
        assert result.source == "whisper"
        assert result.language_code == "en"

    def test_get_transcript_force_whisper_failure(self, service):
        with patch("app.services.whisper.get_whisper_transcript") as mock_whisper:
            mock_whisper.return_value = None
            result = service.get_transcript("test123", force_whisper=True)

        assert result is None

    def test_get_transcript_force_whisper_exception(self, service):
        with patch("app.services.whisper.get_whisper_transcript") as mock_whisper:
            mock_whisper.side_effect = Exception("Whisper error")
            result = service.get_transcript("test123", force_whisper=True)

        assert result is None

    def test_get_transcript_youtube_success(self, service):
        """Test successful transcript fetch from YouTube."""

        class MockFetchedEntry:
            def __init__(self, text, start, duration):
                self.text = text
                self.start = start
                self.duration = duration

        class MockFetchedTranscript:
            def __init__(self):
                self.language = "English"
                self.language_code = "en"
                self.is_generated = False
                self.is_translatable = True

            def fetch(self):
                return [
                    MockFetchedEntry("Hello", 0.0, 1.0),
                    MockFetchedEntry("world", 1.0, 1.0),
                ]

        mock_transcript_list = [MockFetchedTranscript()]

        with patch("app.services.youtube.YouTubeTranscriptApi") as mock_api:
            mock_api.return_value.list.return_value = mock_transcript_list
            result = service.get_transcript(
                "test123",
                preferred_languages=["en"],
                prefer_manual=True,
            )

        assert result is not None
        assert result.text == "Hello world"
        assert result.source == "youtube"
        assert result.language == "English"
        assert result.language_code == "en"

    def test_get_transcript_whisper_fallback(self, service):
        """Test fallback to Whisper when YouTube has no transcripts."""
        from youtube_transcript_api import NoTranscriptFound

        with patch("app.services.youtube.YouTubeTranscriptApi") as mock_api:
            mock_api.return_value.list.side_effect = NoTranscriptFound(
                "test", ["en"], {}
            )

            with patch("app.services.whisper.get_whisper_transcript") as mock_whisper:
                mock_whisper.return_value = ("Fallback text", "en")
                result = service.get_transcript(
                    "test123",
                    use_whisper_fallback=True,
                )

        assert result is not None
        assert result.text == "Fallback text"
        assert result.source == "whisper"

    def test_get_transcript_whisper_fallback_also_fails(self, service):
        """Test when both YouTube and Whisper fail."""
        from youtube_transcript_api import TranscriptsDisabled

        with patch("app.services.youtube.YouTubeTranscriptApi") as mock_api:
            mock_api.return_value.list.side_effect = TranscriptsDisabled("test")

            with patch("app.services.whisper.get_whisper_transcript") as mock_whisper:
                mock_whisper.return_value = None
                result = service.get_transcript(
                    "test123",
                    use_whisper_fallback=True,
                )

        assert result is None

    def test_get_transcript_no_fallback(self, service):
        """Test when YouTube fails and fallback is disabled."""
        from youtube_transcript_api import NoTranscriptFound

        with patch("app.services.youtube.YouTubeTranscriptApi") as mock_api:
            mock_api.return_value.list.side_effect = NoTranscriptFound(
                "test", ["en"], {}
            )
            result = service.get_transcript(
                "test123",
                use_whisper_fallback=False,
            )

        assert result is None
