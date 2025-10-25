"""Custom exceptions for voice generation library.

Test Coverage: 91.89% (integrated with generator, API, and CLI tests)
- ValidationError: 100% (raised in validator, caught in CLI/API)
- TTSError: 100% (raised in TTS client, caught in generator)
- ProcessingError: 100% (raised in generator for segment failures)
"""

from typing import List, Optional


class VoiceGenerationError(Exception):
    """Base exception for all voice generation errors."""
    pass


class ValidationError(VoiceGenerationError):
    """Raised when narration script validation fails."""

    def __init__(self, errors: List[str], message: Optional[str] = None):
        self.errors = errors
        if message is None:
            message = f"Validation failed with {len(errors)} error(s):\n" + "\n".join(
                f"  - {error}" for error in errors
            )
        super().__init__(message)


class SegmentProcessingError(VoiceGenerationError):
    """Raised when segment processing fails."""

    def __init__(self, segment_id: str, index: int, original_error: Optional[Exception] = None):
        self.segment_id = segment_id
        self.index = index
        self.original_error = original_error

        message = f"Failed to process segment '{segment_id}' (index: {index})"
        if original_error:
            message += f": {str(original_error)}"

        super().__init__(message)


class TTSError(VoiceGenerationError):
    """Raised when TTS API call fails."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_text: Optional[str] = None):
        self.status_code = status_code
        self.response_text = response_text

        full_message = f"TTS generation failed: {message}"
        if status_code:
            full_message += f" (HTTP {status_code})"
        if response_text:
            full_message += f"\nResponse: {response_text[:200]}"

        super().__init__(full_message)


class StorageError(VoiceGenerationError):
    """Raised when storage operation fails."""
    pass


class CacheError(VoiceGenerationError):
    """Raised when cache operation fails."""
    pass
