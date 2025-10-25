"""Simple convenience API for common use cases.

Test Coverage: 100.00% (12 tests)
- Successful generation: 100% (4 tests)
- Credential handling: 100% (4 tests)
- Voice config integration: 100% (1 test)
- Error handling: 100% (2 tests)
- Verbose mode: 100% (1 test)
"""

import os
import logging
from pathlib import Path
from typing import Optional, Union

from voice_generation.clients.elevenlabs import ElevenLabsClient
from voice_generation.core.generator import VoiceNarrationGenerator
from voice_generation.core.models import NarrationScript
from voice_generation.core.results import GenerationResult
from voice_generation.storage.filesystem import FileSystemStorage


logger = logging.getLogger(__name__)


def generate_narration(
    input_json: Union[str, Path],
    output_dir: Union[str, Path] = "audio_out",
    cache_dir: Optional[Union[str, Path]] = ".audio_cache",
    api_key: Optional[str] = None,
    voice_id: Optional[str] = None,
    verbose: bool = False,
) -> GenerationResult:
    """
    Generate voice narration audio from a narration script JSON.

    This is the simplest way to use the library. For advanced usage,
    instantiate VoiceNarrationGenerator directly.

    Args:
        input_json: Path to narration script JSON file
        output_dir: Directory to write audio files and metadata (default: "audio_out")
        cache_dir: Directory for TTS caching, or None to disable (default: ".audio_cache")
        api_key: ElevenLabs API key (default: XI_API_KEY env var)
        voice_id: ElevenLabs voice ID (default: from JSON or VOICE_ID env var)
        verbose: Enable verbose logging (default: False)

    Returns:
        GenerationResult with output paths and statistics

    Raises:
        ValidationError: If JSON schema or business rules invalid
        TTSError: If TTS generation fails
        IOError: If file I/O fails
        FileNotFoundError: If input JSON not found
        ValueError: If required credentials missing

    Example:
        >>> from voice_generation import generate_narration
        >>> result = generate_narration("calm_breathing.json")
        >>> print(f"Generated {result.segment_count} segments")
        Generated 3 segments
    """
    # Setup logging
    if verbose:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    # Load script
    logger.info(f"Loading narration script from {input_json}")
    script = NarrationScript.from_file(input_json)

    # Get credentials
    api_key = api_key or os.getenv("XI_API_KEY")
    voice_id = voice_id or script.voice_config.voice_id or os.getenv("VOICE_ID")

    if not api_key:
        raise ValueError(
            "ElevenLabs API key required. Provide via:\n"
            "  - api_key parameter\n"
            "  - XI_API_KEY environment variable"
        )

    if not voice_id:
        raise ValueError(
            "Voice ID required. Provide via:\n"
            "  - voice_id parameter in narration script JSON\n"
            "  - voice_id parameter to this function\n"
            "  - VOICE_ID environment variable"
        )

    # Setup TTS client
    logger.info(f"Initializing ElevenLabs client (voice_id={voice_id[:8]}...)")
    tts_client = ElevenLabsClient(
        api_key=api_key,
        voice_id=voice_id,
        model=script.voice_config.model,
        stability=script.voice_config.stability,
        similarity_boost=script.voice_config.similarity_boost,
        style=script.voice_config.style,
        use_speaker_boost=script.voice_config.use_speaker_boost,
        cache_dir=Path(cache_dir) if cache_dir else None,
    )

    # Setup storage
    storage = FileSystemStorage(output_dir)

    # Setup generator
    generator = VoiceNarrationGenerator(tts_client=tts_client, storage=storage, verbose=verbose)

    # Generate
    logger.info(f"Generating narration for '{script.exercise.title}'")
    result = generator.generate(script)

    logger.info("Generation complete!")
    return result
