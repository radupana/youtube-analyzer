from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.db.database import get_session
from app.db.models import Chunk, Video
from app.main import app


@pytest.fixture
def test_client():
    engine = create_engine(
        "sqlite:///file:test_videos_db?mode=memory&cache=shared&uri=true",
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


def create_session(client) -> str:
    response = client.post("/api/v1/sessions", json={"title": "Test Session"})
    return response.json()["id"]


def test_health_check(test_client):
    client, _ = test_client
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "memory" in data
    assert "rss_mb" in data["memory"]
    assert "models" in data
    assert "whisper" in data["models"]
    assert "embeddings" in data["models"]


def test_list_videos(test_client):
    client, _ = test_client
    response = client.get("/api/v1/videos")
    assert response.status_code == 200
    data = response.json()
    assert "videos" in data
    assert "total" in data
    assert isinstance(data["videos"], list)
    assert data["total"] >= 0


def test_get_video_not_found(test_client):
    client, _ = test_client
    response = client.get("/api/v1/videos/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"


def test_add_video(test_client):
    client, _ = test_client
    session_id = create_session(client)
    response = client.post(
        "/api/v1/videos/add",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "session_id": session_id,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "pending"


def test_add_video_missing_session_id(test_client):
    client, _ = test_client
    response = client.post(
        "/api/v1/videos/add",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert response.status_code == 422


def test_add_video_invalid_session_id(test_client):
    client, _ = test_client
    response = client.post(
        "/api/v1/videos/add",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "session_id": "nonexistent-session",
        },
    )
    assert response.status_code == 404
    assert "Session not found" in response.json()["detail"]


def test_add_channel_url_rejected(test_client):
    client, _ = test_client
    session_id = create_session(client)
    response = client.post(
        "/api/v1/videos/add",
        json={
            "url": "https://www.youtube.com/@JeffNippard",
            "session_id": session_id,
        },
    )
    assert response.status_code == 400
    assert "single video URLs" in response.json()["detail"]


def test_add_playlist_url_rejected(test_client):
    client, _ = test_client
    session_id = create_session(client)
    response = client.post(
        "/api/v1/videos/add",
        json={
            "url": "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf",
            "session_id": session_id,
        },
    )
    assert response.status_code == 400
    assert "single video URLs" in response.json()["detail"]


def test_delete_video_not_found(test_client):
    client, _ = test_client
    response = client.delete("/api/v1/videos/nonexistent-video-id")
    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"


def test_get_transcript_success(test_client):
    client, engine = test_client
    with Session(engine) as db:
        video = Video(
            id="test123",
            title="Test Video",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT10M",
            published_at=datetime.now(UTC),
            transcript="Hello world. This is a test transcript.",
            transcript_source="youtube",
        )
        db.add(video)
        db.commit()

        chunk1 = Chunk(
            id="test123_0",
            video_id="test123",
            text="Hello world.",
            start_time=0.0,
            end_time=5.0,
            token_count=3,
            embedding=b"fake",
        )
        chunk2 = Chunk(
            id="test123_1",
            video_id="test123",
            text="This is a test transcript.",
            start_time=5.0,
            end_time=10.0,
            token_count=6,
            embedding=b"fake",
        )
        db.add(chunk1)
        db.add(chunk2)
        db.commit()

    response = client.get("/api/v1/videos/test123/transcript")
    assert response.status_code == 200
    data = response.json()
    assert data["video_id"] == "test123"
    assert data["video_title"] == "Test Video"
    assert data["full_text"] == "Hello world. This is a test transcript."
    assert len(data["segments"]) == 2
    assert data["segments"][0]["text"] == "Hello world."
    assert data["segments"][0]["start_time"] == 0.0
    assert data["segments"][1]["start_time"] == 5.0
    assert data["has_timestamps"] is True


def test_get_transcript_not_found(test_client):
    client, _ = test_client
    response = client.get("/api/v1/videos/nonexistent/transcript")
    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"


def test_get_transcript_no_transcript(test_client):
    client, engine = test_client
    with Session(engine) as db:
        video = Video(
            id="notranscript",
            title="No Transcript Video",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT10M",
            published_at=datetime.now(UTC),
            transcript=None,
            transcript_source=None,
        )
        db.add(video)
        db.commit()

    response = client.get("/api/v1/videos/notranscript/transcript")
    assert response.status_code == 400
    assert "No transcript" in response.json()["detail"]


def test_get_transcript_no_timestamps(test_client):
    client, engine = test_client
    with Session(engine) as db:
        video = Video(
            id="whisper123",
            title="Whisper Video",
            channel_id="ch123",
            channel_title="Test Channel",
            duration="PT10M",
            published_at=datetime.now(UTC),
            transcript="Whisper transcribed text.",
            transcript_source="whisper",
        )
        db.add(video)
        db.commit()

        chunk = Chunk(
            id="whisper123_0",
            video_id="whisper123",
            text="Whisper transcribed text.",
            start_time=0.0,
            end_time=0.0,
            token_count=4,
            embedding=b"fake",
        )
        db.add(chunk)
        db.commit()

    response = client.get("/api/v1/videos/whisper123/transcript")
    assert response.status_code == 200
    data = response.json()
    assert data["has_timestamps"] is False
