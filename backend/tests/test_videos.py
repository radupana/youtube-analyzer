from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def create_session() -> str:
    """Helper to create a session and return its ID."""
    response = client.post("/api/v1/sessions", json={"title": "Test Session"})
    return response.json()["id"]


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "healthy"}


def test_list_videos():
    response = client.get("/api/v1/videos")
    assert response.status_code == 200
    data = response.json()
    assert "videos" in data
    assert "total" in data
    assert isinstance(data["videos"], list)
    assert data["total"] >= 0


def test_get_video_not_found():
    """Getting a non-existent video returns 404."""
    response = client.get("/api/v1/videos/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"


def test_add_video():
    """Adding a video URL returns a task ID."""
    session_id = create_session()
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


def test_add_video_missing_session_id():
    """Adding a video without session_id returns 422."""
    response = client.post(
        "/api/v1/videos/add",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ"},
    )
    assert response.status_code == 422


def test_add_video_invalid_session_id():
    """Adding a video with non-existent session returns 404."""
    response = client.post(
        "/api/v1/videos/add",
        json={
            "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
            "session_id": "nonexistent-session",
        },
    )
    assert response.status_code == 404
    assert "Session not found" in response.json()["detail"]


def test_add_channel_url_rejected():
    """Channel URLs should be rejected with 400."""
    session_id = create_session()
    response = client.post(
        "/api/v1/videos/add",
        json={
            "url": "https://www.youtube.com/@JeffNippard",
            "session_id": session_id,
        },
    )
    assert response.status_code == 400
    assert "single video URLs" in response.json()["detail"]


def test_add_playlist_url_rejected():
    """Playlist URLs should be rejected with 400."""
    session_id = create_session()
    response = client.post(
        "/api/v1/videos/add",
        json={
            "url": "https://www.youtube.com/playlist?list=PLrAXtmErZgOeiKm4sgNOknGvNjby9efdf",
            "session_id": session_id,
        },
    )
    assert response.status_code == 400
    assert "single video URLs" in response.json()["detail"]


def test_delete_video_not_found():
    """Deleting a non-existent video returns 404."""
    response = client.delete("/api/v1/videos/nonexistent-video-id")
    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"
