from unittest.mock import AsyncMock, patch

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
def mock_llm_response(mock_provider):
    with patch("app.services.llm.litellm.acompletion") as mock:
        mock_choice = AsyncMock()
        mock_choice.message.content = "This is a test response from the LLM."
        mock_response = AsyncMock()
        mock_response.choices = [mock_choice]
        mock.return_value = mock_response
        yield mock


def test_send_message(test_client, mock_llm_response):
    client, _ = test_client
    response = client.post(
        "/api/v1/chat/message", json={"message": "Hello, how are you?"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "response" in data
    assert data["response"] == "This is a test response from the LLM."
    assert "session_id" in data
    assert "timestamp" in data
    assert len(data["session_id"]) > 0


def test_send_message_with_session_id(test_client, mock_llm_response):
    client, _ = test_client
    session_id = create_session(client)
    response = client.post(
        "/api/v1/chat/message",
        json={"message": "Hello again", "session_id": session_id},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id


def test_send_message_with_invalid_session_id(test_client):
    client, _ = test_client
    response = client.post(
        "/api/v1/chat/message",
        json={"message": "Hello", "session_id": "nonexistent-session"},
    )
    assert response.status_code == 404
    assert "Session not found" in response.json()["detail"]


def test_send_empty_message(test_client):
    client, _ = test_client
    response = client.post("/api/v1/chat/message", json={"message": ""})
    assert response.status_code == 422


def test_llm_called_with_correct_model(test_client, mock_llm_response, mock_provider):
    client, _ = test_client
    client.post("/api/v1/chat/message", json={"message": "Test"})
    mock_llm_response.assert_called_once()
    call_kwargs = mock_llm_response.call_args.kwargs
    assert call_kwargs["model"] == "gemini/gemini-2.0-flash"


def test_chat_without_provider(test_client):
    client, _ = test_client
    with patch("app.services.llm.get_current_provider", return_value=None):
        response = client.post("/api/v1/chat/message", json={"message": "Hello"})
        assert response.status_code == 503
        assert "No LLM provider configured" in response.json()["detail"]
