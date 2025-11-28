import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.db.database import get_session
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
    assert response.json() == {"status": "healthy"}


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
