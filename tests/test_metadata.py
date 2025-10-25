"""Tests for MetadataBuilder (breath cycle creation and metadata generation).

Test Coverage Goals:
- Breath cycle creation from breathing patterns
- Audio guide mapping (closest match algorithm)
- Voice configuration handling
- JSON metadata structure validation
- Segment metadata aggregation
- Natural vs structured breathing patterns
"""

import pytest
from pathlib import Path

from voice_generation.processors.metadata import MetadataBuilder
from voice_generation.core.models import (
    NarrationScript, Segment, BreathingPattern, AudioConfig, Exercise, VoiceConfig
)
from voice_generation.core.results import SegmentResult


# ============================================================================
# Audio Guide Mapping Tests
# ============================================================================


class TestAudioGuideMapping:
    """Test audio guide file matching algorithm."""

    def test_exact_match(self):
        """Test exact duration match returns correct audio file."""
        audio_map = {
            4000: "4s_audio.mp3",
            5000: "5s_audio.mp3",
            6000: "6s_audio.mp3",
        }

        result = MetadataBuilder._find_closest_audio_guide(5000, audio_map)
        assert result == "5s_audio.mp3"

    def test_closest_match_within_tolerance(self):
        """Test closest match within 2s tolerance."""
        audio_map = {
            4000: "4s_audio.mp3",
            6000: "6s_audio.mp3",
        }

        # 5000ms is equidistant (1000ms) from both 4000 and 6000
        # Algorithm picks first match found (dictionary iteration order)
        result = MetadataBuilder._find_closest_audio_guide(5000, audio_map)
        assert result in ["4s_audio.mp3", "6s_audio.mp3"]  # Either is valid

        # 4500ms is 500ms from 4000, 1500ms from 6000 - should match 4000
        result = MetadataBuilder._find_closest_audio_guide(4500, audio_map)
        assert result == "4s_audio.mp3"

    def test_no_match_beyond_tolerance(self):
        """Test no match returned if beyond 2s tolerance."""
        audio_map = {
            4000: "4s_audio.mp3",
        }

        # 6500ms is 2500ms away from 4000ms (beyond 2s tolerance)
        result = MetadataBuilder._find_closest_audio_guide(6500, audio_map)
        assert result is None

    def test_zero_duration_returns_none(self):
        """Test zero duration returns None."""
        audio_map = {4000: "4s_audio.mp3"}
        result = MetadataBuilder._find_closest_audio_guide(0, audio_map)
        assert result is None

    def test_empty_audio_map_returns_none(self):
        """Test empty audio map returns None."""
        result = MetadataBuilder._find_closest_audio_guide(5000, {})
        assert result is None


# ============================================================================
# Breathing Guides Configuration Tests
# ============================================================================


class TestBreathingGuidesConfiguration:
    """Test creation of breathing guides configuration."""

    def test_structured_breathing_creates_guides(self):
        """Test structured breathing pattern creates audio guides."""
        breathing = BreathingPattern(
            inhale_ms=4000,
            exhale_ms=6000,
            repetitions=10,
        )

        guides = MetadataBuilder._create_breathing_guides(breathing)

        assert len(guides) == 1
        assert "audio_breathing_guide_set" in guides[0]

        guide_set = guides[0]["audio_breathing_guide_set"]
        assert "breathe_in" in guide_set
        assert "breathe_out" in guide_set

        # Check inhale guide
        assert guide_set["breathe_in"]["key"] == "audio_guide/breathing/4in_minimal.mp3"
        assert guide_set["breathe_in"]["sound_level"] == 60

        # Check exhale guide
        assert guide_set["breathe_out"]["key"] == "audio_guide/breathing/6out_minimal.mp3"
        assert guide_set["breathe_out"]["sound_level"] == 60

    def test_natural_breathing_no_guides(self):
        """Test natural breathing pattern creates no audio guides."""
        breathing = BreathingPattern(
            duration_ms=120000,  # Natural breathing
            repetitions=1,
        )

        guides = MetadataBuilder._create_breathing_guides(breathing)
        assert guides == []

    def test_only_inhale_guide(self):
        """Test breathing with only inhale creates only inhale guide."""
        breathing = BreathingPattern(
            inhale_ms=5000,
            exhale_ms=0,  # No exhale
            repetitions=5,
        )

        guides = MetadataBuilder._create_breathing_guides(breathing)
        guide_set = guides[0]["audio_breathing_guide_set"]

        assert "breathe_in" in guide_set
        assert "breathe_out" not in guide_set

    def test_only_exhale_guide(self):
        """Test breathing with only exhale creates only exhale guide."""
        breathing = BreathingPattern(
            inhale_ms=0,  # No inhale
            exhale_ms=7000,
            repetitions=5,
        )

        guides = MetadataBuilder._create_breathing_guides(breathing)
        guide_set = guides[0]["audio_breathing_guide_set"]

        assert "breathe_out" in guide_set
        assert "breathe_in" not in guide_set


# ============================================================================
# Voice Configuration Tests
# ============================================================================


class TestVoiceConfiguration:
    """Test voice configuration creation."""

    def test_create_voices_config(self, tmp_path):
        """Test creating voice configuration from segment result."""
        audio_file = tmp_path / "test_audio.wav"
        audio_file.touch()

        exercise_dir = tmp_path / "exercise-v1"
        exercise_dir.mkdir()

        segment_result = SegmentResult(
            segment_id="intro",
            segment_index=0,
            audio_path=exercise_dir / "intro_0.wav",
            duration_ms=5000,
            fragment_count=2,
        )

        voices = MetadataBuilder._create_voices_config(segment_result, exercise_dir)

        assert len(voices) == 1
        voice = voices[0]

        assert voice["key"] == f"program_panic/{exercise_dir.name}/intro_0.wav"
        assert voice["repetitions"] == 1
        assert voice["sound_level"] == 75
        assert voice["timeout"] == 0


# ============================================================================
# Breath Cycle Creation Tests
# ============================================================================


class TestBreathCycleCreation:
    """Test complete breath cycle object creation."""

    def test_create_breath_cycle_structured(self, tmp_path):
        """Test creating breath cycle with structured breathing."""
        segment = Segment(
            id="practice",
            type="breathing_cycle",
            breathing=BreathingPattern(
                inhale_ms=5000,
                exhale_ms=6000,
                hold_in_ms=2000,
                hold_out_ms=1000,
                repetitions=10,
            ),
            audio=AudioConfig(
                fragments=["Breathe in.", "Breathe out."],
                max_duration_ms=10000,
            ),
        )

        exercise_dir = tmp_path / "test-exercise-v1"
        exercise_dir.mkdir()

        segment_result = SegmentResult(
            segment_id="practice",
            segment_index=0,
            audio_path=exercise_dir / "practice_0.wav",
            duration_ms=5000,
            fragment_count=2,
        )

        cycle = MetadataBuilder._create_breath_cycle(segment, segment_result, exercise_dir)

        # Check breathing pattern
        assert cycle["breathe_in"] == 5000
        assert cycle["breathe_out"] == 6000
        assert cycle["hold_in"] == 2000
        assert cycle["hold_out"] == 1000
        assert cycle["repetitions"] == 10
        assert cycle["natural"] == 0

        # Check voices
        assert len(cycle["voices"]) == 1
        assert "program_panic/test-exercise-v1/practice_0.wav" in cycle["voices"][0]["key"]

        # Check breathing guides
        assert len(cycle["audio_breathing_guides"]) == 1

        # Check empty arrays
        assert cycle["audio_biofeedbacks"] == []
        assert cycle["commands_text"] == []

    def test_create_breath_cycle_natural(self, tmp_path):
        """Test creating breath cycle with natural breathing."""
        segment = Segment(
            id="intro",
            type="narration",
            breathing=BreathingPattern(
                duration_ms=120000,  # Natural breathing
                repetitions=1,
            ),
            audio=AudioConfig(
                fragments=["Welcome to this exercise."],
            ),
        )

        exercise_dir = tmp_path / "test-v1"
        exercise_dir.mkdir()

        segment_result = SegmentResult(
            segment_id="intro",
            segment_index=0,
            audio_path=exercise_dir / "intro_0.wav",
            duration_ms=8000,
            fragment_count=1,
        )

        cycle = MetadataBuilder._create_breath_cycle(segment, segment_result, exercise_dir)

        # Natural breathing
        assert cycle["breathe_in"] == 0
        assert cycle["breathe_out"] == 0
        assert cycle["natural"] == 120000

        # No breathing guides for natural breathing
        assert cycle["audio_breathing_guides"] == []


# ============================================================================
# Segment Metadata Tests
# ============================================================================


class TestSegmentMetadata:
    """Test segment metadata aggregation."""

    def test_build_segments_metadata(self, tmp_path):
        """Test building segment metadata from results."""
        results = [
            SegmentResult(
                segment_id="intro",
                segment_index=0,
                audio_path=tmp_path / "intro_0.wav",
                duration_ms=5000,
                fragment_count=2,
            ),
            SegmentResult(
                segment_id="intro",
                segment_index=1,
                audio_path=tmp_path / "intro_1.wav",
                duration_ms=3000,
                fragment_count=1,
            ),
            SegmentResult(
                segment_id="practice",
                segment_index=0,
                audio_path=tmp_path / "practice_0.wav",
                duration_ms=10000,
                fragment_count=3,
            ),
        ]

        metadata = MetadataBuilder._build_segments_metadata(results)

        # Check structure
        assert "intro" in metadata
        assert "practice" in metadata

        # Check intro has 2 segments
        assert len(metadata["intro"]) == 2
        assert metadata["intro"][0]["segment_index"] == 0
        assert metadata["intro"][0]["duration_ms"] == 5000
        assert metadata["intro"][0]["fragment_count"] == 2

        # Check practice has 1 segment
        assert len(metadata["practice"]) == 1
        assert metadata["practice"][0]["duration_ms"] == 10000

    def test_build_segments_metadata_with_shortening(self, tmp_path):
        """Test segment metadata includes text shortening info."""
        results = [
            SegmentResult(
                segment_id="practice",
                segment_index=0,
                audio_path=tmp_path / "practice_0.wav",
                duration_ms=5000,
                fragment_count=2,
                was_shortened=True,
                original_text="This is a very long piece of text that was too long.",
                shortened_text="This is shorter text.",
            ),
        ]

        metadata = MetadataBuilder._build_segments_metadata(results)

        segment_meta = metadata["practice"][0]
        assert segment_meta["was_shortened"] is True
        assert segment_meta["original_text"] == "This is a very long piece of text that was too long."
        assert segment_meta["shortened_text"] == "This is shorter text."


# ============================================================================
# Complete Metadata Building Tests
# ============================================================================


class TestCompleteMetadataBuilding:
    """Test complete metadata building workflow."""

    def test_build_metadata_complete(self, tmp_path):
        """Test building complete metadata structure."""
        script = NarrationScript(
            exercise=Exercise(
                title="Test Exercise",
                id="test-exercise-v1",
                category="calm",
                tags=["beginner", "stress"],
                description="A test breathing exercise",
            ),
            segments=[
                Segment(
                    id="intro",
                    type="narration",
                    breathing=BreathingPattern(duration_ms=10000, repetitions=1),
                    audio=AudioConfig(fragments=["Welcome."]),
                ),
                Segment(
                    id="practice",
                    type="breathing_cycle",
                    breathing=BreathingPattern(
                        inhale_ms=4000,
                        exhale_ms=6000,
                        repetitions=5,
                    ),
                    audio=AudioConfig(
                        fragments=["Breathe in.", "Breathe out."],
                        max_duration_ms=9000,
                    ),
                ),
            ],
            voice_config=VoiceConfig(),
        )

        exercise_dir = tmp_path / "test-exercise-v1"
        exercise_dir.mkdir()

        segment_results = [
            SegmentResult(
                segment_id="intro",
                segment_index=0,
                audio_path=exercise_dir / "intro_0.wav",
                duration_ms=5000,
                fragment_count=1,
            ),
            SegmentResult(
                segment_id="practice",
                segment_index=0,
                audio_path=exercise_dir / "practice_0.wav",
                duration_ms=8000,
                fragment_count=2,
            ),
        ]

        metadata = MetadataBuilder.build_metadata(script, segment_results, exercise_dir)

        # Check top-level fields
        assert metadata["exercise_title"] == "Test Exercise"
        assert metadata["exercise_id"] == "test-exercise-v1"
        assert metadata["category"] == "calm"
        assert metadata["tags"] == ["beginner", "stress"]
        assert metadata["description"] == "A test breathing exercise"

        # Check segments
        assert "intro" in metadata["segments"]
        assert "practice" in metadata["segments"]

        # Check breath cycles (should have 2: intro + practice)
        assert len(metadata["breath_cycles"]) == 2

    def test_build_metadata_skips_narration_only(self, tmp_path):
        """Test narration-only segments (no breathing) are skipped in breath_cycles."""
        script = NarrationScript(
            exercise=Exercise(
                title="Test",
                id="test-v1",
            ),
            segments=[
                Segment(
                    id="narration",
                    type="narration",
                    breathing=None,  # No breathing pattern
                    audio=AudioConfig(fragments=["Just narration."]),
                ),
            ],
            voice_config=VoiceConfig(),
        )

        exercise_dir = tmp_path / "test-v1"
        exercise_dir.mkdir()

        segment_results = [
            SegmentResult(
                segment_id="narration",
                segment_index=0,
                audio_path=exercise_dir / "narration_0.wav",
                duration_ms=3000,
                fragment_count=1,
            ),
        ]

        metadata = MetadataBuilder.build_metadata(script, segment_results, exercise_dir)

        # Should have segments but no breath cycles
        assert "narration" in metadata["segments"]
        assert len(metadata["breath_cycles"]) == 0

    def test_build_metadata_missing_segment_result(self, tmp_path):
        """Test metadata building handles missing segment results gracefully."""
        script = NarrationScript(
            exercise=Exercise(title="Test", id="test-v1"),
            segments=[
                Segment(
                    id="practice",
                    type="breathing_cycle",
                    breathing=BreathingPattern(inhale_ms=4000, exhale_ms=6000, repetitions=5),
                    audio=AudioConfig(fragments=["Breathe."]),
                ),
            ],
            voice_config=VoiceConfig(),
        )

        exercise_dir = tmp_path / "test-v1"
        exercise_dir.mkdir()

        # No segment results provided
        segment_results = []

        metadata = MetadataBuilder.build_metadata(script, segment_results, exercise_dir)

        # Should have empty segments and no breath cycles
        assert metadata["segments"] == {}
        assert metadata["breath_cycles"] == []
