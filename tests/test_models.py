"""Tests for Pydantic data models (validation, serialization, business rules).

Test Coverage Goals:
- Exercise model validation
- AudioConfig model validation
- BreathingPattern model validation
- Segment model validation
- VoiceConfig model validation
- NarrationScript model validation and file I/O
"""

import json
import pytest
from pathlib import Path
from pydantic import ValidationError

from voice_generation.core.models import (
    Exercise,
    AudioConfig,
    BreathingPattern,
    Segment,
    VoiceConfig,
    NarrationScript,
)


# ============================================================================
# Exercise Model Tests
# ============================================================================


class TestExerciseModel:
    """Test Exercise model validation."""

    def test_valid_exercise(self):
        """Test creating valid exercise with all fields."""
        exercise = Exercise(
            id="test-ex-v1",
            title="Test Exercise",
            description="A test exercise",
            category="testing",
            tags=["test", "unit"],
            duration_seconds=60,
        )
        assert exercise.id == "test-ex-v1"
        assert exercise.title == "Test Exercise"
        assert exercise.duration_seconds == 60

    def test_exercise_minimal_fields(self):
        """Test exercise with only required fields."""
        exercise = Exercise(
            id="minimal-v1",
            title="Minimal",
        )
        assert exercise.id == "minimal-v1"
        assert exercise.title == "Minimal"
        assert exercise.description is None
        assert exercise.tags == []

    def test_exercise_id_validation_alphanumeric(self):
        """Test exercise ID must be alphanumeric with hyphens/underscores."""
        # Valid IDs
        Exercise(id="valid-id-123", title="Test")
        Exercise(id="valid_id_456", title="Test")
        Exercise(id="validid789", title="Test")

        # Invalid IDs with special characters
        with pytest.raises(ValidationError) as exc_info:
            Exercise(id="invalid@id", title="Test")
        assert "alphanumeric" in str(exc_info.value).lower()

    def test_exercise_empty_id_raises_error(self):
        """Test empty exercise ID raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            Exercise(id="", title="Test")
        assert "at least 1 character" in str(exc_info.value).lower()

    def test_exercise_empty_title_raises_error(self):
        """Test empty title raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            Exercise(id="test-v1", title="")
        assert "at least 1 character" in str(exc_info.value).lower()

    def test_exercise_serialization(self):
        """Test exercise can be serialized to dict."""
        exercise = Exercise(
            id="test-v1",
            title="Test",
            tags=["a", "b"],
        )
        data = exercise.model_dump()
        assert data["id"] == "test-v1"
        assert data["tags"] == ["a", "b"]


# ============================================================================
# AudioConfig Model Tests
# ============================================================================


class TestAudioConfigModel:
    """Test AudioConfig model validation."""

    def test_valid_audio_config(self):
        """Test creating valid audio config."""
        config = AudioConfig(
            fragments=["Fragment 1.", "Fragment 2."],
            max_duration_ms=10000,
        )
        assert len(config.fragments) == 2
        assert config.max_duration_ms == 10000

    def test_audio_config_with_timing(self):
        """Test audio config with timing parameter."""
        config = AudioConfig(
            fragments=["Breathe in."],
            max_duration_ms=5000,
            timing="inhale_phase",
        )
        assert config.timing == "inhale_phase"

    def test_audio_config_empty_fragments_raises_error(self):
        """Test empty fragments list raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AudioConfig(fragments=[], max_duration_ms=1000)
        assert "at least 1 item" in str(exc_info.value).lower()

    def test_audio_config_invalid_timing_raises_error(self):
        """Test invalid timing value raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AudioConfig(
                fragments=["Test"],
                max_duration_ms=1000,
                timing="invalid_timing",
            )
        assert "timing" in str(exc_info.value).lower()

    def test_audio_config_zero_duration_raises_error(self):
        """Test zero max_duration_ms raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AudioConfig(fragments=["Test"], max_duration_ms=0)
        assert "greater than 0" in str(exc_info.value).lower()

    def test_audio_config_negative_duration_raises_error(self):
        """Test negative max_duration_ms raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            AudioConfig(fragments=["Test"], max_duration_ms=-1000)
        assert "greater than 0" in str(exc_info.value).lower()


# ============================================================================
# BreathingPattern Model Tests
# ============================================================================


class TestBreathingPatternModel:
    """Test BreathingPattern model validation."""

    def test_breathing_pattern_with_preset(self):
        """Test creating breathing pattern with preset."""
        pattern = BreathingPattern(pattern="calm", repetitions=10)
        assert pattern.pattern == "calm"
        assert pattern.repetitions == 10

    def test_breathing_pattern_with_explicit_values(self):
        """Test creating breathing pattern with explicit inhale/exhale."""
        pattern = BreathingPattern(
            inhale_ms=4000,
            exhale_ms=6000,
            repetitions=10,
        )
        assert pattern.inhale_ms == 4000
        assert pattern.exhale_ms == 6000

    def test_breathing_pattern_with_holds(self):
        """Test breathing pattern with hold periods."""
        pattern = BreathingPattern(
            inhale_ms=4000,
            hold_in_ms=2000,
            exhale_ms=6000,
            hold_out_ms=1000,
            repetitions=5,
        )
        assert pattern.hold_in_ms == 2000
        assert pattern.hold_out_ms == 1000

    def test_breathing_pattern_with_duration(self):
        """Test breathing pattern with total duration (natural breathing)."""
        pattern = BreathingPattern(
            duration_ms=60000,
            repetitions=1,
        )
        assert pattern.duration_ms == 60000

    def test_breathing_pattern_missing_both_raises_error(self):
        """Test breathing pattern with neither preset nor explicit values raises error."""
        with pytest.raises(ValidationError) as exc_info:
            BreathingPattern(repetitions=10)
        # Check that the error mentions pattern or explicit values
        error_msg = str(exc_info.value).lower()
        assert "pattern" in error_msg and ("explicit" in error_msg or "inhale" in error_msg)

    def test_breathing_pattern_invalid_preset_raises_error(self):
        """Test invalid preset pattern raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            BreathingPattern(pattern="invalid_pattern", repetitions=10)
        assert "pattern" in str(exc_info.value).lower()

    def test_breathing_pattern_zero_repetitions_raises_error(self):
        """Test zero repetitions raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            BreathingPattern(inhale_ms=4000, exhale_ms=6000, repetitions=0)
        # Check that error mentions repetitions must be >= 1
        error_msg = str(exc_info.value).lower()
        assert "repetitions" in error_msg and ("greater" in error_msg or "at least 1" in error_msg)


# ============================================================================
# Segment Model Tests
# ============================================================================


class TestSegmentModel:
    """Test Segment model validation."""

    def test_narration_segment(self):
        """Test creating narration-type segment."""
        audio = AudioConfig(fragments=["Hello"], max_duration_ms=5000)
        segment = Segment(
            id="intro",
            type="narration",
            audio=audio,
        )
        assert segment.type == "narration"
        assert segment.breathing is None

    def test_breathing_cycle_segment(self):
        """Test creating breathing_cycle-type segment."""
        breathing = BreathingPattern(inhale_ms=4000, exhale_ms=6000, repetitions=10)
        audio = AudioConfig(fragments=["Breathe"], max_duration_ms=8000)
        segment = Segment(
            id="practice",
            type="breathing_cycle",
            breathing=breathing,
            audio=audio,
        )
        assert segment.type == "breathing_cycle"
        assert segment.breathing is not None

    def test_segment_empty_id_raises_error(self):
        """Test empty segment ID raises validation error."""
        audio = AudioConfig(fragments=["Test"], max_duration_ms=1000)
        with pytest.raises(ValidationError) as exc_info:
            Segment(id="", type="narration", audio=audio)
        assert "at least 1 character" in str(exc_info.value).lower()

    def test_segment_invalid_type_raises_error(self):
        """Test invalid segment type raises validation error."""
        audio = AudioConfig(fragments=["Test"], max_duration_ms=1000)
        with pytest.raises(ValidationError) as exc_info:
            Segment(id="test", type="invalid_type", audio=audio)
        assert "type" in str(exc_info.value).lower()

    def test_breathing_cycle_without_breathing_raises_error(self):
        """Test breathing_cycle segment without breathing pattern raises error."""
        audio = AudioConfig(fragments=["Test"], max_duration_ms=1000)
        with pytest.raises(ValidationError) as exc_info:
            Segment(id="test", type="breathing_cycle", audio=audio)
        assert "breathing" in str(exc_info.value).lower()


# ============================================================================
# VoiceConfig Model Tests
# ============================================================================


class TestVoiceConfigModel:
    """Test VoiceConfig model validation."""

    def test_valid_voice_config(self):
        """Test creating valid voice config."""
        config = VoiceConfig(
            provider="elevenlabs",
            voice_id="test_voice_123",
            model="eleven_multilingual_v2",
            stability=0.7,
            similarity_boost=0.75,
        )
        assert config.provider == "elevenlabs"
        assert config.stability == 0.7

    def test_voice_config_minimal_fields(self):
        """Test voice config with only required field."""
        config = VoiceConfig(provider="elevenlabs")
        assert config.provider == "elevenlabs"
        assert config.voice_id is None

    def test_voice_config_stability_range_validation(self):
        """Test stability must be between 0 and 1."""
        # Valid values
        VoiceConfig(provider="elevenlabs", stability=0.0)
        VoiceConfig(provider="elevenlabs", stability=0.5)
        VoiceConfig(provider="elevenlabs", stability=1.0)

        # Invalid values
        with pytest.raises(ValidationError):
            VoiceConfig(provider="elevenlabs", stability=-0.1)
        with pytest.raises(ValidationError):
            VoiceConfig(provider="elevenlabs", stability=1.1)

    def test_voice_config_similarity_boost_range_validation(self):
        """Test similarity_boost must be between 0 and 1."""
        # Valid values
        VoiceConfig(provider="elevenlabs", similarity_boost=0.0)
        VoiceConfig(provider="elevenlabs", similarity_boost=1.0)

        # Invalid values
        with pytest.raises(ValidationError):
            VoiceConfig(provider="elevenlabs", similarity_boost=-0.1)
        with pytest.raises(ValidationError):
            VoiceConfig(provider="elevenlabs", similarity_boost=1.1)


# ============================================================================
# NarrationScript Model Tests
# ============================================================================


class TestNarrationScriptModel:
    """Test NarrationScript model validation and file I/O."""

    def test_valid_narration_script(
        self,
        sample_exercise,
        sample_narration_segment,
        sample_voice_config,
    ):
        """Test creating valid narration script."""
        script = NarrationScript(
            exercise=sample_exercise,
            segments=[sample_narration_segment],
            voice_config=sample_voice_config,
        )
        assert len(script.segments) == 1
        assert script.exercise.id == "test-exercise-v1"

    def test_narration_script_empty_segments_raises_error(
        self,
        sample_exercise,
        sample_voice_config,
    ):
        """Test empty segments list raises validation error."""
        with pytest.raises(ValidationError) as exc_info:
            NarrationScript(
                exercise=sample_exercise,
                segments=[],
                voice_config=sample_voice_config,
            )
        assert "at least 1 item" in str(exc_info.value).lower()

    def test_narration_script_from_file(self, sample_json_file):
        """Test loading narration script from JSON file."""
        script = NarrationScript.from_file(sample_json_file)
        assert script.exercise.id == "test-exercise-v1"
        assert len(script.segments) == 2

    def test_narration_script_from_file_not_found(self):
        """Test loading from non-existent file raises error."""
        with pytest.raises(FileNotFoundError):
            NarrationScript.from_file("nonexistent.json")

    def test_narration_script_from_invalid_json(self, invalid_json_file):
        """Test loading from malformed JSON raises JSONDecodeError."""
        with pytest.raises(json.JSONDecodeError):
            NarrationScript.from_file(invalid_json_file)

    def test_narration_script_from_malformed_json(self, malformed_json_file):
        """Test loading from malformed JSON raises error."""
        with pytest.raises(json.JSONDecodeError):
            NarrationScript.from_file(malformed_json_file)

    def test_narration_script_estimate_duration(
        self,
        sample_exercise,
        sample_breathing_segment,
        sample_voice_config,
    ):
        """Test duration estimation for script."""
        script = NarrationScript(
            exercise=sample_exercise,
            segments=[sample_breathing_segment, sample_breathing_segment],
            voice_config=sample_voice_config,
        )
        # Each breathing segment: (4000 + 6000) * 5 = 50000ms
        # Two segments = 100000ms
        estimated = script.estimate_total_duration_ms()
        assert estimated == 100000

    def test_narration_script_serialization(
        self,
        sample_exercise,
        sample_narration_segment,
        sample_voice_config,
    ):
        """Test narration script can be serialized to dict."""
        script = NarrationScript(
            exercise=sample_exercise,
            segments=[sample_narration_segment],
            voice_config=sample_voice_config,
        )
        data = script.model_dump()
        assert "exercise" in data
        assert "segments" in data
        assert "voice_config" in data
        assert isinstance(data["segments"], list)
