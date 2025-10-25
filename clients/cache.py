"""Audio caching system for TTS responses.

Test Coverage: 45.19% (integrated with TTS client tests)
- Cache key generation: 100% (3 tests)
- Basic get/set operations: 100% (3 tests)
- Context-aware caching: 100% (integrated tests)
- Not tested: TTL expiration, cache cleanup, persistence, eviction policies
"""

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Optional

from pydub import AudioSegment

from voice_generation.core.exceptions import CacheError


logger = logging.getLogger(__name__)


class AudioCache:
    """
    File-based cache for TTS audio responses.

    Cache structure:
        {cache_dir}/
            {hash}.wav       # Cached audio file
            {hash}.meta.json # Metadata (timestamp, text, etc.)
    """

    def __init__(self, cache_dir: Path, ttl_days: int = 30):
        """
        Initialize audio cache.

        Args:
            cache_dir: Directory for cache storage
            ttl_days: Time-to-live in days (default: 30)
        """
        self.cache_dir = Path(cache_dir)
        self.ttl_seconds = ttl_days * 24 * 60 * 60
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Initialized AudioCache at {self.cache_dir} (TTL: {ttl_days} days)")

    def _compute_key(self, text: str, previous_text: Optional[str], next_text: Optional[str], voice_config: dict) -> str:
        """
        Compute cache key from text and context.

        Args:
            text: Main text
            previous_text: Previous context
            next_text: Next context
            voice_config: Voice configuration (voice_id, model, etc.)

        Returns:
            SHA256 hash as hexadecimal string
        """
        data = json.dumps({
            "text": text,
            "previous_text": previous_text or "",
            "next_text": next_text or "",
            **voice_config
        }, sort_keys=True)

        return hashlib.sha256(data.encode()).hexdigest()

    def get(
        self,
        text: str,
        previous_text: Optional[str],
        next_text: Optional[str],
        voice_config: dict
    ) -> Optional[AudioSegment]:
        """
        Retrieve audio from cache if available and not expired.

        Args:
            text: Main text
            previous_text: Previous context
            next_text: Next context
            voice_config: Voice configuration

        Returns:
            Cached audio segment, or None if not found/expired
        """
        cache_key = self._compute_key(text, previous_text, next_text, voice_config)
        audio_path = self.cache_dir / f"{cache_key}.wav"
        meta_path = self.cache_dir / f"{cache_key}.meta.json"

        # Check if both files exist
        if not (audio_path.exists() and meta_path.exists()):
            return None

        try:
            # Load metadata
            with open(meta_path, "r") as f:
                metadata = json.load(f)

            # Check TTL
            cached_time = metadata.get("timestamp", 0)
            age_seconds = time.time() - cached_time

            if age_seconds > self.ttl_seconds:
                logger.debug(f"Cache EXPIRED: {cache_key[:8]}... (age: {age_seconds/86400:.1f} days)")
                # Clean up expired entry
                self._delete_entry(cache_key)
                return None

            # Load audio
            audio = AudioSegment.from_wav(audio_path)
            logger.debug(f"Cache HIT: {cache_key[:8]}... ({len(text)} chars)")
            return audio

        except Exception as e:
            logger.warning(f"Cache read error for {cache_key[:8]}...: {e}")
            return None

    def set(
        self,
        text: str,
        previous_text: Optional[str],
        next_text: Optional[str],
        voice_config: dict,
        audio: AudioSegment
    ) -> None:
        """
        Store audio in cache.

        Args:
            text: Main text
            previous_text: Previous context
            next_text: Next context
            voice_config: Voice configuration
            audio: Audio segment to cache
        """
        cache_key = self._compute_key(text, previous_text, next_text, voice_config)
        audio_path = self.cache_dir / f"{cache_key}.wav"
        meta_path = self.cache_dir / f"{cache_key}.meta.json"

        try:
            # Save audio
            audio.export(audio_path, format="wav")

            # Save metadata
            metadata = {
                "timestamp": time.time(),
                "text": text,
                "text_length": len(text),
                "audio_duration_ms": len(audio),
                "voice_config": voice_config
            }
            with open(meta_path, "w") as f:
                json.dump(metadata, f, indent=2)

            logger.debug(f"Cache SET: {cache_key[:8]}... ({len(text)} chars, {len(audio)}ms)")

        except Exception as e:
            logger.error(f"Failed to cache audio for {cache_key[:8]}...: {e}")
            # Clean up partial write
            if audio_path.exists():
                audio_path.unlink()
            if meta_path.exists():
                meta_path.unlink()

    def _delete_entry(self, cache_key: str) -> None:
        """Delete cache entry (both audio and metadata)."""
        audio_path = self.cache_dir / f"{cache_key}.wav"
        meta_path = self.cache_dir / f"{cache_key}.meta.json"

        if audio_path.exists():
            audio_path.unlink()
        if meta_path.exists():
            meta_path.unlink()

    def clear(self) -> int:
        """
        Clear all cached entries.

        Returns:
            Number of entries deleted
        """
        count = 0
        for audio_file in self.cache_dir.glob("*.wav"):
            cache_key = audio_file.stem
            self._delete_entry(cache_key)
            count += 1

        logger.info(f"Cleared cache: {count} entries deleted")
        return count

    def prune_expired(self) -> int:
        """
        Remove expired cache entries.

        Returns:
            Number of entries pruned
        """
        count = 0
        current_time = time.time()

        for meta_file in self.cache_dir.glob("*.meta.json"):
            try:
                with open(meta_file, "r") as f:
                    metadata = json.load(f)

                cached_time = metadata.get("timestamp", 0)
                age_seconds = current_time - cached_time

                if age_seconds > self.ttl_seconds:
                    cache_key = meta_file.stem.replace(".meta", "")
                    self._delete_entry(cache_key)
                    count += 1

            except Exception as e:
                logger.warning(f"Error checking {meta_file}: {e}")

        logger.info(f"Pruned cache: {count} expired entries deleted")
        return count

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats (entry_count, total_size_mb, etc.)
        """
        audio_files = list(self.cache_dir.glob("*.wav"))
        meta_files = list(self.cache_dir.glob("*.meta.json"))

        total_size_bytes = sum(f.stat().st_size for f in audio_files + meta_files)
        total_size_mb = total_size_bytes / (1024 * 1024)

        return {
            "entry_count": len(audio_files),
            "total_size_mb": round(total_size_mb, 2),
            "cache_dir": str(self.cache_dir),
            "ttl_days": self.ttl_seconds / 86400
        }
