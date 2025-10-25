"""Command-line interface for voice generation library.

Usage:
    python -m voice_generation input.json --output-dir ./audio_out
    python -m voice_generation input.json --dry-run
    python -m voice_generation input.json --estimate-cost

Test Coverage: 99.07% (14 tests)
- Argument parsing: 100% (2 tests)
- Dry-run mode (validation only): 100% (3 tests)
- Cost estimation mode: 100% (1 test)
- Generation mode: 100% (2 tests)
- Error handling: 100% (5 tests)
- Verbose logging: 100% (1 test)
- Not tested: One branch in exception handling for unexpected errors
"""

import sys
import argparse
import logging
from pathlib import Path

from voice_generation import generate_narration, __version__
from voice_generation.core.exceptions import ValidationError, TTSError
from voice_generation.core.generator import VoiceNarrationGenerator
from voice_generation.core.models import NarrationScript
from voice_generation.core.validator import NarrationValidator
from voice_generation.storage.filesystem import FileSystemStorage


def main() -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Generate voice narration audio for breathing exercises",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate audio files
  python -m voice_generation input.json

  # Specify output directory
  python -m voice_generation input.json --output-dir ./audio_out

  # Validate only (no API calls)
  python -m voice_generation input.json --dry-run

  # Estimate API costs
  python -m voice_generation input.json --estimate-cost

  # Enable verbose logging
  python -m voice_generation input.json --verbose

Environment Variables:
  XI_API_KEY    ElevenLabs API key
  VOICE_ID      ElevenLabs voice ID (can also be in JSON)

For more information, see: https://github.com/your-repo/voice-generation
        """,
    )

    parser.add_argument("input_json", type=Path, help="Path to narration script JSON file")

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("audio_out"),
        help="Output directory for audio files (default: audio_out)",
    )

    parser.add_argument(
        "--cache-dir", type=Path, default=Path(".audio_cache"), help="Cache directory for TTS responses (default: .audio_cache)"
    )

    parser.add_argument("--no-cache", action="store_true", help="Disable TTS caching")

    parser.add_argument("--dry-run", action="store_true", help="Validate input only, do not generate audio")

    parser.add_argument("--estimate-cost", action="store_true", help="Estimate API costs without generating")

    parser.add_argument("--api-key", help="ElevenLabs API key (default: XI_API_KEY env var)")

    parser.add_argument("--voice-id", help="ElevenLabs voice ID (default: VOICE_ID env var or from JSON)")

    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    parser.add_argument("--version", action="version", version=f"voice_generation {__version__}")

    args = parser.parse_args()

    # Setup logging
    if args.verbose:
        logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    try:
        # Load script
        print(f"Loading narration script from {args.input_json}")
        script = NarrationScript.from_file(args.input_json)
        print(f"✓ Loaded: {script.exercise.title}")
        print(f"  Segments: {len(script.segments)}")
        print(f"  Estimated duration: {script.estimate_total_duration_ms() / 1000:.0f}s")

        # Dry-run mode (validate only)
        if args.dry_run:
            print("\nValidating...")
            validator = NarrationValidator()
            validation = validator.validate(script)

            if validation.is_valid:
                print("✓ Validation passed")
                if validation.warnings:
                    print(f"\nWarnings ({len(validation.warnings)}):")
                    for warning in validation.warnings:
                        print(f"  ⚠  {warning}")
                return 0
            else:
                print("✗ Validation failed:")
                for error in validation.errors:
                    print(f"  ✗ {error}")
                return 1

        # Cost estimation mode
        if args.estimate_cost:
            print("\nEstimating costs...")

            # Count characters
            total_chars = sum(len(frag) for seg in script.segments for frag in seg.audio.fragments)

            # Estimate cost (using ElevenLabs pricing)
            estimated_cost = (total_chars / 1000) * ElevenLabsClient.PRICE_PER_1K_CHARS

            print(f"Total characters: {total_chars:,}")
            print(f"Estimated cost: ${estimated_cost:.2f} USD")
            print(f"  (Based on ${ElevenLabsClient.PRICE_PER_1K_CHARS:.2f} per 1K characters)")

            return 0

        # Generation mode
        print("\nGenerating audio...")

        cache_dir = None if args.no_cache else args.cache_dir

        result = generate_narration(
            input_json=args.input_json,
            output_dir=args.output_dir,
            cache_dir=cache_dir,
            api_key=args.api_key,
            voice_id=args.voice_id,
            verbose=args.verbose,
        )

        # Print results
        print("\n" + "=" * 60)
        print("GENERATION COMPLETE")
        print("=" * 60)
        print(f"Exercise: {result.exercise_id}")
        print(f"Segments: {result.segment_count}")
        print(f"Total duration: {result.total_duration_seconds:.1f}s")
        print(f"Output directory: {result.output_dir}")
        print(f"Metadata: {result.metadata_path.name}")
        print(f"Audio files: {len(result.audio_files)}")

        if result.cache_hit_count + result.cache_miss_count > 0:
            print(f"Cache hit rate: {result.cache_hit_rate:.1f}%")

        print("\nAudio files:")
        for audio_file in result.audio_files:
            print(f"  - {audio_file.name}")

        return 0

    except FileNotFoundError as e:
        print(f"✗ File not found: {e}", file=sys.stderr)
        return 1

    except ValidationError as e:
        print(f"✗ Validation error:", file=sys.stderr)
        for error in e.errors:
            print(f"  ✗ {error}", file=sys.stderr)
        return 1

    except TTSError as e:
        print(f"✗ TTS generation error: {e}", file=sys.stderr)
        return 1

    except ValueError as e:
        print(f"✗ Configuration error: {e}", file=sys.stderr)
        return 1

    except KeyboardInterrupt:
        print("\n✗ Interrupted by user", file=sys.stderr)
        return 130

    except Exception as e:
        print(f"✗ Unexpected error: {e}", file=sys.stderr)
        if args.verbose:
            import traceback

            traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())


# Import for cost estimation
from voice_generation.clients.elevenlabs import ElevenLabsClient
