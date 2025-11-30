import os
from dataclasses import dataclass, field
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
    unload_timeout: int = 300


@dataclass
class RagConfig:
    chunk_size: int = 500
    chunk_overlap: int = 50
    top_k: int = 10
    max_context_tokens: int = 4000


@dataclass
class TranscriptConfig:
    preferred_languages: list[str] = field(default_factory=lambda: ["en"])
    prefer_manual: bool = True


@dataclass
class ProxyConfig:
    # For generic HTTP proxy (e.g., Webshare free with IP auth)
    host: str | None = None
    port: int | None = None
    # For Webshare rotating residential (credentials from env)
    type: str | None = None  # "webshare_rotating"
    username: str | None = None  # from WEBSHARE_PROXY_USERNAME
    password: str | None = None  # from WEBSHARE_PROXY_PASSWORD


_providers: dict[str, LLMProvider] = {}
_current_provider_id: str | None = None
_default_provider_id: str | None = None
_whisper_config: WhisperConfig = WhisperConfig()
_rag_config: RagConfig = RagConfig()
_transcript_config: TranscriptConfig = TranscriptConfig()
_proxy_config: ProxyConfig = ProxyConfig()


def load_config(config_path: str | Path = "config.yaml") -> None:
    global _providers, _current_provider_id, _default_provider_id
    global _whisper_config, _rag_config, _transcript_config, _proxy_config

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
    unload_timeout = whisper_cfg.get("unload_timeout", 300)
    if not isinstance(unload_timeout, int) or unload_timeout < 0:
        raise ValueError(
            f"whisper.unload_timeout must be non-negative int, got {unload_timeout}"
        )
    _whisper_config = WhisperConfig(
        model=whisper_cfg.get("model", "base"),
        fallback_enabled=whisper_cfg.get("fallback_enabled", True),
        unload_timeout=unload_timeout,
    )

    rag_cfg = config.get("rag", {})
    _rag_config = RagConfig(
        chunk_size=rag_cfg.get("chunk_size", 500),
        chunk_overlap=rag_cfg.get("chunk_overlap", 50),
        top_k=rag_cfg.get("top_k", 10),
        max_context_tokens=rag_cfg.get("max_context_tokens", 4000),
    )

    transcript_cfg = config.get("transcripts", {})
    _transcript_config = TranscriptConfig(
        preferred_languages=transcript_cfg.get("preferred_languages", ["en"]),
        prefer_manual=transcript_cfg.get("prefer_manual", True),
    )

    proxy_cfg = config.get("proxy", {})
    _proxy_config = ProxyConfig(
        host=proxy_cfg.get("host"),
        port=proxy_cfg.get("port"),
        type=proxy_cfg.get("type"),
        username=os.environ.get("WEBSHARE_PROXY_USERNAME"),
        password=os.environ.get("WEBSHARE_PROXY_PASSWORD"),
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


def get_rag_config() -> RagConfig:
    return _rag_config


def get_transcript_config() -> TranscriptConfig:
    return _transcript_config


def get_proxy_config() -> ProxyConfig:
    return _proxy_config
