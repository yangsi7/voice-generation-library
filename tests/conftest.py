"""Shared pytest fixtures for voice generation tests.

This module provides reusable test fixtures that can be used across all test files.
Fixtures are automatically discovered by pytest and can be used as function arguments.
"""

import json
import tempfile
from pathlib import Path
from typing import Dict, Any
from unittest.mock import Mock

import pytest
from pydub import AudioSegment

from voice_generation.core.models import (
    Exercise,
    AudioConfig,
    BreathingPattern,
    Segment,
    NarrationScript,
    VoiceConfig,
)
from voice_generation.clients.base import TTSClient
from voice_generation.storage.filesystem import FileSystemStorage


# ============================================================================
# Model Fixtures
# ============================================================================


@pytest.fixture
def sample_exercise() -> Exercise:
    """Sample exercise metadata for testing."""
    return Exercise(
        id="test-exercise-v1",
        title="Test Exercise",
        description="A test breathing exercise for unit tests",
        category="testing",
        tags=["test", "unit"],
        duration_seconds=60,
    )


@pytest.fixture
def sample_audio_config() -> AudioConfig:
    """Sample audio configuration for narration segment."""
    return AudioConfig(
        fragments=["Test narration fragment 1.", "Test narration fragment 2."],
        max_duration_ms=10000,
    )


@pytest.fixture
def sample_breathing_pattern() -> BreathingPattern:
    """Sample breathing pattern for breathing cycle segment."""
    return BreathingPattern(
        inhale_ms=4000,
        exhale_ms=6000,
        repetitions=5,
    )


@pytest.fixture
def sample_narration_segment(sample_audio_config: AudioConfig) -> Segment:
    """Sample narration-type segment."""
    return Segment(
        id="test_narration",
        type="narration",
        audio=sample_audio_config,
    )


@pytest.fixture
def sample_breathing_segment(
    sample_breathing_pattern: BreathingPattern,
    sample_audio_config: AudioConfig,
) -> Segment:
    """Sample breathing_cycle-type segment."""
    audio_config = AudioConfig(
        fragments=["Breathe in.", "Breathe out."],
        max_duration_ms=8000,
        timing="inhale_phase",
    )
    return Segment(
        id="test_breathing",
        type="breathing_cycle",
        breathing=sample_breathing_pattern,
        audio=audio_config,
    )


@pytest.fixture
def sample_voice_config() -> VoiceConfig:
    """Sample voice configuration."""
    return VoiceConfig(
        provider="elevenlabs",
        voice_id="test_voice_123",
        model="eleven_multilingual_v2",
        stability=0.7,
        similarity_boost=0.75,
    )


@pytest.fixture
def sample_narration_script(
    sample_exercise: Exercise,
    sample_narration_segment: Segment,
    sample_breathing_segment: Segment,
    sample_voice_config: VoiceConfig,
) -> NarrationScript:
    """Complete sample narration script with all components."""
    return NarrationScript(
        exercise=sample_exercise,
        segments=[sample_narration_segment, sample_breathing_segment],
        voice_config=sample_voice_config,
    )


@pytest.fixture
def sample_script_dict(
    sample_exercise: Exercise,
    sample_narration_segment: Segment,
    sample_breathing_segment: Segment,
    sample_voice_config: VoiceConfig,
) -> Dict[str, Any]:
    """Sample narration script as dictionary (for JSON testing)."""
    return {
        "exercise": sample_exercise.model_dump(),
        "segments": [
            sample_narration_segment.model_dump(),
            sample_breathing_segment.model_dump(),
        ],
        "voice_config": sample_voice_config.model_dump(),
    }


# ============================================================================
# Audio Fixtures
# ============================================================================


@pytest.fixture
def sample_audio() -> AudioSegment:
    """1-second silent audio segment for testing."""
    return AudioSegment.silent(duration=1000)  # 1 second


@pytest.fixture
def sample_audio_2s() -> AudioSegment:
    """2-second silent audio segment for testing."""
    return AudioSegment.silent(duration=2000)  # 2 seconds


@pytest.fixture
def sample_audio_500ms() -> AudioSegment:
    """500ms silent audio segment for testing."""
    return AudioSegment.silent(duration=500)


@pytest.fixture
def sample_audio_list() -> list[AudioSegment]:
    """List of audio segments for stitching tests."""
    return [
        AudioSegment.silent(duration=1000),
        AudioSegment.silent(duration=1500),
        AudioSegment.silent(duration=2000),
    ]


# ============================================================================
# Mock TTS Client
# ============================================================================


@pytest.fixture
def mock_tts_client() -> Mock:
    """Mocked TTS client that returns 2-second audio for any input."""
    client = Mock(spec=TTSClient)

    # Mock generate_audio to return 2-second silent audio
    client.generate_audio.return_value = AudioSegment.silent(duration=2000)

    # Mock estimate_cost to return realistic cost (ElevenLabs: $0.30 per 1K chars)
    def estimate_cost_side_effect(text):
        return (len(text) / 1000.0) * 0.30

    client.estimate_cost.side_effect = estimate_cost_side_effect

    # Mock statistics
    client.total_characters = 0
    client.total_api_calls = 0
    client.cache_hits = 0
    client.cache_misses = 0

    return client


@pytest.fixture
def mock_tts_client_with_stats() -> Mock:
    """Mocked TTS client with realistic statistics tracking."""
    client = Mock(spec=TTSClient)

    # Track calls
    call_count = {"count": 0}

    def generate_side_effect(text, previous_text=None, next_text=None):
        call_count["count"] += 1
        client.total_api_calls = call_count["count"]
        client.total_characters = len(text)
        return AudioSegment.silent(duration=2000)

    client.generate_audio.side_effect = generate_side_effect
    client.total_characters = 0
    client.total_api_calls = 0
    client.cache_hits = 0
    client.cache_misses = 0

    return client


# ============================================================================
# Storage Fixtures
# ============================================================================


@pytest.fixture
def temp_storage() -> FileSystemStorage:
    """Temporary filesystem storage using system temp directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = FileSystemStorage(tmpdir)
        yield storage
        # Cleanup happens automatically when context exits


@pytest.fixture
def temp_output_dir() -> Path:
    """Temporary output directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
        # Cleanup happens automatically


# ============================================================================
# File Fixtures
# ============================================================================


@pytest.fixture
def sample_json_file(sample_script_dict: Dict[str, Any], tmp_path: Path) -> Path:
    """Temporary JSON file containing sample narration script."""
    json_file = tmp_path / "test_script.json"
    with open(json_file, "w") as f:
        json.dump(sample_script_dict, f, indent=2)
    return json_file


@pytest.fixture
def invalid_json_file(tmp_path: Path) -> Path:
    """Temporary JSON file with invalid content (missing required fields)."""
    json_file = tmp_path / "invalid_script.json"
    with open(json_file, "w") as f:
        json.dump({"invalid": "data"}, f)
    return json_file


@pytest.fixture
def malformed_json_file(tmp_path: Path) -> Path:
    """Temporary file with malformed JSON syntax."""
    json_file = tmp_path / "malformed.json"
    with open(json_file, "w") as f:
        f.write('{"broken": json syntax}')  # Invalid JSON
    return json_file


# ============================================================================
# Cache Fixtures
# ============================================================================


@pytest.fixture
def temp_cache_dir(tmp_path: Path) -> Path:
    """Temporary cache directory for testing."""
    cache_dir = tmp_path / ".test_cache"
    cache_dir.mkdir(exist_ok=True)
    return cache_dir


# ============================================================================
# Environment Fixtures
# ============================================================================


@pytest.fixture
def mock_env_vars(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("XI_API_KEY", "test_api_key_123")
    monkeypatch.setenv("VOICE_ID", "test_voice_456")
    return {
        "XI_API_KEY": "test_api_key_123",
        "VOICE_ID": "test_voice_456",
    }


@pytest.fixture
def missing_env_vars(monkeypatch):
    """Remove environment variables to test error handling."""
    monkeypatch.delenv("XI_API_KEY", raising=False)
    monkeypatch.delenv("VOICE_ID", raising=False)


@pytest.fixture
def simple_script(sample_exercise: Exercise) -> NarrationScript:
    """Simple narration script with 2 segments for testing."""
    return NarrationScript(
        exercise=sample_exercise,
        segments=[
            Segment(
                id="intro",
                type="narration",
                breathing=BreathingPattern(duration_ms=10000, repetitions=1),
                audio=AudioConfig(fragments=["Welcome to this exercise."]),
            ),
            Segment(
                id="practice",
                type="breathing_cycle",
                breathing=BreathingPattern(inhale_ms=4000, exhale_ms=6000, repetitions=3),
                audio=AudioConfig(
                    fragments=["Breathe in slowly.", "Breathe out gently."],
                    max_duration_ms=9000,
                ),
            ),
        ],
        voice_config=VoiceConfig(),
    )


@pytest.fixture
def generator_with_mocks(mock_tts_client: Mock, temp_storage: FileSystemStorage):
    """VoiceNarrationGenerator with mocked TTS client and temp storage."""
    from voice_generation.core.generator import VoiceNarrationGenerator

    generator = VoiceNarrationGenerator(
        tts_client=mock_tts_client,
        storage=temp_storage,
    )
    return generator


@pytest.fixture
def simple_script_json(tmp_path: Path, simple_script: NarrationScript) -> Path:
    """Simple narration script saved as JSON file."""
    json_path = tmp_path / "test_script.json"
    simple_script.to_file(json_path)
    return json_path


@pytest.fixture
def simple_script_json_no_voice(tmp_path: Path, sample_exercise: Exercise) -> Path:
    """Narration script JSON with no voice_id in voice_config."""
    script = NarrationScript(
        exercise=sample_exercise,
        segments=[
            Segment(
                id="intro",
                type="narration",
                breathing=BreathingPattern(duration_ms=5000, repetitions=1),
                audio=AudioConfig(fragments=["Test."]),
            ),
        ],
        voice_config=VoiceConfig(voice_id=None),  # No voice_id
    )
    json_path = tmp_path / "no_voice_script.json"
    script.to_file(json_path)
    return json_path


@pytest.fixture
def script_with_voice_json(tmp_path: Path, sample_exercise: Exercise) -> Path:
    """Narration script JSON with voice_id specified."""
    script = NarrationScript(
        exercise=sample_exercise,
        segments=[
            Segment(
                id="intro",
                type="narration",
                breathing=BreathingPattern(duration_ms=5000, repetitions=1),
                audio=AudioConfig(fragments=["Test."]),
            ),
        ],
        voice_config=VoiceConfig(voice_id="json_voice_id"),
    )
    json_path = tmp_path / "with_voice_script.json"
    script.to_file(json_path)
    return json_path


@pytest.fixture
def invalid_json_file(tmp_path: Path) -> Path:
    """Invalid JSON file for error testing."""
    json_path = tmp_path / "invalid.json"
    json_path.write_text("{invalid json syntax}")
    return json_path
