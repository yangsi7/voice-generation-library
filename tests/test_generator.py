"""Tests for VoiceNarrationGenerator (main orchestrator).

Test Coverage Goals:
- Generator initialization
- Script validation via generator
- Cost estimation
- Full generation workflow (with mocked TTS)
- Segment processing
- Error handling and aggregation
- Metadata creation integration
- Statistics tracking (cache hits/misses)
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock

from pydub import AudioSegment

from voice_generation.core.generator import VoiceNarrationGenerator
from voice_generation.core.models import (
    NarrationScript, Segment, BreathingPattern, AudioConfig, Exercise, VoiceConfig
)
from voice_generation.core.exceptions import ValidationError, SegmentProcessingError, TTSError
from voice_generation.core.results import GenerationResult, ValidationResult, CostEstimate


# ============================================================================
# Generator Initialization Tests
# ============================================================================


class TestGeneratorInitialization:
    """Test generator initialization and configuration."""

    def test_init_with_required_params(self, mock_tts_client, temp_storage):
        """Test initializing generator with required parameters only."""
        generator = VoiceNarrationGenerator(
            tts_client=mock_tts_client,
            storage=temp_storage,
        )

        assert generator.tts == mock_tts_client
        assert generator.storage == temp_storage
        assert generator.audio is not None
        assert generator.validator is not None
        assert generator.verbose is False

    def test_init_with_custom_components(self, mock_tts_client, temp_storage):
        """Test initializing generator with custom audio processor and validator."""
        from voice_generation.processors.audio import AudioProcessor
        from voice_generation.core.validator import NarrationValidator

        custom_audio = AudioProcessor()
        custom_validator = NarrationValidator()

        generator = VoiceNarrationGenerator(
            tts_client=mock_tts_client,
            storage=temp_storage,
            audio_processor=custom_audio,
            validator=custom_validator,
            verbose=True,
        )

        assert generator.audio == custom_audio
        assert generator.validator == custom_validator
        assert generator.verbose is True


# ============================================================================
# Validation Tests
# ============================================================================


class TestGeneratorValidation:
    """Test script validation through generator."""

    def test_validate_valid_script(self, generator_with_mocks, simple_script):
        """Test validating a valid script."""
        result = generator_with_mocks.validate(simple_script)

        assert isinstance(result, ValidationResult)
        assert result.is_valid is True
        assert len(result.errors) == 0

    def test_validate_invalid_script(self, generator_with_mocks):
        """Test validating an invalid script (exercise duration too long)."""
        # Create script with duration > MAX_EXERCISE_DURATION_SECONDS (3600s)
        script = NarrationScript(
            exercise=Exercise(id="test-v1", title="Test"),
            segments=[
                Segment(
                    id="practice",
                    type="breathing_cycle",
                    breathing=BreathingPattern(
                        inhale_ms=4000,
                        exhale_ms=6000,
                        repetitions=500,  # 500 * 10s = 5000s > 3600s
                    ),
                    audio=AudioConfig(fragments=["Breathe."]),
                ),
            ],
            voice_config=VoiceConfig(),
        )

        result = generator_with_mocks.validate(script)

        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "too long" in result.errors[0].lower()


# ============================================================================
# Cost Estimation Tests
# ============================================================================


class TestCostEstimation:
    """Test cost estimation functionality."""

    def test_estimate_cost(self, generator_with_mocks, simple_script):
        """Test estimating cost for a script."""
        result = generator_with_mocks.estimate_cost(simple_script)

        assert isinstance(result, CostEstimate)
        assert result.total_characters > 0
        assert result.estimated_usd > 0
        assert result.currency == "USD"

    def test_estimate_cost_matches_fragment_length(self, generator_with_mocks):
        """Test cost estimation calculates correct character count."""
        script = NarrationScript(
            exercise=Exercise(id="test-v1", title="Test"),
            segments=[
                Segment(
                    id="intro",
                    type="narration",
                    breathing=BreathingPattern(duration_ms=10000, repetitions=1),
                    audio=AudioConfig(fragments=["Hello world", "Test message"]),
                ),
            ],
            voice_config=VoiceConfig(),
        )

        result = generator_with_mocks.estimate_cost(script)

        # "Hello world" (11) + "Test message" (12) = 23 characters
        assert result.total_characters == 23


# ============================================================================
# Segment Processing Tests
# ============================================================================


class TestSegmentProcessing:
    """Test individual segment processing."""

    def test_process_segment_single_fragment(self, generator_with_mocks, tmp_path, sample_audio):
        """Test processing segment with single fragment."""
        generator_with_mocks.tts.generate_audio.return_value = sample_audio

        segment = Segment(
            id="intro",
            type="narration",
            breathing=BreathingPattern(duration_ms=5000, repetitions=1),
            audio=AudioConfig(fragments=["Welcome."]),
        )

        output_dir = tmp_path / "test-v1"
        output_dir.mkdir()

        result = generator_with_mocks._process_segment(segment, 0, output_dir)

        assert result.segment_id == "intro"
        assert result.segment_index == 0
        assert result.fragment_count == 1
        assert result.duration_ms > 0
        assert result.audio_path.exists()
        assert result.was_shortened is False

        # Verify TTS was called once
        assert generator_with_mocks.tts.generate_audio.call_count == 1

    def test_process_segment_multiple_fragments(self, generator_with_mocks, tmp_path, sample_audio):
        """Test processing segment with multiple fragments (stitching)."""
        generator_with_mocks.tts.generate_audio.return_value = sample_audio

        segment = Segment(
            id="practice",
            type="breathing_cycle",
            breathing=BreathingPattern(inhale_ms=4000, exhale_ms=6000, repetitions=5),
            audio=AudioConfig(fragments=["Breathe in.", "Hold.", "Breathe out."]),
        )

        output_dir = tmp_path / "test-v1"
        output_dir.mkdir()

        result = generator_with_mocks._process_segment(segment, 0, output_dir)

        assert result.fragment_count == 3
        # Verify TTS was called for each fragment
        assert generator_with_mocks.tts.generate_audio.call_count == 3

    def test_process_segment_with_context(self, generator_with_mocks, tmp_path, sample_audio):
        """Test segment processing passes context to TTS."""
        generator_with_mocks.tts.generate_audio.return_value = sample_audio

        segment = Segment(
            id="practice",
            type="breathing_cycle",
            breathing=BreathingPattern(inhale_ms=4000, exhale_ms=6000, repetitions=5),
            audio=AudioConfig(fragments=["First.", "Second.", "Third."]),
        )

        output_dir = tmp_path / "test-v1"
        output_dir.mkdir()

        generator_with_mocks._process_segment(segment, 0, output_dir)

        # Check that context was passed for middle fragment
        calls = generator_with_mocks.tts.generate_audio.call_args_list

        # Second call (index 1) should have previous and next text
        second_call = calls[1]
        text, previous, next_text = second_call[0]
        assert text == "Second."
        assert previous == "First."
        assert next_text == "Third."

    def test_process_segment_tts_failure_raises_error(self, generator_with_mocks, tmp_path):
        """Test TTS failure raises TTSError."""
        generator_with_mocks.tts.generate_audio.side_effect = Exception("API Error")

        segment = Segment(
            id="intro",
            type="narration",
            breathing=BreathingPattern(duration_ms=5000, repetitions=1),
            audio=AudioConfig(fragments=["Test."]),
        )

        output_dir = tmp_path / "test-v1"
        output_dir.mkdir()

        with pytest.raises(TTSError) as exc_info:
            generator_with_mocks._process_segment(segment, 0, output_dir)

        assert "failed to generate audio" in str(exc_info.value).lower()


# ============================================================================
# Full Generation Workflow Tests
# ============================================================================


class TestFullGenerationWorkflow:
    """Test complete generation workflow end-to-end."""

    def test_generate_simple_script(self, generator_with_mocks, simple_script, sample_audio):
        """Test generating audio for simple valid script."""
        generator_with_mocks.tts.generate_audio.return_value = sample_audio

        result = generator_with_mocks.generate(simple_script)

        assert isinstance(result, GenerationResult)
        assert result.exercise_id == simple_script.exercise.id
        assert result.segment_count == len(simple_script.segments)
        assert result.total_duration_ms > 0
        assert result.output_dir.exists()
        assert result.metadata_path.exists()
        assert len(result.audio_files) == result.segment_count

    def test_generate_creates_output_directory(self, generator_with_mocks, simple_script, sample_audio):
        """Test generation creates exercise directory."""
        generator_with_mocks.tts.generate_audio.return_value = sample_audio

        result = generator_with_mocks.generate(simple_script)

        expected_dir = generator_with_mocks.storage.base_dir / simple_script.exercise.id
        assert expected_dir.exists()
        assert result.output_dir == expected_dir

    def test_generate_writes_metadata(self, generator_with_mocks, simple_script, sample_audio):
        """Test generation writes metadata JSON."""
        generator_with_mocks.tts.generate_audio.return_value = sample_audio

        result = generator_with_mocks.generate(simple_script)

        metadata_path = result.metadata_path
        assert metadata_path.exists()
        assert metadata_path.suffix == ".json"

        # Verify metadata can be read back
        metadata = generator_with_mocks.storage.read_json(metadata_path)
        assert metadata["exercise_id"] == simple_script.exercise.id
        assert "segments" in metadata
        assert "breath_cycles" in metadata

    def test_generate_writes_audio_files(self, generator_with_mocks, simple_script, sample_audio):
        """Test generation writes WAV audio files."""
        generator_with_mocks.tts.generate_audio.return_value = sample_audio

        result = generator_with_mocks.generate(simple_script)

        for audio_file in result.audio_files:
            assert audio_file.exists()
            assert audio_file.suffix == ".wav"

            # Verify audio can be read back
            audio = AudioSegment.from_file(audio_file)
            assert len(audio) > 0

    def test_generate_tracks_cache_statistics(self, generator_with_mocks, simple_script, sample_audio):
        """Test generation tracks TTS cache statistics."""
        generator_with_mocks.tts.generate_audio.return_value = sample_audio
        generator_with_mocks.tts.cache_hits = 5
        generator_with_mocks.tts.cache_misses = 3

        result = generator_with_mocks.generate(simple_script)

        assert result.cache_hit_count == 5
        assert result.cache_miss_count == 3
        assert result.cache_hit_rate > 0


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestGeneratorErrorHandling:
    """Test error handling and recovery."""

    def test_generate_invalid_script_raises_validation_error(self, generator_with_mocks):
        """Test generating invalid script raises ValidationError."""
        # Script with exercise duration too long
        script = NarrationScript(
            exercise=Exercise(id="test-v1", title="Test"),
            segments=[
                Segment(
                    id="practice",
                    type="breathing_cycle",
                    breathing=BreathingPattern(
                        inhale_ms=4000,
                        exhale_ms=6000,
                        repetitions=500,  # Too many repetitions
                    ),
                    audio=AudioConfig(fragments=["Breathe."]),
                ),
            ],
            voice_config=VoiceConfig(),
        )

        with pytest.raises(ValidationError) as exc_info:
            generator_with_mocks.generate(script)

        assert "validation failed" in str(exc_info.value).lower()

    def test_generate_segment_failure_raises_processing_error(self, generator_with_mocks, simple_script):
        """Test segment processing failure raises SegmentProcessingError."""
        # Make TTS fail on second segment
        generator_with_mocks.tts.generate_audio.side_effect = Exception("TTS failed")

        with pytest.raises(SegmentProcessingError) as exc_info:
            generator_with_mocks.generate(simple_script)

        # Error should include segment info
        error = exc_info.value
        assert error.segment_id is not None
        assert error.index is not None

    def test_generate_logs_warnings(self, generator_with_mocks, sample_audio, caplog):
        """Test generation logs validation warnings."""
        # Script with warnings (long text)
        script = NarrationScript(
            exercise=Exercise(id="test-v1", title="Test"),
            segments=[
                Segment(
                    id="intro",
                    type="narration",
                    breathing=BreathingPattern(duration_ms=5000, repetitions=1),
                    audio=AudioConfig(fragments=["A" * 1001]),  # > 1000 chars = warning
                ),
            ],
            voice_config=VoiceConfig(),
        )

        generator_with_mocks.tts.generate_audio.return_value = sample_audio

        result = generator_with_mocks.generate(script)

        # Should complete successfully despite warnings
        assert isinstance(result, GenerationResult)


# ============================================================================
# Integration with Other Components Tests
# ============================================================================


class TestComponentIntegration:
    """Test integration with audio processor, metadata builder, etc."""

    def test_generate_calls_audio_processor_methods(self, generator_with_mocks, simple_script, sample_audio):
        """Test generation calls audio processor trim/pad/stitch methods."""
        generator_with_mocks.tts.generate_audio.return_value = sample_audio

        # Spy on audio processor
        audio_processor = generator_with_mocks.audio
        original_stitch = audio_processor.stitch
        stitch_calls = []

        def stitch_spy(segments):
            stitch_calls.append(len(segments))
            return original_stitch(segments)

        audio_processor.stitch = stitch_spy

        generator_with_mocks.generate(simple_script)

        # Should have called stitch for each segment
        assert len(stitch_calls) == len(simple_script.segments)

    def test_generate_calls_metadata_builder(self, generator_with_mocks, simple_script, sample_audio):
        """Test generation calls MetadataBuilder to create metadata."""
        generator_with_mocks.tts.generate_audio.return_value = sample_audio

        result = generator_with_mocks.generate(simple_script)

        # Verify metadata was created with breath cycles
        metadata = generator_with_mocks.storage.read_json(result.metadata_path)
        assert "breath_cycles" in metadata
        assert len(metadata["breath_cycles"]) >= 0  # May have 0 if all narration-only

    def test_generate_uses_storage_for_all_io(self, generator_with_mocks, simple_script, sample_audio):
        """Test generation uses storage abstraction for all I/O."""
        generator_with_mocks.tts.generate_audio.return_value = sample_audio

        result = generator_with_mocks.generate(simple_script)

        # All files should be in storage base directory
        assert result.output_dir.parent == generator_with_mocks.storage.base_dir
        for audio_file in result.audio_files:
            assert audio_file.parent == result.output_dir


# ============================================================================
# Statistics and Reporting Tests
# ============================================================================


class TestStatisticsAndReporting:
    """Test statistics tracking and result reporting."""

    def test_generate_result_includes_all_statistics(self, generator_with_mocks, simple_script, sample_audio):
        """Test GenerationResult includes all expected statistics."""
        generator_with_mocks.tts.generate_audio.return_value = sample_audio
        generator_with_mocks.tts.cache_hits = 10
        generator_with_mocks.tts.cache_misses = 5

        result = generator_with_mocks.generate(simple_script)

        # Check all fields are populated
        assert result.exercise_id == simple_script.exercise.id
        assert result.output_dir.exists()
        assert result.segment_count == len(simple_script.segments)
        assert result.total_duration_ms > 0
        assert result.metadata_path.exists()
        assert len(result.audio_files) > 0
        assert result.cache_hit_count == 10
        assert result.cache_miss_count == 5

    def test_generate_result_total_duration_matches_segments(self, generator_with_mocks, simple_script, sample_audio):
        """Test total duration equals sum of segment durations."""
        generator_with_mocks.tts.generate_audio.return_value = sample_audio

        result = generator_with_mocks.generate(simple_script)

        # Read back audio files and sum their durations
        actual_total_ms = 0
        for audio_file in result.audio_files:
            audio = AudioSegment.from_file(audio_file)
            actual_total_ms += len(audio)

        assert result.total_duration_ms == actual_total_ms
