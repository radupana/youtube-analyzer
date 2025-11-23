"""LLM provider abstraction for chat functionality."""

import logging
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types

from .config import LLMConfig

logger = logging.getLogger(__name__)

DEFAULT_CONTEXT_LIMIT = 32_000
_gemini_clients: dict[str, genai.Client] = {}
_context_limit_cache: dict[str, int] = {}


class LLMError(Exception):
    pass


@dataclass
class Message:
    role: str
    content: str


def _get_gemini_client(api_key: str) -> genai.Client:
    """Get or create a cached Gemini client for the given API key."""
    if api_key not in _gemini_clients:
        _gemini_clients[api_key] = genai.Client(api_key=api_key)
    return _gemini_clients[api_key]


def _fetch_gemini_context_limit(config: LLMConfig) -> int | None:
    """Fetch context limit from Gemini API for the configured model."""
    try:
        client = _get_gemini_client(config.api_key)
        model_info = client.models.get(model=config.model)
        if hasattr(model_info, "input_token_limit") and model_info.input_token_limit:
            return int(model_info.input_token_limit)
    except Exception as e:
        logger.warning(f"Failed to fetch model info from Gemini API: {e}")
    return None


def get_context_limit(config: LLMConfig) -> int:
    """Get context limit for the configured model.

    Resolution order:
    1. Explicit config.context_limit if set
    2. Cached value for this model
    3. Fetch from Gemini API (if provider is gemini)
    4. Conservative default (32,000 tokens)
    """
    if config.context_limit is not None:
        return config.context_limit

    cache_key = f"{config.provider}:{config.model}"
    if cache_key in _context_limit_cache:
        return _context_limit_cache[cache_key]

    if config.provider == "gemini":
        limit = _fetch_gemini_context_limit(config)
        if limit is not None:
            _context_limit_cache[cache_key] = limit
            return limit

    logger.warning(
        f"Could not determine context limit for {config.provider}/{config.model}, "
        f"using default {DEFAULT_CONTEXT_LIMIT}. Set llm.context_limit in config to override."
    )
    _context_limit_cache[cache_key] = DEFAULT_CONTEXT_LIMIT
    return DEFAULT_CONTEXT_LIMIT


def call_gemini(messages: list[Message], config: LLMConfig) -> str:
    """Call Gemini API with the given messages.

    Note: Only the last system message is used as the system instruction.
    Multiple system messages will result in only the final one being applied.
    """
    client = _get_gemini_client(config.api_key)

    system_instruction: str | None = None
    contents: list[Any] = []  # types.Content, but list invariance causes mypy issues

    for msg in messages:
        if msg.role == "system":
            system_instruction = msg.content  # Last system message wins
        else:
            contents.append(
                types.Content(
                    role="user" if msg.role == "user" else "model",
                    parts=[types.Part(text=msg.content)],
                )
            )

    try:
        response = client.models.generate_content(
            model=config.model,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7,
            ),
        )
        if response.text:
            return str(response.text)
        raise LLMError("Empty response from Gemini")
    except LLMError:
        raise
    except Exception as e:
        raise LLMError(f"Gemini API error: {e}") from e


def call_llm(messages: list[Message], config: LLMConfig) -> str:
    """Route LLM calls to the appropriate provider.

    Currently supported: gemini
    Future: openai, anthropic (see config.py for provider options)
    """
    if config.provider == "gemini":
        return call_gemini(messages, config)
    # TODO: Add openai and anthropic providers when needed
    raise LLMError(f"Unsupported provider: {config.provider}")
