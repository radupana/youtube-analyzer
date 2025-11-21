"""LLM provider abstraction for chat functionality."""

from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types

from .config import LLMConfig

# Cache Gemini clients by API key to avoid recreating on every call
_gemini_clients: dict[str, genai.Client] = {}


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
