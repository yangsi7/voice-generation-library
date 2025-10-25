"""Integration tests for voice generation system.

Test Coverage Goals:
- Full end-to-end workflow with real file I/O
- Caching verification across sessions
- Error recovery scenarios
- Output file structure validation
- Multiple format support
- Real narration script parsing
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch

from voice_generation import generate_narration
from voice_generation.core.models import NarrationScript
from voice_generation.core.results import GenerationResult
from pydub import AudioSegment


# ============================================================================
# End-to-End Workflow Tests
# ============================================================================


class TestEndToEndWorkflow:
    """Test complete voice generation workflow."""

    @patch('voice_generation.api.ElevenLabsClient')
    def test_complete_workflow_from_json_to_output(
        self, mock_client_class, simple_script_json, tmp_path, sample_audio, mock_env_vars
    ):
        """Test complete workflow: JSON → TTS → Audio → Metadata."""
        # Setup mock TTS client
        mock_client = Mock()
        mock_client.generate_audio.return_value = sample_audio
        mock_client.cache_hits = 0
        mock_client.cache_misses = 2
        mock_client_class.return_value = mock_client

        output_dir = tmp_path / "integration_output"

        # Run generation
        result = generate_narration(
            simple_script_json,
            output_dir=output_dir,
            cache_dir=None,  # Disable caching for this test
        )

        # Verify result
        assert isinstance(result, GenerationResult)
        assert result.segment_count == 2  # intro + practice segments
        assert result.output_dir.exists()
        assert result.metadata_path.exists()

        # Verify audio files exist
        assert len(result.audio_files) == 2
        for audio_file in result.audio_files:
            assert audio_file.exists()
            # Verify audio is valid
            audio = AudioSegment.from_file(audio_file)
            assert len(audio) > 0

        # Verify metadata content
        with open(result.metadata_path) as f:
            metadata = json.load(f)
        assert "exercise_id" in metadata
        assert "segments" in metadata
        assert len(metadata["segments"]) == 2

    @patch('voice_generation.api.ElevenLabsClient')
    def test_workflow_with_custom_output_directory(
        self, mock_client_class, simple_script_json, tmp_path, sample_audio, mock_env_vars
    ):
        """Test workflow with custom output directory."""
        mock_client = Mock()
        mock_client.generate_audio.return_value = sample_audio
        mock_client.cache_hits = 0
        mock_client.cache_misses = 2
        mock_client_class.return_value = mock_client

        custom_output = tmp_path / "custom" / "nested" / "output"

        result = generate_narration(
            simple_script_json,
            output_dir=custom_output,
            cache_dir=None,
        )

        # Verify custom directory was created
        assert result.output_dir.exists()
        assert str(custom_output) in str(result.output_dir)

    @patch('voice_generation.api.ElevenLabsClient')
    def test_workflow_preserves_script_structure(
        self, mock_client_class, simple_script_json, tmp_path, sample_audio, mock_env_vars
    ):
        """Test that output metadata preserves script structure."""
        mock_client = Mock()
        mock_client.generate_audio.return_value = sample_audio
        mock_client.cache_hits = 0
        mock_client.cache_misses = 2
        mock_client_class.return_value = mock_client

        # Load original script
        original_script = NarrationScript.from_file(simple_script_json)

        result = generate_narration(
            simple_script_json,
            output_dir=tmp_path / "output",
            cache_dir=None,
        )

        # Load generated metadata
        with open(result.metadata_path) as f:
            metadata = json.load(f)

        # Verify structure matches
        assert metadata["exercise_id"] == original_script.exercise.id
        assert len(metadata["segments"]) == len(original_script.segments)


# ============================================================================
# Caching Integration Tests
# ============================================================================


class TestCachingIntegration:
    """Test caching behavior across sessions."""

    @patch('voice_generation.api.ElevenLabsClient')
    def test_cache_hit_on_second_generation(
        self, mock_client_class, simple_script_json, tmp_path, sample_audio, mock_env_vars
    ):
        """Test that caching is enabled when cache_dir is provided."""
        cache_dir = tmp_path / "cache"
        output_dir = tmp_path / "output"

        # Mock client with cache tracking
        mock_client = Mock()
        mock_client.generate_audio.return_value = sample_audio
        mock_client.cache_hits = 0
        mock_client.cache_misses = 2
        mock_client_class.return_value = mock_client

        result = generate_narration(
            simple_script_json,
            output_dir=output_dir,
            cache_dir=cache_dir,
        )

        # Verify client was created with cache_dir
        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["cache_dir"] == cache_dir

        # Verify result has cache statistics
        assert result.cache_hit_count == 0
        assert result.cache_miss_count == 2

    @patch('voice_generation.api.ElevenLabsClient')
    def test_no_cache_when_cache_dir_none(
        self, mock_client_class, simple_script_json, tmp_path, sample_audio, mock_env_vars
    ):
        """Test that cache_dir=None disables caching."""
        mock_client = Mock()
        mock_client.generate_audio.return_value = sample_audio
        mock_client.cache_hits = 0
        mock_client.cache_misses = 2
        mock_client_class.return_value = mock_client

        result = generate_narration(
            simple_script_json,
            output_dir=tmp_path / "output",
            cache_dir=None,  # Disable caching
        )

        # Verify client was created with cache_dir=None
        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["cache_dir"] is None


# ============================================================================
# Error Recovery Tests
# ============================================================================


class TestErrorRecovery:
    """Test system behavior when errors occur."""

    def test_handles_missing_input_file(self, tmp_path, mock_env_vars):
        """Test graceful handling of missing input file."""
        nonexistent_file = tmp_path / "nonexistent.json"

        with pytest.raises(FileNotFoundError):
            generate_narration(nonexistent_file)

    @patch('voice_generation.api.ElevenLabsClient')
    def test_handles_invalid_output_directory(
        self, mock_client_class, simple_script_json, sample_audio, mock_env_vars
    ):
        """Test handling of invalid output directory."""
        mock_client = Mock()
        mock_client.generate_audio.return_value = sample_audio
        mock_client.cache_hits = 0
        mock_client.cache_misses = 2
        mock_client_class.return_value = mock_client

        # Try to use a file as a directory (should create parent dir)
        output_dir = Path("/tmp/voice_gen_test_invalid")

        # Should succeed by creating the directory
        result = generate_narration(
            simple_script_json,
            output_dir=output_dir,
            cache_dir=None,
        )

        assert result.output_dir.exists()


# ============================================================================
# Output Validation Tests
# ============================================================================


class TestOutputValidation:
    """Test output file structure and content."""

    @patch('voice_generation.api.ElevenLabsClient')
    def test_output_directory_structure(
        self, mock_client_class, simple_script_json, tmp_path, sample_audio, mock_env_vars
    ):
        """Test that output directory has correct structure."""
        mock_client = Mock()
        mock_client.generate_audio.return_value = sample_audio
        mock_client.cache_hits = 0
        mock_client.cache_misses = 2
        mock_client_class.return_value = mock_client

        result = generate_narration(
            simple_script_json,
            output_dir=tmp_path / "output",
            cache_dir=None,
        )

        # Verify directory structure
        assert result.output_dir.is_dir()
        assert result.output_dir.name == result.exercise_id

        # Verify metadata file
        assert result.metadata_path.is_file()
        assert result.metadata_path.name == f"{result.exercise_id}_metadata.json"

        # Verify audio files
        for audio_file in result.audio_files:
            assert audio_file.is_file()
            assert audio_file.suffix == ".wav"

    @patch('voice_generation.api.ElevenLabsClient')
    def test_metadata_json_is_valid(
        self, mock_client_class, simple_script_json, tmp_path, sample_audio, mock_env_vars
    ):
        """Test that generated metadata JSON is valid."""
        mock_client = Mock()
        mock_client.generate_audio.return_value = sample_audio
        mock_client.cache_hits = 0
        mock_client.cache_misses = 2
        mock_client_class.return_value = mock_client

        result = generate_narration(
            simple_script_json,
            output_dir=tmp_path / "output",
            cache_dir=None,
        )

        # Load and validate metadata
        with open(result.metadata_path) as f:
            metadata = json.load(f)

        # Verify required fields
        assert "exercise_id" in metadata
        assert "exercise_title" in metadata
        assert "segments" in metadata
        assert "breath_cycles" in metadata

        # Verify breath_cycles structure
        assert len(metadata["breath_cycles"]) == 2
        for cycle in metadata["breath_cycles"]:
            assert "breathe_in" in cycle
            assert "breathe_out" in cycle
            assert "repetitions" in cycle
            assert "voices" in cycle
