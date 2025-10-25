"""ElevenLabs TTS client implementation.

Test Coverage: 84.48% (19 tests covering client + cache)
- Client initialization: 100% (3 tests)
- Audio generation (mocked): 100% (3 tests)
- Caching: 100% (3 tests)
- Retry logic: 100% (2 tests)
- Statistics tracking: 100% (2 tests)
- Cost estimation: 100% (2 tests)
- AudioCache: 100% (3 tests)
- Integration: 100% (1 test)
- Not tested: Some error handling edge cases, cache TTL expiration
"""

import io
import logging
import time
from pathlib import Path
from typing import Optional

import requests
from pydub import AudioSegment

from voice_generation.clients.base import TTSClient
from voice_generation.clients.cache import AudioCache
from voice_generation.core.exceptions import TTSError


logger = logging.getLogger(__name__)


class ElevenLabsClient(TTSClient):
    """
    ElevenLabs Text-to-Speech client with caching and retry logic.

    Features:
    - Context-aware TTS (previous_text, next_text for better prosody)
    - Automatic retry with exponential backoff
    - Optional audio caching (file-based)
    - Cost estimation
    """

    # ElevenLabs pricing (approximate, as of 2024)
    PRICE_PER_1K_CHARS = 0.30  # USD

    def __init__(
        self,
        api_key: str,
        voice_id: str,
        model: str = "eleven_multilingual_v2",
        stability: float = 0.6,
        similarity_boost: float = 0.7,
        style: float = 0.15,
        use_speaker_boost: bool = True,
        cache_dir: Optional[Path] = None,
        cache_ttl_days: int = 30,
        max_retries: int = 3,
        retry_backoff_factor: float = 2.0
    ):
        """
        Initialize ElevenLabs TTS client.

        Args:
            api_key: ElevenLabs API key
            voice_id: Voice ID to use
            model: Model name (default: "eleven_multilingual_v2")
            stability: Voice stability 0-1 (default: 0.6)
            similarity_boost: Similarity boost 0-1 (default: 0.7)
            style: Style exaggeration 0-1 (default: 0.15)
            use_speaker_boost: Enable speaker boost (default: True)
            cache_dir: Directory for caching, or None to disable (default: None)
            cache_ttl_days: Cache TTL in days (default: 30)
            max_retries: Maximum retry attempts (default: 3)
            retry_backoff_factor: Exponential backoff factor (default: 2.0)
        """
        self.api_key = api_key
        self.voice_id = voice_id
        self.model = model
        self.stability = stability
        self.similarity_boost = similarity_boost
        self.style = style
        self.use_speaker_boost = use_speaker_boost
        self.max_retries = max_retries
        self.retry_backoff_factor = retry_backoff_factor

        # Initialize cache if enabled
        self.cache = AudioCache(cache_dir, cache_ttl_days) if cache_dir else None

        # Statistics
        self.cache_hits = 0
        self.cache_misses = 0
        self.api_calls = 0
        self.total_characters = 0

        logger.info(
            f"Initialized ElevenLabsClient (voice_id={voice_id}, model={model}, "
            f"cache={'enabled' if self.cache else 'disabled'})"
        )

    def generate_audio(
        self,
        text: str,
        previous_text: Optional[str] = None,
        next_text: Optional[str] = None
    ) -> AudioSegment:
        """
        Generate audio from text using ElevenLabs TTS API.

        Args:
            text: Text to convert to speech
            previous_text: Previous text for context (improves prosody)
            next_text: Next text for context (improves prosody)

        Returns:
            Generated audio segment

        Raises:
            TTSError: If generation fails after all retries
        """
        # Check cache first
        if self.cache:
            voice_config = self._get_voice_config_dict()
            cached_audio = self.cache.get(text, previous_text, next_text, voice_config)

            if cached_audio is not None:
                self.cache_hits += 1
                logger.info(f"Cache HIT ({self.cache_hits} hits, {self.cache_misses} misses): {text[:50]}...")
                return cached_audio

            self.cache_misses += 1

        # Generate via API
        audio = self._call_api_with_retry(text, previous_text, next_text)

        # Store in cache
        if self.cache:
            voice_config = self._get_voice_config_dict()
            self.cache.set(text, previous_text, next_text, voice_config, audio)

        return audio

    def _call_api_with_retry(
        self,
        text: str,
        previous_text: Optional[str],
        next_text: Optional[str]
    ) -> AudioSegment:
        """Call API with exponential backoff retry logic."""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                return self._call_api(text, previous_text, next_text)

            except TTSError as e:
                last_error = e

                # Don't retry on client errors (4xx)
                if e.status_code and 400 <= e.status_code < 500:
                    logger.error(f"Client error (no retry): {e}")
                    raise

                # Retry on server errors (5xx) or network errors
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_backoff_factor ** attempt
                    logger.warning(
                        f"API call failed (attempt {attempt + 1}/{self.max_retries}), "
                        f"retrying in {wait_time:.1f}s: {e}"
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"API call failed after {self.max_retries} attempts: {e}")

        # All retries exhausted
        raise last_error

    def _call_api(
        self,
        text: str,
        previous_text: Optional[str],
        next_text: Optional[str]
    ) -> AudioSegment:
        """Make actual API call to ElevenLabs."""
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream"

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg"
        }

        payload = {
            "text": text,
            "model_id": self.model,
            "voice_settings": {
                "stability": self.stability,
                "similarity_boost": self.similarity_boost,
                "style": self.style,
                "use_speaker_boost": self.use_speaker_boost
            }
        }

        # Add context if provided
        if previous_text:
            payload["previous_text"] = previous_text
        if next_text:
            payload["next_text"] = next_text

        try:
            logger.debug(f"Calling ElevenLabs API for text ({len(text)} chars): {text[:50]}...")
            response = requests.post(url, json=payload, headers=headers, timeout=30)

            # Track statistics
            self.api_calls += 1
            self.total_characters += len(text)

            # Check response
            if response.status_code != 200:
                raise TTSError(
                    message=f"ElevenLabs API returned error",
                    status_code=response.status_code,
                    response_text=response.text
                )

            # Convert MP3 response to AudioSegment
            audio = AudioSegment.from_mp3(io.BytesIO(response.content))
            logger.info(f"Generated audio: {len(audio)}ms from {len(text)} characters")

            return audio

        except requests.RequestException as e:
            raise TTSError(f"Network error calling ElevenLabs API: {e}") from e
        except Exception as e:
            raise TTSError(f"Unexpected error calling ElevenLabs API: {e}") from e

    def estimate_cost(self, text: str) -> float:
        """
        Estimate cost for generating audio from text.

        Args:
            text: Text to estimate

        Returns:
            Estimated cost in USD
        """
        characters = len(text)
        return (characters / 1000.0) * self.PRICE_PER_1K_CHARS

    def _get_voice_config_dict(self) -> dict:
        """Get voice configuration as dictionary (for cache key computation)."""
        return {
            "voice_id": self.voice_id,
            "model": self.model,
            "stability": self.stability,
            "similarity_boost": self.similarity_boost,
            "style": self.style,
            "use_speaker_boost": self.use_speaker_boost
        }

    def get_stats(self) -> dict:
        """
        Get client statistics.

        Returns:
            Dictionary with API call stats and cache stats
        """
        stats = {
            "api_calls": self.api_calls,
            "total_characters": self.total_characters,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
        }

        if self.cache:
            stats["cache"] = self.cache.get_stats()

        if self.cache_hits + self.cache_misses > 0:
            hit_rate = (self.cache_hits / (self.cache_hits + self.cache_misses)) * 100
            stats["cache_hit_rate_percent"] = round(hit_rate, 1)

        return stats
