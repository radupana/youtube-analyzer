import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class LLMProvider:
    id: str
    name: str
    model: str
    api_key: str


@dataclass
class WhisperConfig:
    model: str = "base"
    fallback_enabled: bool = True


_providers: dict[str, LLMProvider] = {}
_current_provider_id: str | None = None
_default_provider_id: str | None = None
_whisper_config: WhisperConfig = WhisperConfig()


def load_config(config_path: str | Path = "config.yaml") -> None:
    global _providers, _current_provider_id, _default_provider_id, _whisper_config

    path = Path(config_path)
    if not path.exists():
        return

    with open(path) as f:
        config = yaml.safe_load(f)

    if config is None:
        return

    _providers = {}
    for provider_cfg in config.get("llm_providers", []):
        api_key = os.environ.get(provider_cfg["api_key_env"], "")
        if not api_key:
            continue
        provider = LLMProvider(
            id=provider_cfg["id"],
            name=provider_cfg["name"],
            model=provider_cfg["model"],
            api_key=api_key,
        )
        _providers[provider.id] = provider

    _default_provider_id = config.get("default_provider")
    if _default_provider_id and _default_provider_id in _providers:
        _current_provider_id = _default_provider_id
    elif _providers:
        _current_provider_id = next(iter(_providers))

    whisper_cfg = config.get("whisper", {})
    _whisper_config = WhisperConfig(
        model=whisper_cfg.get("model", "base"),
        fallback_enabled=whisper_cfg.get("fallback_enabled", True),
    )


def get_providers() -> list[LLMProvider]:
    return list(_providers.values())


def get_current_provider() -> LLMProvider | None:
    if _current_provider_id:
        return _providers.get(_current_provider_id)
    return None


def set_current_provider(provider_id: str) -> bool:
    global _current_provider_id
    if provider_id in _providers:
        _current_provider_id = provider_id
        return True
    return False


def get_provider_by_id(provider_id: str) -> LLMProvider | None:
    return _providers.get(provider_id)


def get_whisper_config() -> WhisperConfig:
    return _whisper_config
