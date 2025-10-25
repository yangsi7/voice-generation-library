"""Tests for CLI interface (__main__.py).

Test Coverage Goals:
- Argument parsing
- Dry-run mode (validation only)
- Cost estimation mode
- Generation mode
- Error handling (file not found, validation errors, TTS errors)
- Verbose logging
- Exit codes
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock
from io import StringIO

from voice_generation.__main__ import main
from voice_generation.core.exceptions import ValidationError, TTSError
from voice_generation.core.results import GenerationResult


# ============================================================================
# CLI Argument Parsing Tests
# ============================================================================


class TestCLIArgumentParsing:
    """Test command-line argument parsing."""

    @patch('voice_generation.__main__.generate_narration')
    @patch('voice_generation.__main__.NarrationScript')
    def test_basic_invocation(self, mock_script_class, mock_generate, simple_script_json, capsys):
        """Test basic CLI invocation with minimal arguments."""
        mock_script = Mock()
        mock_script.exercise.title = "Test"
        mock_script.segments = [Mock(), Mock()]
        mock_script.estimate_total_duration_ms.return_value = 60000
        mock_script_class.from_file.return_value = mock_script

        mock_result = Mock(spec=GenerationResult)
        mock_result.exercise_id = "test-v1"
        mock_result.segment_count = 2
        mock_result.total_duration_seconds = 60.0
        mock_result.output_dir = Path("audio_out/test-v1")
        mock_result.metadata_path = Path("audio_out/test-v1/metadata.json")
        mock_result.audio_files = [Path("file1.wav"), Path("file2.wav")]
        mock_result.cache_hit_count = 0
        mock_result.cache_miss_count = 0
        mock_generate.return_value = mock_result

        with patch.object(sys, 'argv', ['voice_generation', str(simple_script_json)]):
            exit_code = main()

        assert exit_code == 0
        mock_generate.assert_called_once()

    @patch('voice_generation.__main__.NarrationValidator')
    @patch('voice_generation.__main__.NarrationScript')
    def test_custom_output_dir(self, mock_script_class, mock_validator_class, simple_script_json, tmp_path):
        """Test --output-dir argument."""
        mock_script = Mock()
        mock_script.exercise.title = "Test"
        mock_script.segments = []
        mock_script.estimate_total_duration_ms.return_value = 0
        mock_script_class.from_file.return_value = mock_script

        mock_validator = Mock()
        mock_validation = Mock()
        mock_validation.is_valid = True
        mock_validation.warnings = []
        mock_validator.validate.return_value = mock_validation
        mock_validator_class.return_value = mock_validator

        custom_dir = tmp_path / "custom_output"

        with patch.object(sys, 'argv', ['voice_generation', str(simple_script_json), '--output-dir', str(custom_dir), '--dry-run']):
            exit_code = main()

        assert exit_code == 0


# ============================================================================
# Dry-Run Mode Tests
# ============================================================================


class TestDryRunMode:
    """Test --dry-run mode (validation only)."""

    @patch('voice_generation.__main__.NarrationScript')
    @patch('voice_generation.__main__.NarrationValidator')
    def test_dry_run_valid_script(self, mock_validator_class, mock_script_class, simple_script_json, capsys):
        """Test dry-run with valid script."""
        mock_script = Mock()
        mock_script.exercise.title = "Test Exercise"
        mock_script.segments = [Mock()]
        mock_script.estimate_total_duration_ms.return_value = 30000
        mock_script_class.from_file.return_value = mock_script

        mock_validator = Mock()
        mock_validation = Mock()
        mock_validation.is_valid = True
        mock_validation.warnings = []
        mock_validator.validate.return_value = mock_validation
        mock_validator_class.return_value = mock_validator

        with patch.object(sys, 'argv', ['voice_generation', str(simple_script_json), '--dry-run']):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Validation passed" in captured.out

    @patch('voice_generation.__main__.NarrationScript')
    @patch('voice_generation.__main__.NarrationValidator')
    def test_dry_run_invalid_script(self, mock_validator_class, mock_script_class, simple_script_json, capsys):
        """Test dry-run with invalid script."""
        mock_script = Mock()
        mock_script.exercise.title = "Test"
        mock_script.segments = []
        mock_script.estimate_total_duration_ms.return_value = 0
        mock_script_class.from_file.return_value = mock_script

        mock_validator = Mock()
        mock_validation = Mock()
        mock_validation.is_valid = False
        mock_validation.errors = ["Error 1", "Error 2"]
        mock_validator.validate.return_value = mock_validation
        mock_validator_class.return_value = mock_validator

        with patch.object(sys, 'argv', ['voice_generation', str(simple_script_json), '--dry-run']):
            exit_code = main()

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Validation failed" in captured.out

    @patch('voice_generation.__main__.NarrationScript')
    @patch('voice_generation.__main__.NarrationValidator')
    def test_dry_run_with_warnings(self, mock_validator_class, mock_script_class, simple_script_json, capsys):
        """Test dry-run displays warnings."""
        mock_script = Mock()
        mock_script.exercise.title = "Test"
        mock_script.segments = []
        mock_script.estimate_total_duration_ms.return_value = 0
        mock_script_class.from_file.return_value = mock_script

        mock_validator = Mock()
        mock_validation = Mock()
        mock_validation.is_valid = True
        mock_validation.warnings = ["Warning 1", "Warning 2"]
        mock_validator.validate.return_value = mock_validation
        mock_validator_class.return_value = mock_validator

        with patch.object(sys, 'argv', ['voice_generation', str(simple_script_json), '--dry-run']):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Warning" in captured.out


# ============================================================================
# Cost Estimation Mode Tests
# ============================================================================


class TestCostEstimationMode:
    """Test --estimate-cost mode."""

    @patch('voice_generation.__main__.NarrationScript')
    def test_estimate_cost(self, mock_script_class, simple_script_json, capsys):
        """Test cost estimation mode."""
        mock_segment1 = Mock()
        mock_segment1.audio.fragments = ["Text 1", "Text 2"]
        mock_segment2 = Mock()
        mock_segment2.audio.fragments = ["Text 3"]

        mock_script = Mock()
        mock_script.exercise.title = "Test"
        mock_script.segments = [mock_segment1, mock_segment2]
        mock_script.estimate_total_duration_ms.return_value = 0
        mock_script_class.from_file.return_value = mock_script

        with patch.object(sys, 'argv', ['voice_generation', str(simple_script_json), '--estimate-cost']):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Estimating costs" in captured.out
        assert "Total characters" in captured.out
        assert "Estimated cost" in captured.out


# ============================================================================
# Generation Mode Tests
# ============================================================================


class TestGenerationMode:
    """Test normal generation mode."""

    @patch('voice_generation.__main__.generate_narration')
    @patch('voice_generation.__main__.NarrationScript')
    def test_generation_success(self, mock_script_class, mock_generate, simple_script_json, capsys):
        """Test successful generation."""
        mock_script = Mock()
        mock_script.exercise.title = "Test Exercise"
        mock_script.segments = [Mock(), Mock()]
        mock_script.estimate_total_duration_ms.return_value = 45000
        mock_script_class.from_file.return_value = mock_script

        mock_result = Mock(spec=GenerationResult)
        mock_result.exercise_id = "test-exercise-v1"
        mock_result.segment_count = 2
        mock_result.total_duration_seconds = 45.0
        mock_result.output_dir = Path("audio_out/test-exercise-v1")
        mock_result.metadata_path = Path("audio_out/test-exercise-v1/metadata.json")
        mock_result.audio_files = [Path("audio1.wav"), Path("audio2.wav")]
        mock_result.cache_hit_count = 5
        mock_result.cache_miss_count = 3
        mock_result.cache_hit_rate = 62.5
        mock_generate.return_value = mock_result

        with patch.object(sys, 'argv', ['voice_generation', str(simple_script_json)]):
            exit_code = main()

        assert exit_code == 0
        captured = capsys.readouterr()
        assert "GENERATION COMPLETE" in captured.out
        assert "test-exercise-v1" in captured.out
        assert "Cache hit rate" in captured.out

    @patch('voice_generation.__main__.generate_narration')
    @patch('voice_generation.__main__.NarrationScript')
    def test_generation_with_no_cache(self, mock_script_class, mock_generate, simple_script_json):
        """Test generation with --no-cache flag."""
        mock_script = Mock()
        mock_script.exercise.title = "Test"
        mock_script.segments = []
        mock_script.estimate_total_duration_ms.return_value = 0
        mock_script_class.from_file.return_value = mock_script

        mock_result = Mock(spec=GenerationResult)
        mock_result.exercise_id = "test-v1"
        mock_result.segment_count = 0
        mock_result.total_duration_seconds = 0
        mock_result.output_dir = Path("audio_out/test-v1")
        mock_result.metadata_path = Path("metadata.json")
        mock_result.audio_files = []
        mock_result.cache_hit_count = 0
        mock_result.cache_miss_count = 0
        mock_generate.return_value = mock_result

        with patch.object(sys, 'argv', ['voice_generation', str(simple_script_json), '--no-cache']):
            exit_code = main()

        assert exit_code == 0
        # Verify cache_dir=None was passed
        call_kwargs = mock_generate.call_args[1]
        assert call_kwargs['cache_dir'] is None


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestErrorHandling:
    """Test CLI error handling."""

    def test_file_not_found(self, capsys):
        """Test FileNotFoundError handling."""
        with patch.object(sys, 'argv', ['voice_generation', 'nonexistent.json']):
            exit_code = main()

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "File not found" in captured.err

    @patch('voice_generation.__main__.generate_narration')
    @patch('voice_generation.__main__.NarrationScript')
    def test_validation_error(self, mock_script_class, mock_generate, simple_script_json, capsys):
        """Test ValidationError handling."""
        mock_script = Mock()
        mock_script.exercise.title = "Test"
        mock_script.segments = []
        mock_script.estimate_total_duration_ms.return_value = 0
        mock_script_class.from_file.return_value = mock_script

        mock_generate.side_effect = ValidationError(["Error 1", "Error 2"], message="Validation failed")

        with patch.object(sys, 'argv', ['voice_generation', str(simple_script_json)]):
            exit_code = main()

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Validation error" in captured.err

    @patch('voice_generation.__main__.generate_narration')
    @patch('voice_generation.__main__.NarrationScript')
    def test_tts_error(self, mock_script_class, mock_generate, simple_script_json, capsys):
        """Test TTSError handling."""
        mock_script = Mock()
        mock_script.exercise.title = "Test"
        mock_script.segments = []
        mock_script.estimate_total_duration_ms.return_value = 0
        mock_script_class.from_file.return_value = mock_script

        mock_generate.side_effect = TTSError("API failed")

        with patch.object(sys, 'argv', ['voice_generation', str(simple_script_json)]):
            exit_code = main()

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "TTS generation error" in captured.err

    @patch('voice_generation.__main__.generate_narration')
    @patch('voice_generation.__main__.NarrationScript')
    def test_value_error(self, mock_script_class, mock_generate, simple_script_json, capsys):
        """Test ValueError handling (configuration errors)."""
        mock_script = Mock()
        mock_script.exercise.title = "Test"
        mock_script.segments = []
        mock_script.estimate_total_duration_ms.return_value = 0
        mock_script_class.from_file.return_value = mock_script

        mock_generate.side_effect = ValueError("Missing API key")

        with patch.object(sys, 'argv', ['voice_generation', str(simple_script_json)]):
            exit_code = main()

        assert exit_code == 1
        captured = capsys.readouterr()
        assert "Configuration error" in captured.err

    @patch('voice_generation.__main__.NarrationScript')
    def test_keyboard_interrupt(self, mock_script_class, simple_script_json, capsys):
        """Test KeyboardInterrupt handling."""
        mock_script_class.from_file.side_effect = KeyboardInterrupt()

        with patch.object(sys, 'argv', ['voice_generation', str(simple_script_json)]):
            exit_code = main()

        assert exit_code == 130
        captured = capsys.readouterr()
        assert "Interrupted by user" in captured.err


# ============================================================================
# Verbose Mode Tests
# ============================================================================


class TestVerboseMode:
    """Test verbose logging mode."""

    @patch('voice_generation.__main__.logging.basicConfig')
    @patch('voice_generation.__main__.NarrationScript')
    def test_verbose_flag_enables_logging(self, mock_script_class, mock_logging, simple_script_json):
        """Test --verbose flag enables logging."""
        mock_script = Mock()
        mock_script.exercise.title = "Test"
        mock_script.segments = []
        mock_script.estimate_total_duration_ms.return_value = 0
        mock_script_class.from_file.return_value = mock_script

        with patch.object(sys, 'argv', ['voice_generation', str(simple_script_json), '--dry-run', '--verbose']):
            main()

        mock_logging.assert_called_once()
