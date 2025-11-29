from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, SQLModel, create_engine

from app.core.llm_config import LLMProvider
from app.db.database import get_session
from app.main import app


@pytest.fixture
def test_client():
    engine = create_engine(
        "sqlite:///file:test_chat_db?mode=memory&cache=shared&uri=true",
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


def create_session(client) -> str:
    response = client.post("/api/v1/sessions", json={"title": "Test Session"})
    return response.json()["id"]


@pytest.fixture
def mock_provider():
    provider = LLMProvider(
        id="test-provider",
        name="Test Provider",
        model="gemini/gemini-2.0-flash",
        api_key="test-api-key",
    )
    with patch("app.services.llm.get_current_provider", return_value=provider):
        yield provider


@pytest.fixture
def mock_llm_stream(mock_provider):
    with patch("app.core.llm_config.get_current_provider", return_value=mock_provider):
        with patch("app.services.llm.litellm.acompletion") as mock:
            mock.return_value = mock_stream_async_generator()
            yield mock


def mock_stream_async_generator():
    class MockDelta:
        def __init__(self, content):
            self.content = content

    class MockChoice:
        def __init__(self, content):
            self.delta = MockDelta(content)

    class MockChunk:
        def __init__(self, content):
            self.choices = [MockChoice(content)]

    class AsyncGen:
        def __init__(self):
            self.chunks = ["Hello", " ", "world", "!"]
            self.index = 0

        def __aiter__(self):
            return self

        async def __anext__(self):
            if self.index >= len(self.chunks):
                raise StopAsyncIteration
            chunk = MockChunk(self.chunks[self.index])
            self.index += 1
            return chunk

    return AsyncGen()


def test_stream_message(test_client, mock_llm_stream):
    client, _ = test_client
    response = client.post(
        "/api/v1/chat/message/stream",
        json={"message": "Hello, how are you?"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream; charset=utf-8"

    content = response.text
    assert "data:" in content
    assert "[DONE]" in content


def test_stream_message_with_session_id(test_client, mock_llm_stream):
    client, _ = test_client
    session_id = create_session(client)
    response = client.post(
        "/api/v1/chat/message/stream",
        json={"message": "Hello again", "session_id": session_id},
    )
    assert response.status_code == 200
    content = response.text
    assert f"data: {session_id}" in content


def test_stream_message_invalid_session(test_client, mock_provider):
    client, _ = test_client
    with patch("app.core.llm_config.get_current_provider", return_value=mock_provider):
        response = client.post(
            "/api/v1/chat/message/stream",
            json={"message": "Hello", "session_id": "nonexistent-session"},
        )
        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]


def test_stream_without_provider(test_client):
    client, _ = test_client
    session_id = create_session(client)
    with patch("app.core.llm_config.get_current_provider", return_value=None):
        response = client.post(
            "/api/v1/chat/message/stream",
            json={"message": "Hello", "session_id": session_id},
        )
        assert response.status_code == 503
