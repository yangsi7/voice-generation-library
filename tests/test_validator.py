"""Tests for NarrationValidator (business rule validation).

Test Coverage Goals:
- Exercise duration validation
- Segment validation (unique IDs)
- Breathing pattern validation (timing constraints)
- Audio config validation (text length warnings)
- Timing feasibility checks
"""

import pytest

from voice_generation.core.validator import NarrationValidator
from voice_generation.core.models import (
    Exercise,
    AudioConfig,
    BreathingPattern,
    Segment,
    VoiceConfig,
    NarrationScript,
)


# ============================================================================
# Exercise Duration Validation Tests
# ============================================================================


class TestExerciseDurationValidation:
    """Test exercise duration validation rules."""

    def test_valid_exercise_duration(self):
        """Test exercise with reasonable duration passes validation."""
        validator = NarrationValidator()

        # 5-minute exercise (300s)
        exercise = Exercise(id="test-v1", title="Test", duration_seconds=300)
        breathing = BreathingPattern(inhale_ms=4000, exhale_ms=6000, repetitions=30)
        audio = AudioConfig(fragments=["Test"], max_duration_ms=8000)
        segment = Segment(id="practice", type="breathing_cycle", breathing=breathing, audio=audio)
        voice = VoiceConfig(provider="elevenlabs")
        script = NarrationScript(exercise=exercise, segments=[segment], voice_config=voice)

        result = validator.validate(script)
        assert result.is_valid
        assert len(result.errors) == 0

    def test_exercise_duration_too_long(self):
        """Test exercise exceeding 1 hour (3600s) raises error."""
        validator = NarrationValidator()

        # 2-hour exercise (7200s) - should fail
        exercise = Exercise(id="test-v1", title="Test", duration_seconds=7200)
        breathing = BreathingPattern(inhale_ms=4000, exhale_ms=6000, repetitions=720)  # 2 hours worth
        audio = AudioConfig(fragments=["Test"], max_duration_ms=8000)
        segment = Segment(id="practice", type="breathing_cycle", breathing=breathing, audio=audio)
        voice = VoiceConfig(provider="elevenlabs")
        script = NarrationScript(exercise=exercise, segments=[segment], voice_config=voice)

        result = validator.validate(script)
        assert not result.is_valid
        assert len(result.errors) > 0
        assert any("too long" in err.lower() for err in result.errors)

    def test_exercise_duration_mismatch_warning(self):
        """Test warning when specified duration doesn't match estimated duration."""
        validator = NarrationValidator()

        # Specify 600s but actual is 300s (diff > 30s tolerance)
        exercise = Exercise(id="test-v1", title="Test", duration_seconds=600)
        breathing = BreathingPattern(inhale_ms=4000, exhale_ms=6000, repetitions=30)  # 300s
        audio = AudioConfig(fragments=["Test"], max_duration_ms=8000)
        segment = Segment(id="practice", type="breathing_cycle", breathing=breathing, audio=audio)
        voice = VoiceConfig(provider="elevenlabs")
        script = NarrationScript(exercise=exercise, segments=[segment], voice_config=voice)

        result = validator.validate(script)
        assert result.is_valid  # Still valid, just a warning
        assert len(result.warnings) > 0
        assert any("mismatch" in warn.lower() for warn in result.warnings)


# ============================================================================
# Segment Validation Tests
# ============================================================================


class TestSegmentValidation:
    """Test segment-level validation rules."""

    def test_duplicate_segment_ids_error(self):
        """Test duplicate segment IDs raise validation error."""
        validator = NarrationValidator()

        exercise = Exercise(id="test-v1", title="Test")
        audio = AudioConfig(fragments=["Test"], max_duration_ms=5000)
        segment1 = Segment(id="duplicate", type="narration", audio=audio)
        segment2 = Segment(id="duplicate", type="narration", audio=audio)  # Same ID!
        voice = VoiceConfig(provider="elevenlabs")
        script = NarrationScript(exercise=exercise, segments=[segment1, segment2], voice_config=voice)

        result = validator.validate(script)
        assert not result.is_valid
        assert len(result.errors) > 0
        assert any("duplicate" in err.lower() for err in result.errors)

    def test_unique_segment_ids_pass(self):
        """Test unique segment IDs pass validation."""
        validator = NarrationValidator()

        exercise = Exercise(id="test-v1", title="Test")
        audio = AudioConfig(fragments=["Test"], max_duration_ms=5000)
        segment1 = Segment(id="intro", type="narration", audio=audio)
        segment2 = Segment(id="practice", type="narration", audio=audio)
        voice = VoiceConfig(provider="elevenlabs")
        script = NarrationScript(exercise=exercise, segments=[segment1, segment2], voice_config=voice)

        result = validator.validate(script)
        assert result.is_valid


# ============================================================================
# Breathing Pattern Validation Tests
# ============================================================================


class TestBreathingPatternValidation:
    """Test breathing pattern timing validation."""

    def test_breathing_cycle_too_short_error(self):
        """Test breathing cycle < 1s (1000ms) raises error."""
        validator = NarrationValidator()

        exercise = Exercise(id="test-v1", title="Test")
        breathing = BreathingPattern(inhale_ms=300, exhale_ms=400, repetitions=10)  # 700ms total
        audio = AudioConfig(fragments=["Test"], max_duration_ms=500)
        segment = Segment(id="practice", type="breathing_cycle", breathing=breathing, audio=audio)
        voice = VoiceConfig(provider="elevenlabs")
        script = NarrationScript(exercise=exercise, segments=[segment], voice_config=voice)

        result = validator.validate(script)
        assert not result.is_valid
        assert any("too short" in err.lower() for err in result.errors)

    def test_breathing_cycle_very_long_warning(self):
        """Test breathing cycle > 60s (60000ms) raises warning."""
        validator = NarrationValidator()

        exercise = Exercise(id="test-v1", title="Test")
        breathing = BreathingPattern(duration_ms=70000, repetitions=1)  # 70s natural breathing
        audio = AudioConfig(fragments=["Test"], max_duration_ms=5000)
        segment = Segment(id="practice", type="breathing_cycle", breathing=breathing, audio=audio)
        voice = VoiceConfig(provider="elevenlabs")
        script = NarrationScript(exercise=exercise, segments=[segment], voice_config=voice)

        result = validator.validate(script)
        assert result.is_valid  # Still valid, just warning
        assert len(result.warnings) > 0
        assert any("very long" in warn.lower() for warn in result.warnings)

    def test_high_repetitions_warning(self):
        """Test breathing pattern with > 100 repetitions raises warning."""
        validator = NarrationValidator()

        exercise = Exercise(id="test-v1", title="Test")
        breathing = BreathingPattern(inhale_ms=4000, exhale_ms=6000, repetitions=150)
        audio = AudioConfig(fragments=["Test"], max_duration_ms=8000)
        segment = Segment(id="practice", type="breathing_cycle", breathing=breathing, audio=audio)
        voice = VoiceConfig(provider="elevenlabs")
        script = NarrationScript(exercise=exercise, segments=[segment], voice_config=voice)

        result = validator.validate(script)
        assert result.is_valid
        assert len(result.warnings) > 0
        assert any("repetition" in warn.lower() for warn in result.warnings)


# ============================================================================
# Audio Config Validation Tests
# ============================================================================


class TestAudioConfigValidation:
    """Test audio configuration validation rules."""

    def test_many_fragments_warning(self):
        """Test > 20 audio fragments raises warning."""
        validator = NarrationValidator()

        exercise = Exercise(id="test-v1", title="Test")
        # Create 25 fragments
        fragments = [f"Fragment {i}" for i in range(25)]
        audio = AudioConfig(fragments=fragments, max_duration_ms=50000)
        segment = Segment(id="test", type="narration", audio=audio)
        voice = VoiceConfig(provider="elevenlabs")
        script = NarrationScript(exercise=exercise, segments=[segment], voice_config=voice)

        result = validator.validate(script)
        assert result.is_valid
        assert len(result.warnings) > 0
        assert any("many audio fragments" in warn.lower() for warn in result.warnings)

    def test_long_total_text_warning(self):
        """Test > 1000 chars total text raises warning."""
        validator = NarrationValidator()

        exercise = Exercise(id="test-v1", title="Test")
        # Create text > 1000 chars
        long_text = "A" * 1200
        audio = AudioConfig(fragments=[long_text], max_duration_ms=100000)
        segment = Segment(id="test", type="narration", audio=audio)
        voice = VoiceConfig(provider="elevenlabs")
        script = NarrationScript(exercise=exercise, segments=[segment], voice_config=voice)

        result = validator.validate(script)
        assert result.is_valid
        assert len(result.warnings) > 0
        assert any("long text" in warn.lower() and "1200 chars" in warn for warn in result.warnings)

    def test_long_individual_fragment_warning(self):
        """Test > 500 chars in single fragment raises warning."""
        validator = NarrationValidator()

        exercise = Exercise(id="test-v1", title="Test")
        long_fragment = "B" * 600
        audio = AudioConfig(fragments=[long_fragment], max_duration_ms=50000)
        segment = Segment(id="test", type="narration", audio=audio)
        voice = VoiceConfig(provider="elevenlabs")
        script = NarrationScript(exercise=exercise, segments=[segment], voice_config=voice)

        result = validator.validate(script)
        assert result.is_valid
        assert len(result.warnings) > 0
        assert any("fragment" in warn.lower() and "600 chars" in warn for warn in result.warnings)


# ============================================================================
# Timing Feasibility Tests
# ============================================================================


class TestTimingFeasibility:
    """Test audio timing feasibility validation."""

    def test_audio_fits_in_max_duration(self):
        """Test audio that fits in max_duration passes validation."""
        validator = NarrationValidator()

        exercise = Exercise(id="test-v1", title="Test")
        breathing = BreathingPattern(inhale_ms=4000, exhale_ms=6000, repetitions=10)
        # Short text (20 chars) should easily fit in 8000ms
        audio = AudioConfig(fragments=["Short text here."], max_duration_ms=8000)
        segment = Segment(id="practice", type="breathing_cycle", breathing=breathing, audio=audio)
        voice = VoiceConfig(provider="elevenlabs")
        script = NarrationScript(exercise=exercise, segments=[segment], voice_config=voice)

        result = validator.validate(script)
        assert result.is_valid

    def test_audio_exceeds_max_duration_with_shortening_warning(self):
        """Test audio exceeding max_duration with shortening enabled raises warning."""
        validator = NarrationValidator()

        exercise = Exercise(id="test-v1", title="Test")
        breathing = BreathingPattern(inhale_ms=4000, exhale_ms=6000, repetitions=10)
        # Very long text that will exceed max_duration
        long_text = "This is a very long narration script. " * 50  # ~2000 chars
        audio = AudioConfig(
            fragments=[long_text],
            max_duration_ms=3000,  # Too short for this text
            allow_shortening=True,
        )
        segment = Segment(id="practice", type="breathing_cycle", breathing=breathing, audio=audio)
        voice = VoiceConfig(provider="elevenlabs")
        script = NarrationScript(exercise=exercise, segments=[segment], voice_config=voice)

        result = validator.validate(script)
        assert result.is_valid  # Valid because shortening is allowed
        assert len(result.warnings) > 0
        assert any("exceed max_duration" in warn.lower() for warn in result.warnings)

    def test_audio_exceeds_max_duration_without_shortening_error(self):
        """Test audio exceeding max_duration without shortening raises error."""
        validator = NarrationValidator()

        exercise = Exercise(id="test-v1", title="Test")
        breathing = BreathingPattern(inhale_ms=4000, exhale_ms=6000, repetitions=10)
        long_text = "This is a very long narration script. " * 50  # ~2000 chars
        audio = AudioConfig(
            fragments=[long_text],
            max_duration_ms=3000,
            allow_shortening=False,  # Shortening disabled!
        )
        segment = Segment(id="practice", type="breathing_cycle", breathing=breathing, audio=audio)
        voice = VoiceConfig(provider="elevenlabs")
        script = NarrationScript(exercise=exercise, segments=[segment], voice_config=voice)

        result = validator.validate(script)
        assert not result.is_valid
        assert any("exceed max_duration" in err.lower() and "shortening is disabled" in err.lower()
                   for err in result.errors)

    def test_max_duration_exceeds_breathing_cycle_warning(self):
        """Test max_duration > breathing cycle duration raises warning."""
        validator = NarrationValidator()

        exercise = Exercise(id="test-v1", title="Test")
        breathing = BreathingPattern(inhale_ms=4000, exhale_ms=6000, repetitions=10)  # 10s cycle
        audio = AudioConfig(
            fragments=["Test"],
            max_duration_ms=15000,  # Longer than cycle duration!
        )
        segment = Segment(id="practice", type="breathing_cycle", breathing=breathing, audio=audio)
        voice = VoiceConfig(provider="elevenlabs")
        script = NarrationScript(exercise=exercise, segments=[segment], voice_config=voice)

        result = validator.validate(script)
        assert result.is_valid  # Valid but warning
        assert len(result.warnings) > 0
        assert any("exceeds breathing cycle duration" in warn.lower() for warn in result.warnings)

    def test_narration_segment_no_timing_constraint(self):
        """Test narration-only segments skip timing validation."""
        validator = NarrationValidator()

        exercise = Exercise(id="test-v1", title="Test")
        # Narration segment with very long text - should not raise timing errors
        long_text = "A" * 2000
        audio = AudioConfig(fragments=[long_text], max_duration_ms=1000)  # Very short limit
        segment = Segment(id="intro", type="narration", audio=audio)  # Type: narration
        voice = VoiceConfig(provider="elevenlabs")
        script = NarrationScript(exercise=exercise, segments=[segment], voice_config=voice)

        result = validator.validate(script)
        # Should be valid - narration segments don't have timing constraints
        # But may have text length warnings
        assert result.is_valid or len(result.errors) == 0


# ============================================================================
# Integration Tests
# ============================================================================


class TestValidatorIntegration:
    """Test validator with realistic scenarios."""

    def test_valid_complete_script(self, sample_narration_script):
        """Test complete valid script passes all validation."""
        validator = NarrationValidator()
        result = validator.validate(sample_narration_script)
        assert result.is_valid

    def test_multiple_errors_and_warnings(self):
        """Test script with multiple validation issues."""
        validator = NarrationValidator()

        exercise = Exercise(id="test-v1", title="Test", duration_seconds=1000)

        # Segment 1: Duplicate ID, too short breathing cycle
        breathing1 = BreathingPattern(inhale_ms=300, exhale_ms=400, repetitions=10)
        audio1 = AudioConfig(fragments=["Test"], max_duration_ms=500)
        segment1 = Segment(id="duplicate", type="breathing_cycle", breathing=breathing1, audio=audio1)

        # Segment 2: Duplicate ID, long text
        long_text = "A" * 1200
        audio2 = AudioConfig(fragments=[long_text], max_duration_ms=50000)
        segment2 = Segment(id="duplicate", type="narration", audio=audio2)

        voice = VoiceConfig(provider="elevenlabs")
        script = NarrationScript(exercise=exercise, segments=[segment1, segment2], voice_config=voice)

        result = validator.validate(script)
        assert not result.is_valid
        assert len(result.errors) >= 2  # Duplicate ID + breathing cycle too short
        assert len(result.warnings) >= 2  # Duration mismatch + long text
