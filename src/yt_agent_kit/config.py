import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError

# Pre-compile regex pattern for environment variable substitution
ENV_VAR_PATTERN = re.compile(r"\$\{([^}]+)}")


class LLMConfig(BaseModel):
    provider: str = Field(..., pattern="^(gemini|openai|anthropic|custom)$")
    api_key: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)


class Config(BaseModel):
    channel: str = Field(..., min_length=1)
    llm: LLMConfig
    youtube_api_key: str = Field(..., min_length=1)
    extractor: str = Field(..., min_length=1)
    output_file: str = Field(default="results.json")
    max_videos: int = Field(default=50, ge=1, le=1000)


def resolve_env_vars(value: Any, depth: int = 0, max_depth: int = 100) -> Any:
    """
    Recursively resolve environment variables in strings, dicts, and lists.

    Args:
        value: The value to process
        depth: Current recursion depth (internal use)
        max_depth: Maximum allowed recursion depth to prevent stack overflow

    Raises:
        ValueError: If environment variable is not set or max depth exceeded
    """
    if depth > max_depth:
        raise ValueError(
            f"Maximum recursion depth ({max_depth}) exceeded in config resolution. "
            "This may indicate a malformed configuration file."
        )

    if isinstance(value, str):

        def replacer(match: re.Match[str]) -> str:
            env_var = match.group(1)
            env_value = os.environ.get(env_var)
            if env_value is None:
                raise ValueError(f"Environment variable {env_var} is not set")
            return env_value

        return ENV_VAR_PATTERN.sub(replacer, value)
    elif isinstance(value, dict):
        return {k: resolve_env_vars(v, depth + 1, max_depth) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_env_vars(item, depth + 1, max_depth) for item in value]
    return value


def load_config(config_path: Path | None = None) -> Config:
    """
    Load and validate configuration from a YAML file.

    Args:
        config_path: Path to config file (defaults to config.yaml)

    Returns:
        Validated Config object

    Raises:
        FileNotFoundError: If config file doesn't exist
        PermissionError: If config file can't be read due to permissions
        ValueError: If config is invalid or malformed
    """
    if config_path is None:
        config_path = Path("config.yaml")

    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            "Please copy config.example.yaml to config.yaml and fill in your settings"
        )

    try:
        with open(config_path, encoding="utf-8") as f:
            raw_config = yaml.safe_load(f)
    except PermissionError as e:
        raise PermissionError(
            f"Permission denied reading config file: {config_path}\n"
            "Please check file permissions."
        ) from e
    except UnicodeDecodeError as e:
        raise ValueError(
            f"Config file is not valid UTF-8: {config_path}\n"
            "Please ensure the file is saved with UTF-8 encoding."
        ) from e
    except yaml.YAMLError as e:
        raise ValueError(
            f"Invalid YAML syntax in config file: {config_path}\n{e}"
        ) from e
    except OSError as e:
        raise ValueError(f"Error reading config file: {config_path}\n{e}") from e

    # Validate structure before processing
    if not isinstance(raw_config, dict):
        raise ValueError(
            f"Config file must contain a YAML dictionary/object, got {type(raw_config).__name__}"
        )

    resolved_config = resolve_env_vars(raw_config)

    try:
        return Config(**resolved_config)
    except ValidationError as e:
        raise ValueError(f"Invalid configuration:\n{e}") from e
