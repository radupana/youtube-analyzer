"""Tests for language endpoints."""

import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.db.database import get_session
from app.db.models import Video
from app.main import app
from app.services.youtube import LanguageInfo


@pytest.fixture
def test_client():
    engine = create_engine(
        "sqlite:///file:test_languages_db?mode=memory&cache=shared&uri=true",
        connect_args={"check_same_thread": False},
    )
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    def get_test_session():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_test_session
    client = TestClient(app)
    yield client, engine
    app.dependency_overrides.clear()
    SQLModel.metadata.drop_all(engine)
    engine.dispose()


class TestGetAvailableTranscripts:
    def test_returns_cached_languages(self, test_client):
        client, engine = test_client
        cached_languages = [
            {
                "code": "en",
                "name": "English",
                "is_generated": True,
                "is_translatable": True,
            },
            {
                "code": "de",
                "name": "German",
                "is_generated": False,
                "is_translatable": False,
            },
        ]
        with Session(engine) as db:
            video = Video(
                id="cached123",
                title="Test Video",
                channel_id="ch1",
                channel_title="Test Channel",
                duration="PT10M",
                published_at=datetime.now(UTC),
                transcript="Some transcript",
                transcript_source="youtube",
                available_languages_json=json.dumps(cached_languages),
            )
            db.add(video)
            db.commit()

        response = client.get(
            "/api/v1/languages/videos/cached123/available-transcripts"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == "cached123"
        assert data["cached"] is True
        assert len(data["languages"]) == 2
        assert data["languages"][0]["code"] == "en"
        assert data["languages"][0]["is_generated"] is True
        assert data["languages"][1]["code"] == "de"
        assert data["languages"][1]["is_generated"] is False

    def test_fetches_from_api_when_no_cache(self, test_client):
        client, _ = test_client
        mock_languages = [
            LanguageInfo(
                code="fr", name="French", is_generated=False, is_translatable=True
            ),
        ]

        with patch("app.api_v1.endpoints.languages.youtube_service") as mock_svc:
            mock_svc.get_available_languages.return_value = mock_languages
            response = client.get(
                "/api/v1/languages/videos/newvideo/available-transcripts"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == "newvideo"
        assert data["cached"] is False
        assert len(data["languages"]) == 1
        assert data["languages"][0]["code"] == "fr"

    def test_returns_404_when_no_transcripts(self, test_client):
        client, _ = test_client
        with patch("app.api_v1.endpoints.languages.youtube_service") as mock_svc:
            mock_svc.get_available_languages.return_value = []
            response = client.get(
                "/api/v1/languages/videos/novideo/available-transcripts"
            )

        assert response.status_code == 404
        assert "No transcripts available" in response.json()["detail"]

    def test_whisper_available_flag_set(self, test_client):
        client, engine = test_client
        cached_languages = [
            {
                "code": "en",
                "name": "English",
                "is_generated": True,
                "is_translatable": True,
            },
        ]
        with Session(engine) as db:
            video = Video(
                id="cached456",
                title="Test Video",
                channel_id="ch1",
                channel_title="Test Channel",
                duration="PT10M",
                published_at=datetime.now(UTC),
                transcript="Some transcript",
                transcript_source="youtube",
                available_languages_json=json.dumps(cached_languages),
            )
            db.add(video)
            db.commit()

        response = client.get(
            "/api/v1/languages/videos/cached456/available-transcripts"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["whisper_available"] is True


class TestGetTranscriptDefaults:
    def test_returns_defaults(self, test_client):
        client, _ = test_client
        response = client.get("/api/v1/languages/defaults")

        assert response.status_code == 200
        data = response.json()
        assert "preferred_languages" in data
        assert "prefer_manual" in data
        assert isinstance(data["preferred_languages"], list)
        assert isinstance(data["prefer_manual"], bool)

    def test_returns_config_values(self, test_client):
        client, _ = test_client
        from app.core import llm_config
        from app.core.llm_config import TranscriptConfig

        llm_config._transcript_config = TranscriptConfig(
            preferred_languages=["ja", "ko", "en"],
            prefer_manual=False,
        )

        response = client.get("/api/v1/languages/defaults")

        assert response.status_code == 200
        data = response.json()
        assert data["preferred_languages"] == ["ja", "ko", "en"]
        assert data["prefer_manual"] is False

        llm_config._transcript_config = TranscriptConfig()
