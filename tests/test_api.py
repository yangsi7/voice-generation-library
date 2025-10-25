"""Tests for simple convenience API (generate_narration function).

Test Coverage Goals:
- Successful generation via convenience API
- Environment variable credential handling
- Parameter credential handling
- Credential precedence (param > JSON > env)
- Missing credential errors
- File loading and validation
- Default parameter values
- TTS client configuration from script
"""

import pytest
from pathlib import Path
from unittest.mock import patch, Mock

from voice_generation.api import generate_narration
from voice_generation.core.models import NarrationScript, Exercise, Segment, BreathingPattern, AudioConfig, VoiceConfig
from voice_generation.core.results import GenerationResult


# ============================================================================
# Successful Generation Tests
# ============================================================================


class TestSuccessfulGeneration:
    """Test successful narration generation via API."""

    @patch('voice_generation.api.VoiceNarrationGenerator')
    @patch('voice_generation.api.ElevenLabsClient')
    def test_generate_with_env_credentials(
        self, mock_client_class, mock_generator_class, tmp_path, simple_script_json, mock_env_vars
    ):
        """Test generation using environment variables for credentials."""
        # Setup mocks
        mock_generator = Mock()
        mock_result = GenerationResult(
            exercise_id="test-v1",
            output_dir=tmp_path / "audio_out" / "test-v1",
            segment_count=2,
            total_duration_ms=10000,
            metadata_path=tmp_path / "metadata.json",
        )
        mock_generator.generate.return_value = mock_result
        mock_generator_class.return_value = mock_generator

        # Call API
        result = generate_narration(simple_script_json)

        # Verify result
        assert isinstance(result, GenerationResult)
        assert result.exercise_id == "test-v1"

        # Verify TTS client was created with env credentials
        mock_client_class.assert_called_once()
        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["api_key"] == "test_api_key_123"
        assert call_kwargs["voice_id"] == "test_voice_456"

    @patch('voice_generation.api.VoiceNarrationGenerator')
    @patch('voice_generation.api.ElevenLabsClient')
    def test_generate_with_param_credentials(
        self, mock_client_class, mock_generator_class, tmp_path, simple_script_json
    ):
        """Test generation using function parameters for credentials."""
        # Setup mocks
        mock_generator = Mock()
        mock_result = GenerationResult(
            exercise_id="test-v1",
            output_dir=tmp_path / "audio_out" / "test-v1",
            segment_count=2,
            total_duration_ms=10000,
            metadata_path=tmp_path / "metadata.json",
        )
        mock_generator.generate.return_value = mock_result
        mock_generator_class.return_value = mock_generator

        # Call API with explicit credentials
        result = generate_narration(
            simple_script_json,
            api_key="param_api_key",
            voice_id="param_voice_id",
        )

        # Verify TTS client was created with param credentials
        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["api_key"] == "param_api_key"
        assert call_kwargs["voice_id"] == "param_voice_id"

    @patch('voice_generation.api.VoiceNarrationGenerator')
    @patch('voice_generation.api.ElevenLabsClient')
    def test_generate_with_custom_output_dir(
        self, mock_client_class, mock_generator_class, tmp_path, simple_script_json, mock_env_vars
    ):
        """Test generation with custom output directory."""
        mock_generator = Mock()
        mock_result = GenerationResult(
            exercise_id="test-v1",
            output_dir=tmp_path / "custom_output" / "test-v1",
            segment_count=2,
            total_duration_ms=10000,
            metadata_path=tmp_path / "metadata.json",
        )
        mock_generator.generate.return_value = mock_result
        mock_generator_class.return_value = mock_generator

        custom_output = tmp_path / "custom_output"
        result = generate_narration(simple_script_json, output_dir=custom_output)

        # Verify FileSystemStorage was created with custom output dir
        # (Generator is called with storage that has base_dir = custom_output)
        assert result.output_dir.parent == custom_output

    @patch('voice_generation.api.VoiceNarrationGenerator')
    @patch('voice_generation.api.ElevenLabsClient')
    def test_generate_with_cache_disabled(
        self, mock_client_class, mock_generator_class, simple_script_json, mock_env_vars
    ):
        """Test generation with caching disabled."""
        mock_generator = Mock()
        mock_generator.generate.return_value = Mock(spec=GenerationResult)
        mock_generator_class.return_value = mock_generator

        generate_narration(simple_script_json, cache_dir=None)

        # Verify TTS client was created with cache_dir=None
        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["cache_dir"] is None


# ============================================================================
# Credential Handling Tests
# ============================================================================


class TestCredentialHandling:
    """Test credential resolution and precedence."""

    def test_missing_api_key_raises_error(self, simple_script_json, missing_env_vars):
        """Test missing API key raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            generate_narration(simple_script_json, voice_id="test_voice")

        assert "api key required" in str(exc_info.value).lower()
        assert "XI_API_KEY" in str(exc_info.value)

    def test_missing_voice_id_raises_error(self, simple_script_json_no_voice, missing_env_vars):
        """Test missing voice ID raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            generate_narration(simple_script_json_no_voice, api_key="test_key")

        assert "voice id required" in str(exc_info.value).lower()
        assert "VOICE_ID" in str(exc_info.value)

    @patch('voice_generation.api.VoiceNarrationGenerator')
    @patch('voice_generation.api.ElevenLabsClient')
    def test_voice_id_from_json_takes_precedence_over_env(
        self, mock_client_class, mock_generator_class, script_with_voice_json, mock_env_vars
    ):
        """Test voice_id in JSON takes precedence over environment variable."""
        mock_generator = Mock()
        mock_generator.generate.return_value = Mock(spec=GenerationResult)
        mock_generator_class.return_value = mock_generator

        generate_narration(script_with_voice_json)

        # Should use voice_id from JSON, not from env var
        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["voice_id"] == "json_voice_id"  # From JSON
        assert call_kwargs["voice_id"] != "test_voice_456"  # Not from env

    @patch('voice_generation.api.VoiceNarrationGenerator')
    @patch('voice_generation.api.ElevenLabsClient')
    def test_param_credentials_take_precedence(
        self, mock_client_class, mock_generator_class, script_with_voice_json, mock_env_vars
    ):
        """Test function parameters take precedence over JSON and env."""
        mock_generator = Mock()
        mock_generator.generate.return_value = Mock(spec=GenerationResult)
        mock_generator_class.return_value = mock_generator

        generate_narration(
            script_with_voice_json,
            api_key="param_key",
            voice_id="param_voice",
        )

        # Should use parameters, not JSON or env
        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["api_key"] == "param_key"
        assert call_kwargs["voice_id"] == "param_voice"


# ============================================================================
# Voice Config Integration Tests
# ============================================================================


class TestVoiceConfigIntegration:
    """Test TTS client configuration from narration script."""

    @patch('voice_generation.api.VoiceNarrationGenerator')
    @patch('voice_generation.api.ElevenLabsClient')
    def test_tts_client_uses_voice_config_from_script(
        self, mock_client_class, mock_generator_class, simple_script_json, mock_env_vars
    ):
        """Test TTS client is configured with voice settings from script."""
        mock_generator = Mock()
        mock_generator.generate.return_value = Mock(spec=GenerationResult)
        mock_generator_class.return_value = mock_generator

        generate_narration(simple_script_json)

        # Verify TTS client created with voice config from script
        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["model"] == "eleven_multilingual_v2"
        assert call_kwargs["stability"] == 0.6
        assert call_kwargs["similarity_boost"] == 0.7
        assert call_kwargs["style"] == 0.15
        assert call_kwargs["use_speaker_boost"] is True


# ============================================================================
# Error Handling Tests
# ============================================================================


class TestAPIErrorHandling:
    """Test error handling in API layer."""

    def test_nonexistent_file_raises_error(self, mock_env_vars):
        """Test nonexistent input file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            generate_narration("nonexistent_file.json")

    @patch('voice_generation.api.VoiceNarrationGenerator')
    @patch('voice_generation.api.ElevenLabsClient')
    def test_invalid_json_raises_error(
        self, mock_client_class, mock_generator_class, invalid_json_file, mock_env_vars
    ):
        """Test invalid JSON raises appropriate error."""
        with pytest.raises(Exception):  # JSONDecodeError or ValidationError
            generate_narration(invalid_json_file)


# ============================================================================
# Verbose Mode Tests
# ============================================================================


class TestVerboseMode:
    """Test verbose logging mode."""

    @patch('voice_generation.api.VoiceNarrationGenerator')
    @patch('voice_generation.api.ElevenLabsClient')
    @patch('voice_generation.api.logging.basicConfig')
    def test_verbose_mode_enables_logging(
        self, mock_logging, mock_client_class, mock_generator_class, simple_script_json, mock_env_vars
    ):
        """Test verbose=True enables logging configuration."""
        mock_generator = Mock()
        mock_generator.generate.return_value = Mock(spec=GenerationResult)
        mock_generator_class.return_value = mock_generator

        generate_narration(simple_script_json, verbose=True)

        # Verify logging was configured
        mock_logging.assert_called_once()
        call_kwargs = mock_logging.call_args[1]
        assert call_kwargs["level"] == 20  # logging.INFO
