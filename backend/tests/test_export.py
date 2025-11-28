"""Tests for transcript export functionality."""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.db.database import get_session
from app.db.models import Chunk, Video, VideoAnalysis
from app.main import app
from app.services.export import (
    export_json,
    export_markdown,
    export_srt,
    export_txt,
    format_timestamp_srt,
)

client = TestClient(app)


@pytest.fixture
def sample_video() -> Video:
    return Video(
        id="test123",
        title="Test Video Title",
        channel_id="UC123",
        channel_title="Test Channel",
        description="Test description",
        duration="PT5M30S",
        published_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
        transcript="Hello world. This is a test transcript.",
        transcript_source="youtube",
    )


@pytest.fixture
def sample_chunks() -> list[Chunk]:
    return [
        Chunk(
            id="test123_0",
            video_id="test123",
            text="Hello world.",
            start_time=0.0,
            end_time=2.5,
            token_count=3,
            embedding=b"",
        ),
        Chunk(
            id="test123_1",
            video_id="test123",
            text="This is a test transcript.",
            start_time=2.5,
            end_time=5.0,
            token_count=6,
            embedding=b"",
        ),
    ]


class TestFormatTimestampSrt:
    def test_zero(self):
        assert format_timestamp_srt(0.0) == "00:00:00,000"

    def test_seconds_only(self):
        assert format_timestamp_srt(30.5) == "00:00:30,500"

    def test_minutes_and_seconds(self):
        assert format_timestamp_srt(125.123) == "00:02:05,123"

    def test_hours(self):
        assert format_timestamp_srt(3661.0) == "01:01:01,000"


class TestExportTxt:
    def test_basic(self, sample_video: Video):
        result = export_txt(sample_video)
        assert "Title: Test Video Title" in result
        assert "Channel: Test Channel" in result
        assert "https://youtube.com/watch?v=test123" in result
        assert "Hello world. This is a test transcript." in result

    def test_no_transcript(self, sample_video: Video):
        sample_video.transcript = None
        result = export_txt(sample_video)
        assert "(No transcript available)" in result


class TestExportMarkdown:
    def test_basic(self, sample_video: Video):
        result = export_markdown(sample_video)
        assert "# Test Video Title" in result
        assert "**Channel:** Test Channel" in result
        assert "## Transcript" in result
        assert "Hello world. This is a test transcript." in result

    def test_no_transcript(self, sample_video: Video):
        sample_video.transcript = None
        result = export_markdown(sample_video)
        assert "*No transcript available*" in result


class TestExportSrt:
    def test_basic(self, sample_chunks: list[Chunk]):
        result = export_srt(sample_chunks)
        assert "1\n00:00:00,000 --> 00:00:02,500\nHello world." in result
        assert "2\n00:00:02,500 --> 00:00:05,000\nThis is a test transcript." in result

    def test_empty_chunks(self):
        result = export_srt([])
        assert result == ""


class TestExportJson:
    def test_basic(self, sample_video: Video):
        result = export_json(sample_video)
        assert result["video_id"] == "test123"
        assert result["title"] == "Test Video Title"
        assert result["full_text"] == "Hello world. This is a test transcript."

    def test_with_segments(self, sample_video: Video, sample_chunks: list[Chunk]):
        result = export_json(sample_video, sample_chunks)
        assert "segments" in result
        assert len(result["segments"]) == 2
        assert result["segments"][0]["start"] == 0.0
        assert result["segments"][0]["text"] == "Hello world."

    def test_with_analysis(self, sample_video: Video):
        analysis = VideoAnalysis(
            video_id="test123",
            summary="Test summary about the video.",
            key_takeaways='["Takeaway 1", "Takeaway 2"]',
            main_topics='["Topic A", "Topic B"]',
            notable_quotes='["Quote 1"]',
            model_used="gemini/gemini-2.5-flash",
        )
        result = export_json(sample_video, analysis=analysis)
        assert "analysis" in result
        assert result["analysis"]["summary"] == "Test summary about the video."
        assert result["analysis"]["key_takeaways"] == ["Takeaway 1", "Takeaway 2"]
        assert result["analysis"]["main_topics"] == ["Topic A", "Topic B"]
        assert result["analysis"]["notable_quotes"] == ["Quote 1"]
        assert result["analysis"]["model_used"] == "gemini/gemini-2.5-flash"


class TestExportEndpoint:
    def test_export_not_found(self):
        response = client.get("/api/v1/videos/nonexistent/export")
        assert response.status_code == 404

    def test_export_txt_format(self):
        engine = create_engine(
            "sqlite:///file:test_txt?mode=memory&cache=shared&uri=true",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            video = Video(
                id="exporttest",
                title="Export Test Video",
                channel_id="UC123",
                channel_title="Test Channel",
                description="Test description",
                duration="PT5M30S",
                published_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
                transcript="Hello world. This is a test transcript.",
                transcript_source="youtube",
            )
            session.add(video)
            session.commit()

        def override_session():
            with Session(engine) as session:
                yield session

        app.dependency_overrides[get_session] = override_session
        try:
            response = client.get("/api/v1/videos/exporttest/export?format=txt")
            assert response.status_code == 200
            assert "text/plain" in response.headers["content-type"]
            assert "attachment" in response.headers["content-disposition"]
            assert "Title: Export Test Video" in response.text
        finally:
            app.dependency_overrides.clear()

    def test_export_markdown_format(self):
        engine = create_engine(
            "sqlite:///file:test_md?mode=memory&cache=shared&uri=true",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            video = Video(
                id="mdtest",
                title="Markdown Test Video",
                channel_id="UC123",
                channel_title="Test Channel",
                description="Test description",
                duration="PT5M30S",
                published_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
                transcript="Hello world.",
                transcript_source="youtube",
            )
            session.add(video)
            session.commit()

        def override_session():
            with Session(engine) as session:
                yield session

        app.dependency_overrides[get_session] = override_session
        try:
            response = client.get("/api/v1/videos/mdtest/export?format=md")
            assert response.status_code == 200
            assert "text/markdown" in response.headers["content-type"]
            assert "# Markdown Test Video" in response.text
        finally:
            app.dependency_overrides.clear()

    def test_export_json_format(self):
        engine = create_engine(
            "sqlite:///file:test_json?mode=memory&cache=shared&uri=true",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            video = Video(
                id="jsontest",
                title="JSON Test Video",
                channel_id="UC123",
                channel_title="Test Channel",
                description="Test description",
                duration="PT5M30S",
                published_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
                transcript="Hello world.",
                transcript_source="youtube",
            )
            session.add(video)
            session.commit()

        def override_session():
            with Session(engine) as session:
                yield session

        app.dependency_overrides[get_session] = override_session
        try:
            response = client.get("/api/v1/videos/jsontest/export?format=json")
            assert response.status_code == 200
            assert "application/json" in response.headers["content-type"]
            data = response.json()
            assert data["video_id"] == "jsontest"
            assert data["title"] == "JSON Test Video"
        finally:
            app.dependency_overrides.clear()

    def test_export_json_with_analysis(self):
        engine = create_engine(
            "sqlite:///file:test_json_analysis?mode=memory&cache=shared&uri=true",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            video = Video(
                id="jsonanalysistest",
                title="JSON Analysis Test",
                channel_id="UC123",
                channel_title="Test Channel",
                description="",
                duration="PT5M",
                published_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
                transcript="Hello world.",
                transcript_source="youtube",
            )
            session.add(video)
            analysis = VideoAnalysis(
                video_id="jsonanalysistest",
                summary="Test summary.",
                key_takeaways='["Point 1"]',
                main_topics='["Topic A"]',
                notable_quotes='["Quote"]',
                model_used="gemini/gemini-2.5-flash",
            )
            session.add(analysis)
            session.commit()

        def override_session():
            with Session(engine) as session:
                yield session

        app.dependency_overrides[get_session] = override_session
        try:
            response = client.get("/api/v1/videos/jsonanalysistest/export?format=json")
            assert response.status_code == 200
            data = response.json()
            assert "analysis" in data
            assert data["analysis"]["summary"] == "Test summary."
            assert data["analysis"]["key_takeaways"] == ["Point 1"]
        finally:
            app.dependency_overrides.clear()

    def test_export_srt_no_chunks(self):
        engine = create_engine(
            "sqlite:///file:test_srt_no?mode=memory&cache=shared&uri=true",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            video = Video(
                id="srtnotest",
                title="SRT No Chunks Video",
                channel_id="UC123",
                channel_title="Test Channel",
                description="",
                duration="PT1M",
                published_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
                transcript="Hello world.",
                transcript_source="youtube",
            )
            session.add(video)
            session.commit()

        def override_session():
            with Session(engine) as session:
                yield session

        app.dependency_overrides[get_session] = override_session
        try:
            response = client.get("/api/v1/videos/srtnotest/export?format=srt")
            assert response.status_code == 400
            assert "timestamp data" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()

    def test_export_srt_with_chunks(self):
        engine = create_engine(
            "sqlite:///file:test_srt_chunks?mode=memory&cache=shared&uri=true",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            video = Video(
                id="srtvideo",
                title="SRT Test Video",
                channel_id="UC123",
                channel_title="Test Channel",
                description="",
                duration="PT1M",
                published_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
                transcript="Hello world. This is a test.",
                transcript_source="youtube",
            )
            session.add(video)
            chunks = [
                Chunk(
                    id="srtvideo_0",
                    video_id="srtvideo",
                    text="Hello world.",
                    start_time=0.0,
                    end_time=2.5,
                    token_count=3,
                    embedding=b"",
                ),
                Chunk(
                    id="srtvideo_1",
                    video_id="srtvideo",
                    text="This is a test.",
                    start_time=2.5,
                    end_time=5.0,
                    token_count=5,
                    embedding=b"",
                ),
            ]
            for chunk in chunks:
                session.add(chunk)
            session.commit()

        def override_session():
            with Session(engine) as session:
                yield session

        app.dependency_overrides[get_session] = override_session
        try:
            response = client.get("/api/v1/videos/srtvideo/export?format=srt")
            assert response.status_code == 200
            assert "text/srt" in response.headers["content-type"]
            assert "00:00:00,000 --> 00:00:02,500" in response.text
        finally:
            app.dependency_overrides.clear()

    def test_export_no_transcript(self):
        engine = create_engine(
            "sqlite:///file:test_no_transcript?mode=memory&cache=shared&uri=true",
            connect_args={"check_same_thread": False},
        )
        SQLModel.metadata.create_all(engine)
        with Session(engine) as session:
            video = Video(
                id="notranscript",
                title="No Transcript Video",
                channel_id="UC123",
                channel_title="Test Channel",
                description="",
                duration="PT1M",
                published_at=datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC),
                transcript=None,
                transcript_source="none",
            )
            session.add(video)
            session.commit()

        def override_session():
            with Session(engine) as session:
                yield session

        app.dependency_overrides[get_session] = override_session
        try:
            response = client.get("/api/v1/videos/notranscript/export")
            assert response.status_code == 400
            assert "No transcript" in response.json()["detail"]
        finally:
            app.dependency_overrides.clear()
