from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Settings from environment variables only - no config files."""

    model_config = SettingsConfigDict(
        # NO .env file reading - Docker Compose handles env vars
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    api_v1_str: str = "/api/v1"
    project_name: str = "YouTube Analyzer API"

    # Required from environment
    youtube_api_key: str = Field(..., validation_alias="YOUTUBE_API_KEY")
    gemini_api_key: str = Field(..., validation_alias="GEMINI_API_KEY")

    # Optional with defaults
    cors_origins: list[str] = Field(
        default=["http://localhost:3000", "http://127.0.0.1:3000"]
    )

    max_videos_default: int = Field(default=50, validation_alias="MAX_VIDEOS")
    whisper_model: str = Field(default="base", validation_alias="WHISPER_MODEL")
    enable_whisper_fallback: bool = Field(
        default=True, validation_alias="ENABLE_WHISPER_FALLBACK"
    )
    llm_model: str = Field(default="gemini-2.0-flash", validation_alias="LLM_MODEL")


@lru_cache
def get_settings() -> Settings:
    return Settings()
