"""Abstract TTS client interface."""

from abc import ABC, abstractmethod
from typing import Optional

from pydub import AudioSegment


class TTSClient(ABC):
    """Abstract base class for Text-to-Speech clients."""

    @abstractmethod
    def generate_audio(
        self,
        text: str,
        previous_text: Optional[str] = None,
        next_text: Optional[str] = None
    ) -> AudioSegment:
        """
        Generate audio from text using TTS.

        Args:
            text: Text to convert to speech
            previous_text: Previous text for context (improves prosody)
            next_text: Next text for context (improves prosody)

        Returns:
            Generated audio segment

        Raises:
            TTSError: If generation fails
        """
        pass

    @abstractmethod
    def estimate_cost(self, text: str) -> float:
        """
        Estimate cost for generating audio from text.

        Args:
            text: Text to estimate

        Returns:
            Estimated cost in USD

        Note:
            This is an estimate only. Actual costs may vary.
        """
        pass
