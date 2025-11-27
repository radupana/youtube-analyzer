from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.llm_config import LLMProvider
from app.main import app

client = TestClient(app)


@pytest.fixture
def mock_provider():
    """Mock the LLM provider for chat tests."""
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


def test_send_message(mock_llm_response):
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


def test_send_message_with_session_id(mock_llm_response):
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


def test_llm_called_with_correct_model(mock_llm_response, mock_provider):
    client.post("/api/v1/chat/message", json={"message": "Test"})
    mock_llm_response.assert_called_once()
    call_kwargs = mock_llm_response.call_args.kwargs
    assert call_kwargs["model"] == "gemini/gemini-2.0-flash"


def test_chat_without_provider():
    """Test that chat returns 503 when no provider is configured."""
    with patch("app.services.llm.get_current_provider", return_value=None):
        response = client.post("/api/v1/chat/message", json={"message": "Hello"})
        assert response.status_code == 503
        assert "No LLM provider configured" in response.json()["detail"]
