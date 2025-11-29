"""Tests for YouTube service language functionality."""

import pytest

from app.services.youtube import (
    LanguageInfo,
    TranscriptResult,
    YouTubeService,
    validate_language_codes,
)


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
