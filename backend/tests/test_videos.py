from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


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


def test_get_video():
    response = client.get("/api/v1/videos/dQw4w9WgXcQ")
    assert response.status_code == 200
    video = response.json()
    assert video["id"] == "dQw4w9WgXcQ"
    assert "title" in video
    assert "channel_id" in video


def test_get_video_not_found():
    response = client.get("/api/v1/videos/nonexistent")
    assert response.status_code == 404
    assert response.json()["detail"] == "Video not found"


def test_add_video():
    response = client.post(
        "/api/v1/videos/add",
        json={"url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ", "max_videos": 10},
    )
    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "pending"


def test_delete_video():
    response = client.delete("/api/v1/videos/dQw4w9WgXcQ")
    assert response.status_code == 200
    assert response.json()["success"] is True
