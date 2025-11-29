"""Pattern loading and management service."""

from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Pattern:
    id: str
    name: str
    description: str
    icon: str
    category: str
    system_prompt: str
    user_prompt: str
    inputs: list[str] = field(
        default_factory=lambda: ["transcript", "video_title", "channel"]
    )
    output_format: str = "markdown"


@dataclass
class PatternSummary:
    id: str
    name: str
    description: str
    icon: str
    category: str


_patterns: dict[str, Pattern] = {}

REQUIRED_FIELDS = [
    "id",
    "name",
    "description",
    "icon",
    "category",
    "system_prompt",
    "user_prompt",
]


def load_patterns(patterns_dir: Path = Path("patterns")) -> None:
    """Load all patterns from YAML files. Raises on invalid YAML."""
    global _patterns
    _patterns = {}

    if not patterns_dir.exists():
        return

    for file in patterns_dir.glob("*.yaml"):
        with open(file) as f:
            data = yaml.safe_load(f)

        missing = [f for f in REQUIRED_FIELDS if f not in data]
        if missing:
            raise ValueError(f"Pattern {file.name} missing required fields: {missing}")

        pattern = Pattern(
            id=data["id"],
            name=data["name"],
            description=data["description"],
            icon=data["icon"],
            category=data["category"],
            system_prompt=data["system_prompt"],
            user_prompt=data["user_prompt"],
            inputs=data.get("inputs", ["transcript", "video_title", "channel"]),
            output_format=data.get("output_format", "markdown"),
        )
        _patterns[pattern.id] = pattern


def get_pattern(pattern_id: str) -> Pattern | None:
    return _patterns.get(pattern_id)


def list_patterns() -> list[PatternSummary]:
    return [
        PatternSummary(
            id=p.id,
            name=p.name,
            description=p.description,
            icon=p.icon,
            category=p.category,
        )
        for p in _patterns.values()
    ]


def validate_inputs(pattern: Pattern, available: dict[str, str | None]) -> list[str]:
    """Return list of missing required inputs."""
    return [inp for inp in pattern.inputs if not available.get(inp)]


def format_pattern_prompt(
    pattern: Pattern,
    video_title: str,
    channel: str,
    transcript: str,
) -> str:
    """Format the user prompt with video context."""
    return pattern.user_prompt.format(
        video_title=video_title,
        channel=channel,
        transcript=transcript,
    )
