import pytest
import yaml

from app.core import llm_config
from app.core.llm_config import (
    LLMProvider,
    RagConfig,
    TranscriptConfig,
    WhisperConfig,
    get_current_provider,
    get_provider_by_id,
    get_providers,
    get_rag_config,
    get_transcript_config,
    get_whisper_config,
    load_config,
    set_current_provider,
)


@pytest.fixture(autouse=True)
def reset_llm_config():
    """Reset global state before each test."""
    llm_config._providers = {}
    llm_config._current_provider_id = None
    llm_config._default_provider_id = None
    llm_config._whisper_config = WhisperConfig()
    llm_config._rag_config = RagConfig()
    llm_config._transcript_config = TranscriptConfig()
    yield
    llm_config._providers = {}
    llm_config._current_provider_id = None
    llm_config._default_provider_id = None
    llm_config._whisper_config = WhisperConfig()
    llm_config._rag_config = RagConfig()
    llm_config._transcript_config = TranscriptConfig()


class TestLoadConfig:
    def test_load_config_with_valid_yaml(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TEST_API_KEY", "test-key-123")

        config = {
            "llm_providers": [
                {
                    "id": "test-provider",
                    "name": "Test Provider",
                    "model": "gemini/gemini-2.0-flash",
                    "api_key_env": "TEST_API_KEY",
                }
            ],
            "default_provider": "test-provider",
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config))

        load_config(config_file)

        providers = get_providers()
        assert len(providers) == 1
        assert providers[0].id == "test-provider"
        assert providers[0].api_key == "test-key-123"

    def test_load_config_skips_provider_without_api_key(self, monkeypatch, tmp_path):
        monkeypatch.delenv("MISSING_KEY", raising=False)

        config = {
            "llm_providers": [
                {
                    "id": "no-key-provider",
                    "name": "No Key",
                    "model": "openai/gpt-4",
                    "api_key_env": "MISSING_KEY",
                }
            ]
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config))

        load_config(config_file)

        assert len(get_providers()) == 0

    def test_load_config_with_multiple_providers(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GEMINI_KEY", "gemini-key")
        monkeypatch.setenv("OPENAI_KEY", "openai-key")

        config = {
            "llm_providers": [
                {
                    "id": "gemini",
                    "name": "Gemini",
                    "model": "gemini/gemini-2.0-flash",
                    "api_key_env": "GEMINI_KEY",
                },
                {
                    "id": "openai",
                    "name": "OpenAI",
                    "model": "openai/gpt-4o",
                    "api_key_env": "OPENAI_KEY",
                },
            ],
            "default_provider": "openai",
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config))

        load_config(config_file)

        providers = get_providers()
        assert len(providers) == 2
        current = get_current_provider()
        assert current.id == "openai"

    def test_load_config_nonexistent_file(self, tmp_path):
        load_config(tmp_path / "nonexistent.yaml")
        assert len(get_providers()) == 0
        assert get_current_provider() is None

    def test_load_config_sets_first_provider_if_no_default(self, monkeypatch, tmp_path):
        monkeypatch.setenv("API_KEY", "test-key")

        config = {
            "llm_providers": [
                {
                    "id": "first",
                    "name": "First Provider",
                    "model": "gemini/gemini-2.0-flash",
                    "api_key_env": "API_KEY",
                }
            ]
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config))

        load_config(config_file)

        current = get_current_provider()
        assert current.id == "first"


class TestProviderManagement:
    def test_set_current_provider_valid(self, monkeypatch, tmp_path):
        monkeypatch.setenv("KEY1", "key1")
        monkeypatch.setenv("KEY2", "key2")

        config = {
            "llm_providers": [
                {
                    "id": "provider1",
                    "name": "Provider 1",
                    "model": "gemini/gemini-2.0-flash",
                    "api_key_env": "KEY1",
                },
                {
                    "id": "provider2",
                    "name": "Provider 2",
                    "model": "openai/gpt-4o",
                    "api_key_env": "KEY2",
                },
            ],
            "default_provider": "provider1",
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config))
        load_config(config_file)

        assert get_current_provider().id == "provider1"
        assert set_current_provider("provider2") is True
        assert get_current_provider().id == "provider2"

    def test_set_current_provider_invalid(self, monkeypatch, tmp_path):
        monkeypatch.setenv("KEY1", "key1")

        config = {
            "llm_providers": [
                {
                    "id": "provider1",
                    "name": "Provider 1",
                    "model": "gemini/gemini-2.0-flash",
                    "api_key_env": "KEY1",
                }
            ]
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config))
        load_config(config_file)

        assert set_current_provider("nonexistent") is False
        assert get_current_provider().id == "provider1"

    def test_get_provider_by_id(self, monkeypatch, tmp_path):
        monkeypatch.setenv("KEY", "test-key")

        config = {
            "llm_providers": [
                {
                    "id": "test",
                    "name": "Test",
                    "model": "gemini/gemini-2.0-flash",
                    "api_key_env": "KEY",
                }
            ]
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config))
        load_config(config_file)

        provider = get_provider_by_id("test")
        assert provider is not None
        assert provider.name == "Test"

        assert get_provider_by_id("nonexistent") is None


class TestLLMProvider:
    def test_provider_dataclass(self):
        provider = LLMProvider(
            id="test",
            name="Test Provider",
            model="gemini/gemini-2.0-flash",
            api_key="test-key",
        )
        assert provider.id == "test"
        assert provider.name == "Test Provider"
        assert provider.model == "gemini/gemini-2.0-flash"
        assert provider.api_key == "test-key"


class TestWhisperConfig:
    def test_default_whisper_config(self):
        config = get_whisper_config()
        assert config.model == "base"
        assert config.fallback_enabled is True
        assert config.unload_timeout == 300

    def test_whisper_config_from_yaml(self, monkeypatch, tmp_path):
        monkeypatch.setenv("API_KEY", "test-key")

        config = {
            "llm_providers": [
                {
                    "id": "test",
                    "name": "Test",
                    "model": "gemini/gemini-2.0-flash",
                    "api_key_env": "API_KEY",
                }
            ],
            "whisper": {
                "model": "large",
                "fallback_enabled": False,
                "unload_timeout": 60,
            },
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config))

        load_config(config_file)

        whisper_cfg = get_whisper_config()
        assert whisper_cfg.model == "large"
        assert whisper_cfg.fallback_enabled is False
        assert whisper_cfg.unload_timeout == 60

    def test_whisper_config_defaults_when_missing(self, monkeypatch, tmp_path):
        monkeypatch.setenv("API_KEY", "test-key")

        config = {
            "llm_providers": [
                {
                    "id": "test",
                    "name": "Test",
                    "model": "gemini/gemini-2.0-flash",
                    "api_key_env": "API_KEY",
                }
            ],
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config))

        load_config(config_file)

        whisper_cfg = get_whisper_config()
        assert whisper_cfg.model == "base"
        assert whisper_cfg.fallback_enabled is True
        assert whisper_cfg.unload_timeout == 300


class TestRagConfig:
    def test_default_rag_config(self):
        config = get_rag_config()
        assert config.chunk_size == 500
        assert config.chunk_overlap == 50
        assert config.top_k == 10
        assert config.max_context_tokens == 4000

    def test_rag_config_from_yaml(self, monkeypatch, tmp_path):
        monkeypatch.setenv("API_KEY", "test-key")

        config = {
            "llm_providers": [
                {
                    "id": "test",
                    "name": "Test",
                    "model": "gemini/gemini-2.0-flash",
                    "api_key_env": "API_KEY",
                }
            ],
            "rag": {
                "chunk_size": 1000,
                "chunk_overlap": 100,
                "top_k": 20,
                "max_context_tokens": 8000,
            },
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config))

        load_config(config_file)

        rag_cfg = get_rag_config()
        assert rag_cfg.chunk_size == 1000
        assert rag_cfg.chunk_overlap == 100
        assert rag_cfg.top_k == 20
        assert rag_cfg.max_context_tokens == 8000

    def test_rag_config_defaults_when_missing(self, monkeypatch, tmp_path):
        monkeypatch.setenv("API_KEY", "test-key")

        config = {
            "llm_providers": [
                {
                    "id": "test",
                    "name": "Test",
                    "model": "gemini/gemini-2.0-flash",
                    "api_key_env": "API_KEY",
                }
            ],
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config))

        load_config(config_file)

        rag_cfg = get_rag_config()
        assert rag_cfg.chunk_size == 500
        assert rag_cfg.chunk_overlap == 50
        assert rag_cfg.top_k == 10
        assert rag_cfg.max_context_tokens == 4000


class TestTranscriptConfig:
    def test_default_transcript_config(self):
        config = get_transcript_config()
        assert config.preferred_languages == ["en"]
        assert config.prefer_manual is True

    def test_transcript_config_from_yaml(self, monkeypatch, tmp_path):
        monkeypatch.setenv("API_KEY", "test-key")

        config = {
            "llm_providers": [
                {
                    "id": "test",
                    "name": "Test",
                    "model": "gemini/gemini-2.0-flash",
                    "api_key_env": "API_KEY",
                }
            ],
            "transcripts": {
                "preferred_languages": ["de", "fr", "en"],
                "prefer_manual": False,
            },
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config))

        load_config(config_file)

        transcript_cfg = get_transcript_config()
        assert transcript_cfg.preferred_languages == ["de", "fr", "en"]
        assert transcript_cfg.prefer_manual is False

    def test_transcript_config_defaults_when_missing(self, monkeypatch, tmp_path):
        monkeypatch.setenv("API_KEY", "test-key")

        config = {
            "llm_providers": [
                {
                    "id": "test",
                    "name": "Test",
                    "model": "gemini/gemini-2.0-flash",
                    "api_key_env": "API_KEY",
                }
            ],
        }
        config_file = tmp_path / "config.yaml"
        config_file.write_text(yaml.dump(config))

        load_config(config_file)

        transcript_cfg = get_transcript_config()
        assert transcript_cfg.preferred_languages == ["en"]
        assert transcript_cfg.prefer_manual is True
