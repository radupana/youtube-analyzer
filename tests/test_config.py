import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from yt_agent_kit.config import (
    Config,
    EmbeddingsConfig,
    LLMConfig,
    SearchConfig,
    load_config,
    resolve_env_vars,
)


class TestResolveEnvVars:
    def test_simple_string(self):
        assert resolve_env_vars("hello") == "hello"

    def test_env_var_substitution(self, monkeypatch):
        monkeypatch.setenv("TEST_VAR", "test_value")
        assert resolve_env_vars("${TEST_VAR}") == "test_value"

    def test_missing_env_var_raises(self):
        with pytest.raises(ValueError, match="TEST_MISSING is not set"):
            resolve_env_vars("${TEST_MISSING}")

    def test_dict_with_env_vars(self, monkeypatch):
        monkeypatch.setenv("KEY1", "value1")
        monkeypatch.setenv("KEY2", "value2")
        input_dict = {"a": "${KEY1}", "b": "${KEY2}", "c": "static"}
        expected = {"a": "value1", "b": "value2", "c": "static"}
        assert resolve_env_vars(input_dict) == expected

    def test_nested_structure(self, monkeypatch):
        monkeypatch.setenv("NESTED", "nested_value")
        input_data = {
            "level1": {"level2": "${NESTED}", "list": ["${NESTED}", "static"]}
        }
        expected = {
            "level1": {"level2": "nested_value", "list": ["nested_value", "static"]}
        }
        assert resolve_env_vars(input_data) == expected


class TestLoadConfig:
    def test_load_valid_config(self):
        config_data = {
            "llm": {
                "provider": "gemini",
                "api_key": "test-api-key-1234567890",
                "model": "gemini-2.0-flash",
            },
            "youtube_api_key": "youtube-api-key-1234567890",
            "output_file": "out.json",
            "max_videos": 10,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = load_config(config_path)
            assert config.llm.provider == "gemini"
            assert config.llm.api_key == "test-api-key-1234567890"
            assert config.youtube_api_key == "youtube-api-key-1234567890"
            assert config.max_videos == 10
        finally:
            config_path.unlink()

    def test_missing_config_file(self):
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config(Path("nonexistent.yaml"))

    def test_config_with_env_vars(self, monkeypatch):
        monkeypatch.setenv("TEST_API_KEY", "secret-api-key-1234567890")
        monkeypatch.setenv("YT_KEY", "youtube-api-key-1234567890")

        config_data = {
            "llm": {
                "provider": "gemini",
                "api_key": "${TEST_API_KEY}",
                "model": "gemini-2.0-flash",
            },
            "youtube_api_key": "${YT_KEY}",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = load_config(config_path)
            assert config.llm.api_key == "secret-api-key-1234567890"
            assert config.youtube_api_key == "youtube-api-key-1234567890"
        finally:
            config_path.unlink()

    def test_invalid_llm_provider(self):
        config_data = {
            "llm": {
                "provider": "invalid",
                "api_key": "test-api-key-1234567890",
                "model": "model",
            },
            "youtube_api_key": "youtube-api-key-1234567890",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="Invalid configuration"):
                load_config(config_path)
        finally:
            config_path.unlink()

    def test_max_videos_validation(self):
        config_data = {
            "llm": {
                "provider": "gemini",
                "api_key": "test-api-key-1234567890",
                "model": "model",
            },
            "youtube_api_key": "youtube-api-key-1234567890",
            "max_videos": 1001,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            with pytest.raises(ValueError, match="Invalid configuration"):
                load_config(config_path)
        finally:
            config_path.unlink()


class TestValidateConfig:
    def test_valid_config(self):
        config = Config(
            llm=LLMConfig(
                provider="gemini",
                api_key="test-api-key-1234567890",
                model="model",
            ),
            youtube_api_key="youtube-api-key-1234567890",
        )
        # Config validation happens at instantiation via Pydantic
        assert config.llm.provider == "gemini"

    def test_missing_youtube_key(self):
        with pytest.raises(
            ValidationError, match="String should have at least 20 characters"
        ):
            Config(
                llm=LLMConfig(
                    provider="gemini",
                    api_key="test-api-key-1234567890",
                    model="model",
                ),
                youtube_api_key="",
            )


class TestEmbeddingsConfig:
    def test_defaults(self):
        config = EmbeddingsConfig()
        assert config.model == "all-MiniLM-L6-v2"
        assert config.chunk_size == 1200
        assert config.chunk_overlap == 200

    def test_custom_values(self):
        config = EmbeddingsConfig(
            model="custom-model", chunk_size=2000, chunk_overlap=300
        )
        assert config.model == "custom-model"
        assert config.chunk_size == 2000
        assert config.chunk_overlap == 300

    def test_chunk_size_validation(self):
        with pytest.raises(ValidationError):
            EmbeddingsConfig(chunk_size=50)

    def test_chunk_overlap_validation(self):
        with pytest.raises(ValidationError):
            EmbeddingsConfig(chunk_overlap=-1)


class TestSearchConfig:
    def test_defaults(self):
        config = SearchConfig()
        assert config.top_k == 8

    def test_custom_top_k(self):
        config = SearchConfig(top_k=15)
        assert config.top_k == 15

    def test_top_k_validation(self):
        with pytest.raises(ValidationError):
            SearchConfig(top_k=0)
        with pytest.raises(ValidationError):
            SearchConfig(top_k=100)


class TestConfigWithEmbeddings:
    def test_config_includes_embeddings_defaults(self):
        config = Config(
            llm=LLMConfig(
                provider="gemini",
                api_key="test-api-key-1234567890",
                model="model",
            ),
            youtube_api_key="youtube-api-key-1234567890",
        )
        assert config.embeddings.model == "all-MiniLM-L6-v2"
        assert config.embeddings.chunk_size == 1200
        assert config.search.top_k == 8

    def test_load_config_with_embeddings(self):
        config_data = {
            "llm": {
                "provider": "gemini",
                "api_key": "test-api-key-1234567890",
                "model": "gemini-2.0-flash",
            },
            "youtube_api_key": "youtube-api-key-1234567890",
            "embeddings": {
                "model": "custom-embed-model",
                "chunk_size": 1500,
                "chunk_overlap": 250,
            },
            "search": {"top_k": 10},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = load_config(config_path)
            assert config.embeddings.model == "custom-embed-model"
            assert config.embeddings.chunk_size == 1500
            assert config.embeddings.chunk_overlap == 250
            assert config.search.top_k == 10
        finally:
            config_path.unlink()
