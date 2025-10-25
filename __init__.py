"""
Voice Generation Library for Breathing Exercise Narration.

This library provides both CLI and programmatic interfaces for generating
professional voice narration audio for breathing exercises using ElevenLabs TTS.

CLI Usage:
    python -m voice_generation input.json --output-dir ./audio_out
    python -m voice_generation input.json --dry-run
    python -m voice_generation input.json --estimate-cost

Library Usage (Simple):
    from voice_generation import generate_narration
    result = generate_narration("input.json", output_dir="audio_out")

Library Usage (Advanced):
    from voice_generation import VoiceNarrationGenerator, NarrationScript
    script = NarrationScript.from_file("input.json")
    generator = VoiceNarrationGenerator(...)
    result = generator.generate(script)
"""

__version__ = "2.0.0"

# Simple API (convenience function)
from voice_generation.api import generate_narration

# Advanced API (direct class access)
from voice_generation.core.generator import VoiceNarrationGenerator
from voice_generation.core.models import NarrationScript, Exercise, Segment
from voice_generation.core.validator import NarrationValidator
from voice_generation.core.exceptions import (
    ValidationError,
    SegmentProcessingError,
    TTSError,
    StorageError,
    CacheError,
)

# Client interfaces
from voice_generation.clients.base import TTSClient
from voice_generation.clients.elevenlabs import ElevenLabsClient

# Storage interfaces
from voice_generation.storage.base import Storage
from voice_generation.storage.filesystem import FileSystemStorage

# Results
from voice_generation.core.results import (
    GenerationResult,
    ValidationResult,
    CostEstimate,
    SegmentResult,
)

__all__ = [
    # Simple API
    "generate_narration",
    # Core
    "VoiceNarrationGenerator",
    "NarrationScript",
    "Exercise",
    "Segment",
    "NarrationValidator",
    # Clients
    "TTSClient",
    "ElevenLabsClient",
    # Storage
    "Storage",
    "FileSystemStorage",
    # Results
    "GenerationResult",
    "ValidationResult",
    "CostEstimate",
    "SegmentResult",
    # Exceptions
    "ValidationError",
    "SegmentProcessingError",
    "TTSError",
    "StorageError",
    "CacheError",
]
