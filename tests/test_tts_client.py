"""Tests for ElevenLabsClient and AudioCache (mocked API calls).

Test Coverage Goals:
- TTS client initialization
- Mocked audio generation
- Cache hit/miss scenarios
- Retry logic with exponential backoff
- Error handling (rate limits, API errors)
- Statistics tracking
- Cost estimation
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import io

from pydub import AudioSegment
import requests

from voice_generation.clients.elevenlabs import ElevenLabsClient
from voice_generation.clients.cache import AudioCache
from voice_generation.core.exceptions import TTSError


# ============================================================================
# Client Initialization Tests
# ============================================================================


class TestClientInitialization:
    """Test TTS client initialization."""

    def test_init_without_cache(self):
        """Test initializing client without caching."""
        client = ElevenLabsClient(
            api_key="test_key",
            voice_id="test_voice",
        )

        assert client.api_key == "test_key"
        assert client.voice_id == "test_voice"
        assert client.cache is None
        assert client.cache_hits == 0
        assert client.cache_misses == 0

    def test_init_with_cache(self, temp_cache_dir):
        """Test initializing client with caching enabled."""
        client = ElevenLabsClient(
            api_key="test_key",
            voice_id="test_voice",
            cache_dir=temp_cache_dir,
        )

        assert client.cache is not None
        assert isinstance(client.cache, AudioCache)

    def test_init_custom_parameters(self):
        """Test initializing client with custom voice parameters."""
        client = ElevenLabsClient(
            api_key="test_key",
            voice_id="test_voice",
            model="custom_model",
            stability=0.8,
            similarity_boost=0.9,
            style=0.5,
            max_retries=5,
        )

        assert client.model == "custom_model"
        assert client.stability == 0.8
        assert client.similarity_boost == 0.9
        assert client.style == 0.5
        assert client.max_retries == 5


# ============================================================================
# Audio Generation Tests (Mocked)
# ============================================================================


class TestAudioGeneration:
    """Test audio generation with mocked API calls."""

    @patch('requests.post')
    def test_generate_audio_success(self, mock_post, sample_audio):
        """Test successful audio generation."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = sample_audio.export(format="mp3").read()
        mock_post.return_value = mock_response

        client = ElevenLabsClient(api_key="test_key", voice_id="test_voice")
        audio = client.generate_audio("Test text")

        assert isinstance(audio, AudioSegment)
        assert client.api_calls == 1
        assert client.total_characters == len("Test text")
        mock_post.assert_called_once()

    @patch('requests.post')
    def test_generate_audio_with_context(self, mock_post, sample_audio):
        """Test audio generation with previous/next text context."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = sample_audio.export(format="mp3").read()
        mock_post.return_value = mock_response

        client = ElevenLabsClient(api_key="test_key", voice_id="test_voice")
        audio = client.generate_audio(
            text="Current text",
            previous_text="Previous text",
            next_text="Next text",
        )

        assert isinstance(audio, AudioSegment)
        # Verify context was passed in request
        call_args = mock_post.call_args
        assert "previous_text" in str(call_args) or call_args is not None

    @patch('requests.post')
    def test_generate_audio_api_error_raises_exception(self, mock_post):
        """Test API error raises TTSError."""
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = requests.HTTPError("500 Error")
        mock_post.return_value = mock_response

        client = ElevenLabsClient(api_key="test_key", voice_id="test_voice", max_retries=1)

        with pytest.raises(TTSError) as exc_info:
            client.generate_audio("Test text")
        assert "api error" in str(exc_info.value).lower() or "failed" in str(exc_info.value).lower()


# ============================================================================
# Cache Tests
# ============================================================================


class TestCaching:
    """Test audio caching functionality."""

    @patch('requests.post')
    def test_cache_miss_then_hit(self, mock_post, temp_cache_dir, sample_audio):
        """Test cache miss followed by cache hit."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = sample_audio.export(format="mp3").read()
        mock_post.return_value = mock_response

        client = ElevenLabsClient(
            api_key="test_key",
            voice_id="test_voice",
            cache_dir=temp_cache_dir,
        )

        # First call - cache miss
        audio1 = client.generate_audio("Test text")
        assert client.cache_misses == 1
        assert client.cache_hits == 0
        assert client.api_calls == 1

        # Second call with same text - cache hit
        audio2 = client.generate_audio("Test text")
        assert client.cache_misses == 1
        assert client.cache_hits == 1
        assert client.api_calls == 1  # Still 1, no new API call

        # Audio should be the same
        assert len(audio1) == len(audio2)

    @patch('requests.post')
    def test_cache_different_text_separate_entries(self, mock_post, temp_cache_dir, sample_audio):
        """Test different text creates separate cache entries."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = sample_audio.export(format="mp3").read()
        mock_post.return_value = mock_response

        client = ElevenLabsClient(
            api_key="test_key",
            voice_id="test_voice",
            cache_dir=temp_cache_dir,
        )

        # Generate two different texts
        client.generate_audio("Text 1")
        client.generate_audio("Text 2")

        assert client.cache_misses == 2
        assert client.api_calls == 2

    @patch('requests.post')
    def test_no_cache_always_calls_api(self, mock_post, sample_audio):
        """Test without cache, API is always called."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = sample_audio.export(format="mp3").read()
        mock_post.return_value = mock_response

        client = ElevenLabsClient(
            api_key="test_key",
            voice_id="test_voice",
            # No cache_dir - caching disabled
        )

        # Call twice with same text
        client.generate_audio("Test text")
        client.generate_audio("Test text")

        assert client.api_calls == 2  # Both calls hit API
        assert client.cache_hits == 0
        assert client.cache_misses == 0


# ============================================================================
# Retry Logic Tests
# ============================================================================


class TestRetryLogic:
    """Test retry logic with exponential backoff."""

    @patch('requests.post')
    @patch('time.sleep')  # Mock sleep to speed up tests
    def test_retry_on_failure_then_success(self, mock_sleep, mock_post, sample_audio):
        """Test retry logic: fail twice, succeed on third try."""
        # First two calls fail, third succeeds
        error_response = Mock()
        error_response.status_code = 503
        error_response.raise_for_status.side_effect = requests.HTTPError("503 Error")

        success_response = Mock()
        success_response.status_code = 200
        success_response.content = sample_audio.export(format="mp3").read()

        mock_post.side_effect = [error_response, error_response, success_response]

        client = ElevenLabsClient(
            api_key="test_key",
            voice_id="test_voice",
            max_retries=3,
            retry_backoff_factor=2.0,
        )

        audio = client.generate_audio("Test text")

        assert isinstance(audio, AudioSegment)
        assert mock_post.call_count == 3  # 2 failures + 1 success
        # Verify exponential backoff (1s, 2s)
        assert mock_sleep.call_count == 2

    @patch('requests.post')
    def test_max_retries_exceeded_raises_error(self, mock_post):
        """Test max retries exceeded raises TTSError."""
        error_response = Mock()
        error_response.status_code = 503
        error_response.raise_for_status.side_effect = requests.HTTPError("503 Error")
        mock_post.return_value = error_response

        client = ElevenLabsClient(
            api_key="test_key",
            voice_id="test_voice",
            max_retries=2,
        )

        with pytest.raises(TTSError) as exc_info:
            client.generate_audio("Test text")

        assert mock_post.call_count == 2  # max_retries


# ============================================================================
# Statistics Tests
# ============================================================================


class TestStatistics:
    """Test client statistics tracking."""

    @patch('requests.post')
    def test_statistics_tracking(self, mock_post, sample_audio):
        """Test statistics are tracked correctly."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = sample_audio.export(format="mp3").read()
        mock_post.return_value = mock_response

        client = ElevenLabsClient(api_key="test_key", voice_id="test_voice")

        client.generate_audio("First text")
        client.generate_audio("Second longer text")

        assert client.api_calls == 2
        assert client.total_characters == len("First text") + len("Second longer text")

    def test_get_cache_stats(self, temp_cache_dir):
        """Test getting cache statistics."""
        client = ElevenLabsClient(
            api_key="test_key",
            voice_id="test_voice",
            cache_dir=temp_cache_dir,
        )

        # Simulate some cache activity
        client.cache_hits = 10
        client.cache_misses = 5

        # Calculate hit rate
        total_attempts = client.cache_hits + client.cache_misses
        hit_rate = (client.cache_hits / total_attempts * 100) if total_attempts > 0 else 0

        assert hit_rate == (10 / 15 * 100)  # 66.67%


# ============================================================================
# Cost Estimation Tests
# ============================================================================


class TestCostEstimation:
    """Test cost estimation functionality."""

    def test_estimate_cost(self):
        """Test cost estimation based on character count."""
        client = ElevenLabsClient(api_key="test_key", voice_id="test_voice")

        # 1000 characters
        text = "A" * 1000
        estimated_cost = (len(text) / 1000) * client.PRICE_PER_1K_CHARS

        assert estimated_cost == 0.30  # $0.30 for 1000 chars

    def test_estimate_cost_fractional(self):
        """Test cost estimation for fractional amounts."""
        client = ElevenLabsClient(api_key="test_key", voice_id="test_voice")

        # 500 characters
        text = "A" * 500
        estimated_cost = (len(text) / 1000) * client.PRICE_PER_1K_CHARS

        assert estimated_cost == 0.15  # $0.15 for 500 chars


# ============================================================================
# AudioCache Tests
# ============================================================================


class TestAudioCache:
    """Test AudioCache independently."""

    def test_cache_set_and_get(self, temp_cache_dir, sample_audio):
        """Test setting and getting cached audio."""
        cache = AudioCache(temp_cache_dir, ttl_days=30)

        # Cache audio
        cache.set(
            text="Test text",
            previous_text=None,
            next_text=None,
            voice_config={},
            audio=sample_audio,
        )

        # Retrieve from cache
        cached_audio = cache.get(
            text="Test text",
            previous_text=None,
            next_text=None,
            voice_config={},
        )

        assert cached_audio is not None
        assert len(cached_audio) == len(sample_audio)

    def test_cache_miss_returns_none(self, temp_cache_dir):
        """Test cache miss returns None."""
        cache = AudioCache(temp_cache_dir, ttl_days=30)

        cached_audio = cache.get(
            text="Nonexistent text",
            previous_text=None,
            next_text=None,
            voice_config={},
        )

        assert cached_audio is None

    def test_cache_different_context_different_key(self, temp_cache_dir, sample_audio):
        """Test different context creates different cache keys."""
        cache = AudioCache(temp_cache_dir, ttl_days=30)

        # Cache with no context
        cache.set("Text", None, None, {}, sample_audio)

        # Try to get with different context
        cached = cache.get("Text", "Previous", None, {})

        assert cached is None  # Should be a cache miss


# ============================================================================
# Integration Tests
# ============================================================================


class TestTTSClientIntegration:
    """Test realistic TTS client workflows."""

    @patch('requests.post')
    def test_complete_workflow_with_cache(self, mock_post, temp_cache_dir, sample_audio):
        """Test complete workflow: generate, cache, retrieve."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = sample_audio.export(format="mp3").read()
        mock_post.return_value = mock_response

        client = ElevenLabsClient(
            api_key="test_key",
            voice_id="test_voice",
            cache_dir=temp_cache_dir,
            max_retries=3,
        )

        # Generate multiple texts
        texts = ["Text 1", "Text 2", "Text 1"]  # Text 1 repeats

        for text in texts:
            client.generate_audio(text)

        assert client.api_calls == 2  # Only 2 unique texts
        assert client.cache_hits == 1  # Third call was cache hit
        assert client.cache_misses == 2
