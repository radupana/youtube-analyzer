"""Simple file-based caching utilities."""

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# Cache configuration
DEFAULT_CACHE_MAX_AGE_HOURS = 24


def cache_path(key: str) -> Path:
    """
    Generate cache file path from key using SHA256 hash.

    Using hash-based approach prevents filename collisions and avoids
    issues with special characters across different filesystems.
    """
    cache_dir = Path(".cache")
    cache_dir.mkdir(exist_ok=True)
    # Use SHA256 to avoid collisions and handle all special characters
    safe_key = hashlib.sha256(key.encode()).hexdigest()
    return cache_dir / f"{safe_key}.json"


def get_from_cache(
    cache_key: str, max_age_hours: int = DEFAULT_CACHE_MAX_AGE_HOURS
) -> Any | None:
    """
    Load from .cache/ if exists and not expired.

    Args:
        cache_key: Unique identifier for cached data
        max_age_hours: Maximum age in hours before cache is considered stale

    Returns:
        Cached data if valid, None otherwise
    """
    file_path = cache_path(cache_key)

    if not file_path.exists():
        return None

    try:
        with open(file_path, encoding="utf-8") as f:
            cached = json.load(f)

        cached_at = datetime.fromisoformat(cached["timestamp"])
        age = datetime.now() - cached_at

        if age > timedelta(hours=max_age_hours):
            return None

        return cached["data"]
    except (json.JSONDecodeError, KeyError, ValueError):
        return None


def save_to_cache(cache_key: str, data: Any) -> None:
    """
    Save to .cache/ with timestamp.

    Args:
        cache_key: Unique identifier for cached data
        data: Data to cache (must be JSON serializable)
    """
    file_path = cache_path(cache_key)

    cache_entry = {"timestamp": datetime.now().isoformat(), "data": data}

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(cache_entry, f, indent=2)
