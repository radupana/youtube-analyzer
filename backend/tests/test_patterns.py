"""Tests for pattern loading and management service."""

import pytest
import yaml

from app.services.patterns import (
    Pattern,
    PatternSummary,
    format_pattern_prompt,
    get_pattern,
    list_patterns,
    load_patterns,
    validate_inputs,
)


class TestPatternLoading:
    def test_load_patterns_from_directory(self, tmp_path):
        pattern_data = {
            "id": "test_pattern",
            "name": "Test Pattern",
            "description": "A test pattern",
            "icon": "🧪",
            "category": "test",
            "system_prompt": "You are a test assistant.",
            "user_prompt": "Analyze: {transcript}",
        }
        (tmp_path / "test.yaml").write_text(yaml.dump(pattern_data))

        load_patterns(tmp_path)

        pattern = get_pattern("test_pattern")
        assert pattern is not None
        assert pattern.name == "Test Pattern"
        assert pattern.icon == "🧪"
        assert pattern.category == "test"

    def test_load_patterns_with_custom_inputs(self, tmp_path):
        pattern_data = {
            "id": "custom_inputs",
            "name": "Custom Inputs",
            "description": "Pattern with custom inputs",
            "icon": "📥",
            "category": "test",
            "system_prompt": "System",
            "user_prompt": "Title: {video_title}",
            "inputs": ["video_title"],
        }
        (tmp_path / "custom_inputs.yaml").write_text(yaml.dump(pattern_data))

        load_patterns(tmp_path)

        pattern = get_pattern("custom_inputs")
        assert pattern is not None
        assert pattern.inputs == ["video_title"]

    def test_load_patterns_empty_directory(self, tmp_path):
        load_patterns(tmp_path)
        assert list_patterns() == []

    def test_load_patterns_nonexistent_directory(self, tmp_path):
        nonexistent = tmp_path / "nonexistent"
        load_patterns(nonexistent)
        assert list_patterns() == []

    def test_pattern_validation_missing_fields(self, tmp_path):
        invalid = {"id": "incomplete", "name": "Incomplete"}
        (tmp_path / "bad.yaml").write_text(yaml.dump(invalid))

        with pytest.raises(ValueError, match="missing required fields"):
            load_patterns(tmp_path)

    def test_load_multiple_patterns(self, tmp_path):
        for i in range(3):
            pattern_data = {
                "id": f"pattern_{i}",
                "name": f"Pattern {i}",
                "description": f"Description {i}",
                "icon": "📄",
                "category": "test",
                "system_prompt": "System",
                "user_prompt": "{transcript}",
            }
            (tmp_path / f"pattern_{i}.yaml").write_text(yaml.dump(pattern_data))

        load_patterns(tmp_path)

        patterns = list_patterns()
        assert len(patterns) == 3


class TestListPatterns:
    def test_list_patterns_returns_summaries(self, tmp_path):
        pattern_data = {
            "id": "summary_test",
            "name": "Summary Test",
            "description": "Test description",
            "icon": "📋",
            "category": "analysis",
            "system_prompt": "System prompt here",
            "user_prompt": "User prompt: {transcript}",
        }
        (tmp_path / "test.yaml").write_text(yaml.dump(pattern_data))

        load_patterns(tmp_path)

        patterns = list_patterns()
        assert len(patterns) == 1
        assert isinstance(patterns[0], PatternSummary)
        assert patterns[0].id == "summary_test"
        assert patterns[0].name == "Summary Test"
        assert patterns[0].description == "Test description"


class TestGetPattern:
    def test_get_existing_pattern(self, tmp_path):
        pattern_data = {
            "id": "existing",
            "name": "Existing",
            "description": "An existing pattern",
            "icon": "✅",
            "category": "test",
            "system_prompt": "System",
            "user_prompt": "{transcript}",
        }
        (tmp_path / "existing.yaml").write_text(yaml.dump(pattern_data))
        load_patterns(tmp_path)

        pattern = get_pattern("existing")
        assert pattern is not None
        assert pattern.id == "existing"

    def test_get_nonexistent_pattern(self, tmp_path):
        load_patterns(tmp_path)
        pattern = get_pattern("nonexistent")
        assert pattern is None


class TestInputValidation:
    def test_validate_inputs_all_present(self):
        pattern = Pattern(
            id="test",
            name="T",
            description="D",
            icon="I",
            category="C",
            system_prompt="S",
            user_prompt="U",
            inputs=["transcript", "video_title"],
        )
        available = {"transcript": "text", "video_title": "title", "channel": "ch"}

        missing = validate_inputs(pattern, available)
        assert missing == []

    def test_validate_inputs_missing_one(self):
        pattern = Pattern(
            id="test",
            name="T",
            description="D",
            icon="I",
            category="C",
            system_prompt="S",
            user_prompt="U",
            inputs=["transcript", "video_title"],
        )
        available = {"transcript": "text", "channel": "ch"}

        missing = validate_inputs(pattern, available)
        assert missing == ["video_title"]

    def test_validate_inputs_missing_all(self):
        pattern = Pattern(
            id="test",
            name="T",
            description="D",
            icon="I",
            category="C",
            system_prompt="S",
            user_prompt="U",
            inputs=["transcript", "video_title"],
        )
        available = {"channel": "ch"}

        missing = validate_inputs(pattern, available)
        assert "transcript" in missing
        assert "video_title" in missing

    def test_validate_inputs_none_value_counts_as_missing(self):
        pattern = Pattern(
            id="test",
            name="T",
            description="D",
            icon="I",
            category="C",
            system_prompt="S",
            user_prompt="U",
            inputs=["transcript"],
        )
        available = {"transcript": None}

        missing = validate_inputs(pattern, available)
        assert missing == ["transcript"]


class TestFormatPatternPrompt:
    def test_format_all_variables(self):
        pattern = Pattern(
            id="test",
            name="Test",
            description="Test",
            icon="🧪",
            category="test",
            system_prompt="System",
            user_prompt="Title: {video_title}\nChannel: {channel}\n{transcript}",
        )

        result = format_pattern_prompt(
            pattern,
            video_title="My Video",
            channel="My Channel",
            transcript="Hello world",
        )

        assert "My Video" in result
        assert "My Channel" in result
        assert "Hello world" in result

    def test_format_partial_variables(self):
        pattern = Pattern(
            id="test",
            name="Test",
            description="Test",
            icon="🧪",
            category="test",
            system_prompt="System",
            user_prompt="Transcript only:\n{transcript}",
        )

        result = format_pattern_prompt(
            pattern,
            video_title="Ignored",
            channel="Ignored",
            transcript="Content here",
        )

        assert "Content here" in result
        assert "Ignored" not in result


class TestPatternDataclasses:
    def test_pattern_defaults(self):
        pattern = Pattern(
            id="test",
            name="Test",
            description="Desc",
            icon="I",
            category="C",
            system_prompt="S",
            user_prompt="U",
        )

        assert pattern.inputs == ["transcript", "video_title", "channel"]
        assert pattern.output_format == "markdown"
