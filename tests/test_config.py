import os
import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from yt_agent_kit.config import Config, LLMConfig, load_config, resolve_env_vars


class TestResolveEnvVars:
    def test_simple_string(self):
        assert resolve_env_vars("hello") == "hello"

    def test_env_var_substitution(self):
        os.environ["TEST_VAR"] = "test_value"
        assert resolve_env_vars("${TEST_VAR}") == "test_value"

    def test_missing_env_var_raises(self):
        with pytest.raises(ValueError, match="TEST_MISSING is not set"):
            resolve_env_vars("${TEST_MISSING}")

    def test_dict_with_env_vars(self):
        os.environ["KEY1"] = "value1"
        os.environ["KEY2"] = "value2"
        input_dict = {"a": "${KEY1}", "b": "${KEY2}", "c": "static"}
        expected = {"a": "value1", "b": "value2", "c": "static"}
        assert resolve_env_vars(input_dict) == expected

    def test_nested_structure(self):
        os.environ["NESTED"] = "nested_value"
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
            "channel": "TestChannel",
            "llm": {
                "provider": "gemini",
                "api_key": "test-key",
                "model": "gemini-2.0-flash",
            },
            "youtube_api_key": "yt-key",
            "extractor": "test_extractor",
            "output_file": "out.json",
            "max_videos": 10,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = load_config(config_path)
            assert config.channel == "TestChannel"
            assert config.llm.provider == "gemini"
            assert config.llm.api_key == "test-key"
            assert config.youtube_api_key == "yt-key"
            assert config.max_videos == 10
        finally:
            config_path.unlink()

    def test_missing_config_file(self):
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config(Path("nonexistent.yaml"))

    def test_config_with_env_vars(self):
        os.environ["TEST_API_KEY"] = "secret-key"
        os.environ["YT_KEY"] = "youtube-key"

        config_data = {
            "channel": "TestChannel",
            "llm": {
                "provider": "gemini",
                "api_key": "${TEST_API_KEY}",
                "model": "gemini-2.0-flash",
            },
            "youtube_api_key": "${YT_KEY}",
            "extractor": "test",
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(config_data, f)
            config_path = Path(f.name)

        try:
            config = load_config(config_path)
            assert config.llm.api_key == "secret-key"
            assert config.youtube_api_key == "youtube-key"
        finally:
            config_path.unlink()

    def test_invalid_llm_provider(self):
        config_data = {
            "channel": "Test",
            "llm": {"provider": "invalid", "api_key": "key", "model": "model"},
            "youtube_api_key": "key",
            "extractor": "test",
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
            "channel": "Test",
            "llm": {"provider": "gemini", "api_key": "key", "model": "model"},
            "youtube_api_key": "key",
            "extractor": "test",
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
            channel="Test",
            llm=LLMConfig(provider="gemini", api_key="key", model="model"),
            youtube_api_key="yt-key",
            extractor="test",
        )
        # Config validation happens at instantiation via Pydantic
        assert config.channel == "Test"

    def test_missing_youtube_key(self):
        # Pydantic validates at instantiation, so we need to bypass validation
        # by creating a dict first
        with pytest.raises(
            ValidationError, match="String should have at least 1 character"
        ):
            Config(
                channel="Test",
                llm=LLMConfig(provider="gemini", api_key="key", model="model"),
                youtube_api_key="",
                extractor="test",
            )
