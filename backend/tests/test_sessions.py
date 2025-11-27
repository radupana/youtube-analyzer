import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.db.database import get_session
from app.db.models import Message, SessionVideo
from app.db.models import Session as DBSession
from app.main import app


@pytest.fixture
def test_client():
    engine = create_engine(
        "sqlite:///file:test_sessions?mode=memory&cache=shared",
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


class TestListSessions:
    def test_list_sessions_empty(self, test_client):
        client, _ = test_client
        response = client.get("/api/v1/sessions")
        assert response.status_code == 200
        data = response.json()
        assert data["sessions"] == []
        assert data["total"] == 0

    def test_list_sessions_with_data(self, test_client):
        client, engine = test_client
        with Session(engine) as session:
            s = DBSession(title="Test Session")
            session.add(s)
            session.commit()

        response = client.get("/api/v1/sessions")
        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 1
        assert data["sessions"][0]["title"] == "Test Session"
        assert data["sessions"][0]["video_count"] == 0
        assert data["sessions"][0]["message_count"] == 0


class TestCreateSession:
    def test_create_session_default_title(self, test_client):
        client, _ = test_client
        response = client.post("/api/v1/sessions")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Untitled Session"
        assert "id" in data
        assert "created_at" in data
        assert "updated_at" in data

    def test_create_session_custom_title(self, test_client):
        client, _ = test_client
        response = client.post("/api/v1/sessions", json={"title": "My Custom Session"})
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "My Custom Session"

    def test_create_session_empty_title_uses_default(self, test_client):
        client, _ = test_client
        response = client.post("/api/v1/sessions", json={"title": None})
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Untitled Session"


class TestGetSession:
    def test_get_session_not_found(self, test_client):
        client, _ = test_client
        response = client.get("/api/v1/sessions/nonexistent-id")
        assert response.status_code == 404
        assert response.json()["detail"] == "Session not found"

    def test_get_session_with_messages_and_videos(self, test_client):
        client, engine = test_client
        with Session(engine) as session:
            s = DBSession(id="test-session-id", title="Full Session")
            session.add(s)
            session.commit()

            msg = Message(
                session_id=s.id,
                role="user",
                content="Hello",
            )
            video = SessionVideo(
                session_id=s.id,
                video_id="abc123",
                title="Test Video",
                channel_title="Test Channel",
                transcript_source="youtube",
            )
            session.add_all([msg, video])
            session.commit()

        response = client.get("/api/v1/sessions/test-session-id")
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Full Session"
        assert len(data["messages"]) == 1
        assert data["messages"][0]["content"] == "Hello"
        assert len(data["videos"]) == 1
        assert data["videos"][0]["video_id"] == "abc123"


class TestUpdateSession:
    def test_update_session_not_found(self, test_client):
        client, _ = test_client
        response = client.put(
            "/api/v1/sessions/nonexistent-id", json={"title": "New Title"}
        )
        assert response.status_code == 404

    def test_update_session_title(self, test_client):
        client, engine = test_client
        with Session(engine) as session:
            s = DBSession(id="update-test-id", title="Original Title")
            session.add(s)
            session.commit()

        response = client.put(
            "/api/v1/sessions/update-test-id", json={"title": "Updated Title"}
        )
        assert response.status_code == 200
        data = response.json()
        assert data["title"] == "Updated Title"

    def test_update_session_invalid_title(self, test_client):
        client, _ = test_client
        response = client.put("/api/v1/sessions/any-id", json={"title": ""})
        assert response.status_code == 422


class TestDeleteSession:
    def test_delete_session_not_found(self, test_client):
        client, _ = test_client
        response = client.delete("/api/v1/sessions/nonexistent-id")
        assert response.status_code == 404

    def test_delete_session_success(self, test_client):
        client, engine = test_client
        with Session(engine) as session:
            s = DBSession(id="delete-test-id", title="To Delete")
            session.add(s)
            session.commit()

        response = client.delete("/api/v1/sessions/delete-test-id")
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_delete_session_cascades(self, test_client):
        client, engine = test_client
        with Session(engine) as session:
            s = DBSession(id="cascade-test-id", title="Cascade Test")
            session.add(s)
            session.commit()

            msg = Message(session_id=s.id, role="user", content="Will be deleted")
            video = SessionVideo(
                session_id=s.id,
                video_id="vid1",
                title="Video",
                channel_title="Channel",
            )
            session.add_all([msg, video])
            session.commit()

        response = client.delete("/api/v1/sessions/cascade-test-id")
        assert response.status_code == 200

        response = client.get("/api/v1/sessions/cascade-test-id")
        assert response.status_code == 404
