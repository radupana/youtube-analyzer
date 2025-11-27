import pytest
from pydantic import ValidationError

from app.core.config import Settings


class TestSettings:
    def test_settings_with_required_fields(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_API_KEY", "test-youtube-key")
        settings = Settings()
        assert settings.youtube_api_key == "test-youtube-key"

    def test_missing_youtube_api_key_raises(self, monkeypatch):
        monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
        with pytest.raises(ValidationError):
            Settings()

    def test_default_cors_origins(self, monkeypatch):
        monkeypatch.setenv("YOUTUBE_API_KEY", "test")
        settings = Settings()
        assert "http://localhost:3000" in settings.cors_origins
        assert "http://127.0.0.1:3000" in settings.cors_origins
