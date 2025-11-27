from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.core.llm_config import LLMProvider
from app.main import app

client = TestClient(app)


@pytest.fixture
def mock_providers():
    """Mock multiple providers for settings tests."""
    providers = [
        LLMProvider(
            id="gemini",
            name="Gemini",
            model="gemini/gemini-2.0-flash",
            api_key="gemini-key",
        ),
        LLMProvider(
            id="openai",
            name="OpenAI GPT-4",
            model="openai/gpt-4o",
            api_key="openai-key",
        ),
    ]
    with patch("app.api_v1.endpoints.settings.get_providers", return_value=providers):
        yield providers


class TestListProviders:
    def test_list_providers_returns_all(self, mock_providers):
        response = client.get("/api/v1/settings/llm-providers")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == "gemini"
        assert data[1]["id"] == "openai"

    def test_list_providers_excludes_api_key(self, mock_providers):
        response = client.get("/api/v1/settings/llm-providers")
        assert response.status_code == 200
        data = response.json()
        for provider in data:
            assert "api_key" not in provider

    def test_list_providers_empty(self):
        with patch("app.api_v1.endpoints.settings.get_providers", return_value=[]):
            response = client.get("/api/v1/settings/llm-providers")
            assert response.status_code == 200
            assert response.json() == []


class TestGetCurrentProvider:
    def test_get_current_provider(self):
        provider = LLMProvider(
            id="test",
            name="Test Provider",
            model="gemini/gemini-2.0-flash",
            api_key="key",
        )
        with patch(
            "app.api_v1.endpoints.settings.get_current_provider", return_value=provider
        ):
            response = client.get("/api/v1/settings/llm-provider")
            assert response.status_code == 200
            data = response.json()
            assert data["id"] == "test"
            assert data["name"] == "Test Provider"
            assert "api_key" not in data

    def test_get_current_provider_none(self):
        with patch(
            "app.api_v1.endpoints.settings.get_current_provider", return_value=None
        ):
            response = client.get("/api/v1/settings/llm-provider")
            assert response.status_code == 200
            assert response.json() is None


class TestSetCurrentProvider:
    def test_set_provider_success(self):
        provider = LLMProvider(
            id="openai",
            name="OpenAI",
            model="openai/gpt-4o",
            api_key="key",
        )
        with patch(
            "app.api_v1.endpoints.settings.get_provider_by_id", return_value=provider
        ):
            with patch(
                "app.api_v1.endpoints.settings.set_current_provider"
            ) as mock_set:
                response = client.post(
                    "/api/v1/settings/llm-provider", json={"id": "openai"}
                )
                assert response.status_code == 200
                data = response.json()
                assert data["id"] == "openai"
                mock_set.assert_called_once_with("openai")

    def test_set_provider_not_found(self):
        with patch(
            "app.api_v1.endpoints.settings.get_provider_by_id", return_value=None
        ):
            response = client.post(
                "/api/v1/settings/llm-provider", json={"id": "nonexistent"}
            )
            assert response.status_code == 404
            assert "not found" in response.json()["detail"]

    def test_set_provider_missing_id(self):
        response = client.post("/api/v1/settings/llm-provider", json={})
        assert response.status_code == 422
