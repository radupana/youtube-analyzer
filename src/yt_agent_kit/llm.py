"""LLM provider abstraction for chat functionality."""

from dataclasses import dataclass

from google import genai
from google.genai import types

from .config import LLMConfig


class LLMError(Exception):
    pass


@dataclass
class Message:
    role: str
    content: str


def call_gemini(messages: list[Message], config: LLMConfig) -> str:
    client = genai.Client(api_key=config.api_key)

    system_instruction = None
    contents: list[types.Content] = []

    for msg in messages:
        if msg.role == "system":
            system_instruction = msg.content
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
    if config.provider == "gemini":
        return call_gemini(messages, config)
    raise LLMError(f"Unsupported provider: {config.provider}")
