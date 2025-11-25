from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_send_message():
    response = client.post(
        "/api/v1/chat/message", json={"message": "Hello, how are you?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert "session_id" in data
    assert "timestamp" in data
    assert len(data["session_id"]) > 0


def test_send_message_with_session_id():
    session_id = "test-session-123"
    response = client.post(
        "/api/v1/chat/message",
        json={"message": "Hello again", "session_id": session_id},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id


def test_send_empty_message():
    response = client.post("/api/v1/chat/message", json={"message": ""})
    assert response.status_code == 422
