"""Integration tests for analysis endpoint."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.db.database import get_session
from app.db.models import Video, VideoAnalysis
from app.main import app
from app.services.analysis import AnalysisOutput


@pytest.fixture
def test_client():
    engine = create_engine(
        "sqlite:///file:test_analysis?mode=memory&cache=shared",
        connect_args={"check_same_thread": False, "uri": True},
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


def create_video_with_transcript(engine) -> Video:
    with Session(engine) as session:
        video = Video(
            id="test-video-123",
            title="Test Video Title",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT15M30S",
            published_at=datetime.now(UTC),
            transcript="This is a test transcript about Python programming and AI.",
            transcript_source="youtube",
        )
        session.add(video)
        session.commit()
        session.refresh(video)
        return video


def create_video_without_transcript(engine) -> Video:
    with Session(engine) as session:
        video = Video(
            id="no-transcript-456",
            title="Video Without Transcript",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT5M",
            published_at=datetime.now(UTC),
            transcript=None,
        )
        session.add(video)
        session.commit()
        session.refresh(video)
        return video


def create_cached_analysis(engine, video_id: str) -> VideoAnalysis:
    with Session(engine) as session:
        analysis = VideoAnalysis(
            video_id=video_id,
            summary="Cached summary about Python.",
            key_takeaways='["Learn Python", "Practice daily"]',
            main_topics='["Python", "Programming"]',
            notable_quotes='["Code is poetry"]',
            model_used="gemini/gemini-2.5-flash",
        )
        session.add(analysis)
        session.commit()
        session.refresh(analysis)
        return analysis


class TestAnalyzeVideo:
    def test_analyze_video_success(self, test_client):
        client, engine = test_client
        video = create_video_with_transcript(engine)

        mock_output = AnalysisOutput(
            summary="Generated summary",
            key_takeaways=["Point 1", "Point 2"],
            main_topics=["Topic A"],
            notable_quotes=["Quote 1"],
        )

        with patch("app.api_v1.endpoints.analysis.get_current_provider") as mock_prov:
            mock_prov.return_value = MagicMock(model="gemini/gemini-2.5-flash")
            with patch(
                "app.api_v1.endpoints.analysis.generate_analysis",
                new_callable=AsyncMock,
                return_value=mock_output,
            ):
                response = client.post(f"/api/v1/videos/{video.id}/analyze")

        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == video.id
        assert data["summary"] == "Generated summary"
        assert data["key_takeaways"] == ["Point 1", "Point 2"]
        assert data["cached"] is False

    def test_analyze_video_returns_cached(self, test_client):
        client, engine = test_client
        video = create_video_with_transcript(engine)
        create_cached_analysis(engine, video.id)

        response = client.post(f"/api/v1/videos/{video.id}/analyze")

        assert response.status_code == 200
        data = response.json()
        assert data["summary"] == "Cached summary about Python."
        assert data["cached"] is True

    def test_analyze_video_force_regenerate(self, test_client):
        client, engine = test_client
        video = create_video_with_transcript(engine)
        create_cached_analysis(engine, video.id)

        mock_output = AnalysisOutput(
            summary="New summary",
            key_takeaways=["New point"],
            main_topics=["New topic"],
            notable_quotes=[],
        )

        with patch("app.api_v1.endpoints.analysis.get_current_provider") as mock_prov:
            mock_prov.return_value = MagicMock(model="gemini/gemini-2.5-flash")
            with patch(
                "app.api_v1.endpoints.analysis.generate_analysis",
                new_callable=AsyncMock,
                return_value=mock_output,
            ):
                response = client.post(
                    f"/api/v1/videos/{video.id}/analyze",
                    json={"force_regenerate": True},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["summary"] == "New summary"
        assert data["cached"] is False

    def test_analyze_video_not_found(self, test_client):
        client, _ = test_client
        response = client.post("/api/v1/videos/nonexistent/analyze")

        assert response.status_code == 404
        assert "Video not found" in response.json()["detail"]

    def test_analyze_video_no_transcript(self, test_client):
        client, engine = test_client
        video = create_video_without_transcript(engine)

        response = client.post(f"/api/v1/videos/{video.id}/analyze")

        assert response.status_code == 400
        assert "without transcript" in response.json()["detail"]


class TestGetAnalysis:
    def test_get_cached_analysis(self, test_client):
        client, engine = test_client
        video = create_video_with_transcript(engine)
        create_cached_analysis(engine, video.id)

        response = client.get(f"/api/v1/videos/{video.id}/analysis")

        assert response.status_code == 200
        data = response.json()
        assert data["summary"] == "Cached summary about Python."
        assert data["cached"] is True

    def test_get_analysis_not_found(self, test_client):
        client, engine = test_client
        video = create_video_with_transcript(engine)

        response = client.get(f"/api/v1/videos/{video.id}/analysis")

        assert response.status_code == 404
        assert "No analysis found" in response.json()["detail"]

    def test_get_analysis_video_not_found(self, test_client):
        client, _ = test_client
        response = client.get("/api/v1/videos/nonexistent/analysis")

        assert response.status_code == 404
        assert "Video not found" in response.json()["detail"]


class TestDeleteAnalysis:
    def test_delete_analysis(self, test_client):
        client, engine = test_client
        video = create_video_with_transcript(engine)
        create_cached_analysis(engine, video.id)

        response = client.delete(f"/api/v1/videos/{video.id}/analysis")

        assert response.status_code == 200
        assert response.json()["success"] is True

        get_response = client.get(f"/api/v1/videos/{video.id}/analysis")
        assert get_response.status_code == 404

    def test_delete_analysis_not_found(self, test_client):
        client, engine = test_client
        video = create_video_with_transcript(engine)

        response = client.delete(f"/api/v1/videos/{video.id}/analysis")

        assert response.status_code == 404
