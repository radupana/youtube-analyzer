import os
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field, ValidationError


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


def resolve_env_vars(value: Any) -> Any:
    if isinstance(value, str):
        pattern = re.compile(r"\$\{([^}]+)}")

        def replacer(match: re.Match[str]) -> str:
            env_var = match.group(1)
            env_value = os.environ.get(env_var)
            if env_value is None:
                raise ValueError(f"Environment variable {env_var} is not set")
            return env_value

        return pattern.sub(replacer, value)
    elif isinstance(value, dict):
        return {k: resolve_env_vars(v) for k, v in value.items()}
    elif isinstance(value, list):
        return [resolve_env_vars(item) for item in value]
    return value


def load_config(config_path: Path | None = None) -> Config:
    if config_path is None:
        config_path = Path("config.yaml")

    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found: {config_path}\n"
            "Please copy config.example.yaml to config.yaml and fill in your settings"
        )

    with open(config_path, encoding="utf-8") as f:
        raw_config = yaml.safe_load(f)

    resolved_config = resolve_env_vars(raw_config)

    try:
        return Config(**resolved_config)
    except ValidationError as e:
        raise ValueError(f"Invalid configuration:\n{e}") from e
