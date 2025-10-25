"""Result classes for voice generation operations.

Test Coverage: 95.56% (integrated with validator and generator tests)
- ValidationResult: 100% (validator tests)
- SegmentResult: 100% (generator tests)
- GenerationResult: 95.56% (generator and integration tests)
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class ValidationResult:
    """Result of narration script validation."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def __str__(self) -> str:
        if self.is_valid:
            msg = "✓ Validation passed"
            if self.warnings:
                msg += f" ({len(self.warnings)} warning(s))"
            return msg
        else:
            return f"✗ Validation failed with {len(self.errors)} error(s)"


@dataclass
class CostEstimate:
    """Estimated API costs for generation."""

    total_characters: int
    estimated_usd: float
    currency: str = "USD"
    breakdown: Optional[dict] = None

    def __str__(self) -> str:
        return f"Estimated cost: ${self.estimated_usd:.2f} {self.currency} ({self.total_characters:,} characters)"


@dataclass
class SegmentResult:
    """Result of processing a single segment."""

    segment_id: str
    segment_index: int
    audio_path: Path
    duration_ms: int
    fragment_count: int
    was_shortened: bool = False
    original_text: Optional[str] = None
    shortened_text: Optional[str] = None


@dataclass
class GenerationResult:
    """Result of complete narration generation."""

    exercise_id: str
    output_dir: Path
    segment_count: int
    total_duration_ms: int
    metadata_path: Path
    audio_files: List[Path] = field(default_factory=list)
    cache_hit_count: int = 0
    cache_miss_count: int = 0

    @property
    def total_duration_seconds(self) -> float:
        """Total duration in seconds."""
        return self.total_duration_ms / 1000.0

    @property
    def cache_hit_rate(self) -> float:
        """Cache hit rate percentage."""
        total = self.cache_hit_count + self.cache_miss_count
        if total == 0:
            return 0.0
        return (self.cache_hit_count / total) * 100.0

    def __str__(self) -> str:
        lines = [
            f"✓ Generated {self.segment_count} segments",
            f"  Total duration: {self.total_duration_seconds:.1f}s",
            f"  Output directory: {self.output_dir}",
            f"  Metadata: {self.metadata_path.name}",
            f"  Audio files: {len(self.audio_files)}",
        ]
        if self.cache_hit_count + self.cache_miss_count > 0:
            lines.append(f"  Cache hit rate: {self.cache_hit_rate:.1f}%")
        return "\n".join(lines)
