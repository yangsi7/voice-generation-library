"""Audio processing utilities (trim, pad, stitch, duration calculations).

Test Coverage: 77.78% (17 tests)
- Rounding functions: 100%
- Trim and pad operations: 100%
- Audio stitching: 100% (except crossfade feature)
- Duration utilities: 100%
- Silence creation: 100%
- Volume normalization: 100%
- Not tested: trim_silence(), stitch crossfade, mix_with_background()
"""

import math
import logging
from typing import List, Optional

from pydub import AudioSegment
from pydub.silence import detect_nonsilent


logger = logging.getLogger(__name__)


class AudioProcessor:
    """Audio processing utilities for voice narration generation."""

    @staticmethod
    def round_down_to_previous_second(ms: int) -> int:
        """
        Round milliseconds down to previous whole second.

        Args:
            ms: Time in milliseconds

        Returns:
            Rounded milliseconds (floor to nearest second)

        Example:
            >>> AudioProcessor.round_down_to_previous_second(1500)
            1000
            >>> AudioProcessor.round_down_to_previous_second(999)
            0
        """
        return (ms // 1000) * 1000

    @staticmethod
    def round_up_to_next_second(ms: int) -> int:
        """
        Round milliseconds up to next whole second.

        Args:
            ms: Time in milliseconds

        Returns:
            Rounded milliseconds (ceil to nearest second)

        Example:
            >>> AudioProcessor.round_up_to_next_second(1001)
            2000
            >>> AudioProcessor.round_up_to_next_second(1000)
            1000
        """
        return math.ceil(ms / 1000) * 1000

    @staticmethod
    def trim_to_whole_seconds(audio: AudioSegment) -> AudioSegment:
        """
        Trim or pad audio to whole second boundaries.

        Args:
            audio: Input audio segment

        Returns:
            Audio adjusted to nearest whole second (padded if short, trimmed if over)

        Example:
            1.5s audio → 2.0s audio (0ms to 2000ms, padded with silence)
        """
        current_duration_ms = len(audio)
        target_duration_ms = AudioProcessor.round_up_to_next_second(current_duration_ms)

        if current_duration_ms < target_duration_ms:
            # Pad with silence to reach target
            silence_needed = target_duration_ms - current_duration_ms
            return audio + AudioSegment.silent(duration=silence_needed)
        else:
            # Already at or over target, just return up to target
            return audio[:target_duration_ms]

    @staticmethod
    def pad_to_whole_seconds(audio: AudioSegment) -> AudioSegment:
        """
        Pad audio with silence to reach next whole second.

        Args:
            audio: Input audio segment

        Returns:
            Padded audio with silence appended

        Example:
            1.5s audio → 2.0s audio (1.5s audio + 0.5s silence)
        """
        current_length_ms = len(audio)
        target_length_ms = AudioProcessor.round_up_to_next_second(current_length_ms)
        padding_ms = target_length_ms - current_length_ms

        if padding_ms > 0:
            silence = AudioSegment.silent(duration=padding_ms)
            return audio + silence

        return audio

    @staticmethod
    def trim_silence(
        audio: AudioSegment,
        silence_threshold: float = -50.0,
        chunk_size: int = 10,
        keep_silence_ms: int = 100
    ) -> AudioSegment:
        """
        Trim silence from beginning and end of audio.

        Args:
            audio: Input audio segment
            silence_threshold: dBFS threshold for silence detection (default: -50.0)
            chunk_size: Chunk size in milliseconds for silence detection (default: 10ms)
            keep_silence_ms: Amount of silence to keep at edges (default: 100ms)

        Returns:
            Trimmed audio with silence removed

        Example:
            [100ms silence][2s audio][200ms silence] → [2s audio] (with small silence padding)
        """
        # Detect non-silent ranges
        nonsilent_ranges = detect_nonsilent(
            audio,
            min_silence_len=chunk_size,
            silence_thresh=silence_threshold,
            seek_step=1
        )

        if not nonsilent_ranges:
            logger.warning("No non-silent audio detected, returning original")
            return audio

        # Get first and last non-silent timestamps
        start_trim = max(0, nonsilent_ranges[0][0] - keep_silence_ms)
        end_trim = min(len(audio), nonsilent_ranges[-1][1] + keep_silence_ms)

        return audio[start_trim:end_trim]

    @staticmethod
    def stitch(
        segments: List[AudioSegment],
        gap_ms: int = 0,
        crossfade_ms: int = 0
    ) -> AudioSegment:
        """
        Concatenate multiple audio segments with optional gaps or crossfades.

        Args:
            segments: List of audio segments to stitch together
            gap_ms: Silence gap between segments in milliseconds (default: 0)
            crossfade_ms: Crossfade duration in milliseconds (default: 0)

        Returns:
            Stitched audio segment

        Raises:
            ValueError: If segments list is empty

        Example:
            stitch([seg1, seg2, seg3], gap_ms=500) → seg1 + 500ms silence + seg2 + 500ms silence + seg3
        """
        if not segments:
            raise ValueError("Cannot stitch empty segment list")

        if len(segments) == 1:
            return segments[0]

        result = segments[0]

        for segment in segments[1:]:
            if crossfade_ms > 0:
                # Crossfade overlaps the end of current with start of next
                result = result.append(segment, crossfade=crossfade_ms)
            else:
                # Simple concatenation with optional gap
                if gap_ms > 0:
                    result += AudioSegment.silent(duration=gap_ms)
                result += segment

        return result

    @staticmethod
    def get_duration_ms(audio: AudioSegment) -> int:
        """
        Get audio duration in milliseconds.

        Args:
            audio: Audio segment

        Returns:
            Duration in milliseconds
        """
        return len(audio)

    @staticmethod
    def get_duration_seconds(audio: AudioSegment) -> float:
        """
        Get audio duration in seconds.

        Args:
            audio: Audio segment

        Returns:
            Duration in seconds (float)
        """
        return len(audio) / 1000.0

    @staticmethod
    def create_silence(duration_ms: int) -> AudioSegment:
        """
        Create silent audio segment.

        Args:
            duration_ms: Duration in milliseconds

        Returns:
            Silent audio segment

        Raises:
            ValueError: If duration_ms is negative
        """
        if duration_ms < 0:
            raise ValueError(f"Duration must be non-negative, got {duration_ms}ms")

        return AudioSegment.silent(duration=duration_ms)

    @staticmethod
    def mix_with_background(
        voice: AudioSegment,
        background: AudioSegment,
        voice_volume_db: float = 0,
        background_volume_db: float = -20
    ) -> AudioSegment:
        """
        Mix voice with background audio (e.g., music, nature sounds).

        Args:
            voice: Primary voice audio
            background: Background audio
            voice_volume_db: Voice volume adjustment in dB (default: 0 = no change)
            background_volume_db: Background volume adjustment in dB (default: -20 = quieter)

        Returns:
            Mixed audio segment

        Note:
            Background is looped if shorter than voice, or trimmed if longer.
        """
        # Adjust volumes
        voice = voice + voice_volume_db
        background = background + background_volume_db

        # Match lengths (loop or trim background)
        voice_duration = len(voice)
        background_duration = len(background)

        if background_duration < voice_duration:
            # Loop background to match voice duration
            repeats = math.ceil(voice_duration / background_duration)
            background = background * repeats

        # Trim background to voice length
        background = background[:voice_duration]

        # Overlay (mix)
        return voice.overlay(background)

    @staticmethod
    def normalize_volume(audio: AudioSegment, target_dBFS: float = -20.0) -> AudioSegment:
        """
        Normalize audio to target dBFS level.

        Args:
            audio: Input audio
            target_dBFS: Target dBFS level (default: -20.0)

        Returns:
            Normalized audio

        Example:
            Quiet audio → boosted to -20dBFS
            Loud audio → reduced to -20dBFS
        """
        change_in_dBFS = target_dBFS - audio.dBFS
        return audio + change_in_dBFS
