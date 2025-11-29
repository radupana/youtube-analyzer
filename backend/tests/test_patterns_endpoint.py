"""Integration tests for patterns endpoint."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine, select

from app.db.database import get_session
from app.db.models import PatternResult as DBPatternResult
from app.db.models import Video
from app.main import app
from app.services.pattern_execution import PatternResult
from app.services.patterns import Pattern, PatternSummary


@pytest.fixture
def test_client(tmp_path):
    engine = create_engine(
        "sqlite:///file:test_patterns?mode=memory&cache=shared",
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
            transcript="This is a test transcript about Python programming.",
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


class TestListPatterns:
    def test_list_patterns_returns_loaded_patterns(self, test_client):
        client, _ = test_client

        mock_patterns = [
            PatternSummary(
                id="test1",
                name="Test Pattern 1",
                description="Description 1",
                icon="🧪",
                category="test",
            ),
            PatternSummary(
                id="test2",
                name="Test Pattern 2",
                description="Description 2",
                icon="📝",
                category="summary",
            ),
        ]

        with patch(
            "app.api_v1.endpoints.patterns.list_patterns", return_value=mock_patterns
        ):
            response = client.get("/api/v1/patterns")

        assert response.status_code == 200
        data = response.json()
        assert len(data["patterns"]) == 2
        assert data["patterns"][0]["id"] == "test1"
        assert data["patterns"][1]["id"] == "test2"

    def test_list_patterns_empty(self, test_client):
        client, _ = test_client

        with patch("app.api_v1.endpoints.patterns.list_patterns", return_value=[]):
            response = client.get("/api/v1/patterns")

        assert response.status_code == 200
        data = response.json()
        assert data["patterns"] == []


class TestApplyPattern:
    def test_apply_pattern_success(self, test_client):
        client, engine = test_client
        video = create_video_with_transcript(engine)

        test_pattern = Pattern(
            id="test_pattern",
            name="Test Pattern",
            description="A test pattern",
            icon="🧪",
            category="test",
            system_prompt="You are helpful.",
            user_prompt="Analyze: {transcript}",
        )

        mock_result = PatternResult(
            content="# Analysis\n\nThis is the analysis result.",
            model_used="test-model",
            created_at=datetime.now(UTC),
        )

        with patch(
            "app.api_v1.endpoints.patterns.get_pattern", return_value=test_pattern
        ):
            with patch(
                "app.api_v1.endpoints.patterns.execute_pattern",
                new_callable=AsyncMock,
                return_value=mock_result,
            ):
                response = client.post(
                    f"/api/v1/patterns/videos/{video.id}/results/test_pattern"
                )

        assert response.status_code == 200
        data = response.json()
        assert data["video_id"] == video.id
        assert data["pattern_id"] == "test_pattern"
        assert data["pattern_name"] == "Test Pattern"
        assert "Analysis" in data["result"]
        assert data["model_used"] == "test-model"

    def test_apply_pattern_video_not_found(self, test_client):
        client, _ = test_client

        response = client.post(
            "/api/v1/patterns/videos/nonexistent/results/extract_wisdom"
        )

        assert response.status_code == 404
        assert "Video not found" in response.json()["detail"]

    def test_apply_pattern_pattern_not_found(self, test_client):
        client, engine = test_client
        video = create_video_with_transcript(engine)

        with patch("app.api_v1.endpoints.patterns.get_pattern", return_value=None):
            response = client.post(
                f"/api/v1/patterns/videos/{video.id}/results/nonexistent"
            )

        assert response.status_code == 404
        assert "Pattern not found" in response.json()["detail"]

    def test_apply_pattern_missing_transcript(self, test_client):
        client, engine = test_client
        video = create_video_without_transcript(engine)

        test_pattern = Pattern(
            id="test_pattern",
            name="Test Pattern",
            description="A test pattern",
            icon="🧪",
            category="test",
            system_prompt="System",
            user_prompt="{transcript}",
            inputs=["transcript"],
        )

        with patch(
            "app.api_v1.endpoints.patterns.get_pattern", return_value=test_pattern
        ):
            response = client.post(
                f"/api/v1/patterns/videos/{video.id}/results/test_pattern"
            )

        assert response.status_code == 422
        assert "missing required data" in response.json()["detail"]
        assert "transcript" in response.json()["detail"]


class TestPatternCaching:
    def test_returns_cached_result(self, test_client):
        client, engine = test_client
        video = create_video_with_transcript(engine)

        with Session(engine) as session:
            cached = DBPatternResult(
                video_id=video.id,
                pattern_id="summarize",
                result="# Cached Summary\n\nThis was cached.",
                model_used="cached-model",
            )
            session.add(cached)
            session.commit()

        test_pattern = Pattern(
            id="summarize",
            name="Summarize",
            description="Summarize",
            icon="📝",
            category="summary",
            system_prompt="System",
            user_prompt="{transcript}",
        )

        with patch(
            "app.api_v1.endpoints.patterns.get_pattern", return_value=test_pattern
        ):
            response = client.post(
                f"/api/v1/patterns/videos/{video.id}/results/summarize"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["result"] == "# Cached Summary\n\nThis was cached."
        assert data["model_used"] == "cached-model"

    def test_refresh_replaces_cached_result(self, test_client):
        client, engine = test_client
        video = create_video_with_transcript(engine)

        with Session(engine) as session:
            cached = DBPatternResult(
                video_id=video.id,
                pattern_id="summarize",
                result="Old result",
                model_used="old-model",
            )
            session.add(cached)
            session.commit()

        test_pattern = Pattern(
            id="summarize",
            name="Summarize",
            description="Summarize",
            icon="📝",
            category="summary",
            system_prompt="System",
            user_prompt="{transcript}",
        )

        mock_result = PatternResult(
            content="New fresh result",
            model_used="new-model",
            created_at=datetime.now(UTC),
        )

        with patch(
            "app.api_v1.endpoints.patterns.get_pattern", return_value=test_pattern
        ):
            with patch(
                "app.api_v1.endpoints.patterns.execute_pattern",
                new_callable=AsyncMock,
                return_value=mock_result,
            ):
                response = client.post(
                    f"/api/v1/patterns/videos/{video.id}/results/summarize/refresh"
                )

        assert response.status_code == 200
        data = response.json()
        assert data["result"] == "New fresh result"
        assert data["model_used"] == "new-model"

        with Session(engine) as session:
            results = session.exec(
                select(DBPatternResult).where(DBPatternResult.video_id == video.id)
            ).all()
            assert len(results) == 1
            assert results[0].result == "New fresh result"

    def test_get_pattern_result(self, test_client):
        client, engine = test_client
        video = create_video_with_transcript(engine)

        with Session(engine) as session:
            cached = DBPatternResult(
                video_id=video.id,
                pattern_id="extract_wisdom",
                result="# Wisdom\n\nSome wisdom here.",
                model_used="test-model",
            )
            session.add(cached)
            session.commit()

        test_pattern = Pattern(
            id="extract_wisdom",
            name="Extract Wisdom",
            description="Extract",
            icon="💡",
            category="analysis",
            system_prompt="System",
            user_prompt="{transcript}",
        )

        with patch(
            "app.api_v1.endpoints.patterns.get_pattern", return_value=test_pattern
        ):
            response = client.get(
                f"/api/v1/patterns/videos/{video.id}/results/extract_wisdom"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["pattern_id"] == "extract_wisdom"
        assert data["pattern_name"] == "Extract Wisdom"
        assert "Wisdom" in data["result"]

    def test_get_pattern_result_not_found(self, test_client):
        client, engine = test_client
        video = create_video_with_transcript(engine)

        response = client.get(f"/api/v1/patterns/videos/{video.id}/results/nonexistent")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    def test_list_video_pattern_results(self, test_client):
        client, engine = test_client
        video = create_video_with_transcript(engine)

        with Session(engine) as session:
            r1 = DBPatternResult(
                video_id=video.id,
                pattern_id="summarize",
                result="Summary",
                model_used="model1",
            )
            r2 = DBPatternResult(
                video_id=video.id,
                pattern_id="extract_wisdom",
                result="Wisdom",
                model_used="model2",
            )
            session.add(r1)
            session.add(r2)
            session.commit()

        response = client.get(f"/api/v1/patterns/videos/{video.id}/results")

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        pattern_ids = {r["pattern_id"] for r in data}
        assert pattern_ids == {"summarize", "extract_wisdom"}

    def test_delete_pattern_result(self, test_client):
        client, engine = test_client
        video = create_video_with_transcript(engine)

        with Session(engine) as session:
            cached = DBPatternResult(
                video_id=video.id,
                pattern_id="summarize",
                result="To be deleted",
                model_used="test",
            )
            session.add(cached)
            session.commit()

        response = client.delete(
            f"/api/v1/patterns/videos/{video.id}/results/summarize"
        )

        assert response.status_code == 200
        assert response.json()["success"] is True

        with Session(engine) as session:
            results = session.exec(
                select(DBPatternResult).where(DBPatternResult.video_id == video.id)
            ).all()
            assert len(results) == 0

    def test_delete_pattern_result_not_found(self, test_client):
        client, engine = test_client
        video = create_video_with_transcript(engine)

        response = client.delete(
            f"/api/v1/patterns/videos/{video.id}/results/nonexistent"
        )

        assert response.status_code == 404
