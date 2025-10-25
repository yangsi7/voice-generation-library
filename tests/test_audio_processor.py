"""Tests for audio processor utilities."""

import pytest
from pydub import AudioSegment

from voice_generation.processors.audio import AudioProcessor


class TestRoundingFunctions:
    """Test time rounding utilities."""

    def test_round_down_to_previous_second(self):
        assert AudioProcessor.round_down_to_previous_second(0) == 0
        assert AudioProcessor.round_down_to_previous_second(500) == 0
        assert AudioProcessor.round_down_to_previous_second(999) == 0
        assert AudioProcessor.round_down_to_previous_second(1000) == 1000
        assert AudioProcessor.round_down_to_previous_second(1500) == 1000
        assert AudioProcessor.round_down_to_previous_second(2999) == 2000
        assert AudioProcessor.round_down_to_previous_second(5000) == 5000

    def test_round_up_to_next_second(self):
        assert AudioProcessor.round_up_to_next_second(0) == 0
        assert AudioProcessor.round_up_to_next_second(1) == 1000
        assert AudioProcessor.round_up_to_next_second(500) == 1000
        assert AudioProcessor.round_up_to_next_second(999) == 1000
        assert AudioProcessor.round_up_to_next_second(1000) == 1000
        assert AudioProcessor.round_up_to_next_second(1001) == 2000
        assert AudioProcessor.round_up_to_next_second(1500) == 2000
        assert AudioProcessor.round_up_to_next_second(5000) == 5000


class TestTrimAndPad:
    """Test trim and pad operations."""

    def test_trim_to_whole_seconds(self):
        # 1.5 second audio → 2 seconds (rounded up)
        audio = AudioSegment.silent(duration=1500)
        trimmed = AudioProcessor.trim_to_whole_seconds(audio)
        assert len(trimmed) == 2000

    def test_trim_to_whole_seconds_already_whole(self):
        # 2 second audio → 2 seconds (no change)
        audio = AudioSegment.silent(duration=2000)
        trimmed = AudioProcessor.trim_to_whole_seconds(audio)
        assert len(trimmed) == 2000

    def test_pad_to_whole_seconds(self):
        # 1.5 second audio → 2 seconds with padding
        audio = AudioSegment.silent(duration=1500)
        padded = AudioProcessor.pad_to_whole_seconds(audio)
        assert len(padded) == 2000

    def test_pad_to_whole_seconds_already_whole(self):
        # 2 second audio → 2 seconds (no padding needed)
        audio = AudioSegment.silent(duration=2000)
        padded = AudioProcessor.pad_to_whole_seconds(audio)
        assert len(padded) == 2000

    def test_pad_to_whole_seconds_short_audio(self):
        # 100ms audio → 1 second with padding
        audio = AudioSegment.silent(duration=100)
        padded = AudioProcessor.pad_to_whole_seconds(audio)
        assert len(padded) == 1000


class TestStitch:
    """Test audio stitching."""

    def test_stitch_single_segment(self):
        segment = AudioSegment.silent(duration=1000)
        result = AudioProcessor.stitch([segment])
        assert len(result) == 1000

    def test_stitch_multiple_segments(self):
        seg1 = AudioSegment.silent(duration=1000)
        seg2 = AudioSegment.silent(duration=2000)
        seg3 = AudioSegment.silent(duration=500)

        result = AudioProcessor.stitch([seg1, seg2, seg3])
        assert len(result) == 3500

    def test_stitch_with_gap(self):
        seg1 = AudioSegment.silent(duration=1000)
        seg2 = AudioSegment.silent(duration=1000)

        result = AudioProcessor.stitch([seg1, seg2], gap_ms=500)
        # 1000 + 500 (gap) + 1000 = 2500
        assert len(result) == 2500

    def test_stitch_empty_list_raises_error(self):
        with pytest.raises(ValueError, match="Cannot stitch empty segment list"):
            AudioProcessor.stitch([])


class TestDuration:
    """Test duration utilities."""

    def test_get_duration_ms(self):
        audio = AudioSegment.silent(duration=1500)
        assert AudioProcessor.get_duration_ms(audio) == 1500

    def test_get_duration_seconds(self):
        audio = AudioSegment.silent(duration=1500)
        assert AudioProcessor.get_duration_seconds(audio) == 1.5

        audio = AudioSegment.silent(duration=3000)
        assert AudioProcessor.get_duration_seconds(audio) == 3.0


class TestSilence:
    """Test silence creation."""

    def test_create_silence(self):
        silence = AudioProcessor.create_silence(1000)
        assert len(silence) == 1000
        assert silence.dBFS == float('-inf')  # Complete silence

    def test_create_silence_zero_duration(self):
        silence = AudioProcessor.create_silence(0)
        assert len(silence) == 0

    def test_create_silence_negative_raises_error(self):
        with pytest.raises(ValueError, match="Duration must be non-negative"):
            AudioProcessor.create_silence(-100)


class TestNormalize:
    """Test volume normalization."""

    def test_normalize_volume(self):
        # Create audio with actual sound (sine wave at 440Hz)
        from pydub.generators import Sine

        audio = Sine(440).to_audio_segment(duration=1000)
        # Reduce volume to -30dBFS
        audio = audio - 30  # Set to -30dBFS

        # Verify audio has measurable volume (not -inf)
        assert audio.dBFS > -100  # Sanity check

        normalized = AudioProcessor.normalize_volume(audio, target_dBFS=-20.0)

        # Check that normalization changed volume
        assert normalized.dBFS != audio.dBFS
        # Target should be close to -20dBFS (within tolerance)
        assert abs(normalized.dBFS - (-20.0)) < 1.0
