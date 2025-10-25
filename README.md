# Voice Generation Library

Professional Python library for generating voice narration audio for breathing exercises using ElevenLabs TTS API.

## Features

✅ **Dual-Mode Interface**: Use as CLI tool or Python library
✅ **Clean Architecture**: Modular, testable, extensible design
✅ **Cost-Optimized**: Aggressive caching with configurable TTL
✅ **Robust Error Handling**: Retry logic, detailed error messages
✅ **Type-Safe**: Pydantic models with comprehensive validation
✅ **Production-Ready**: Structured logging, statistics tracking

## Installation

### Prerequisites

- Python 3.11+
- FFmpeg (for audio processing)
- ElevenLabs API key

### Install Dependencies

```bash
# Using conda (recommended for audio processing)
conda create -n voice_generation python=3.11.9
conda activate voice_generation
conda install -c conda-forge ffmpeg pydub

# Install Python dependencies
pip install -r requirements-dev.txt
```

### Environment Variables

Create a `.env` file or export environment variables:

```bash
export XI_API_KEY="your_elevenlabs_api_key"
export VOICE_ID="your_voice_id"  # Optional, can be in JSON
```

## Quick Start

### CLI Usage

```bash
# Basic usage
python -m voice_generation examples/calm_breathing.json

# Custom output directory
python -m voice_generation examples/calm_breathing.json --output-dir ./my_audio

# Validate only (no API calls)
python -m voice_generation examples/calm_breathing.json --dry-run

# Estimate costs
python -m voice_generation examples/calm_breathing.json --estimate-cost

# Verbose logging
python -m voice_generation examples/calm_breathing.json --verbose
```

### Library Usage (Simple)

```python
from voice_generation import generate_narration

# Minimal usage (uses environment variables for credentials)
result = generate_narration("calm_breathing.json")

print(f"Generated {result.segment_count} segments")
print(f"Total duration: {result.total_duration_seconds:.1f}s")
print(f"Output directory: {result.output_dir}")
```

### Library Usage (Advanced)

```python
from voice_generation import (
    VoiceNarrationGenerator,
    NarrationScript,
    ElevenLabsClient,
    FileSystemStorage
)
import os

# Load and validate script
script = NarrationScript.from_file("calm_breathing.json")

# Configure TTS client
tts_client = ElevenLabsClient(
    api_key=os.getenv("XI_API_KEY"),
    voice_id=os.getenv("VOICE_ID"),
    cache_dir=".cache",  # Enable caching
    cache_ttl_days=30
)

# Configure storage
storage = FileSystemStorage("audio_out")

# Create generator
generator = VoiceNarrationGenerator(
    tts_client=tts_client,
    storage=storage,
    verbose=True
)

# Validate before generating
validation = generator.validate(script)
if not validation.is_valid:
    for error in validation.errors:
        print(f"Error: {error}")
    exit(1)

# Estimate cost
cost = generator.estimate_cost(script)
print(f"Estimated cost: ${cost.estimated_usd:.2f}")

# Generate
result = generator.generate(script)

# Access results
for audio_file in result.audio_files:
    print(f"Generated: {audio_file}")
```

## JSON Schema

Narration scripts follow a simplified, hierarchical schema:

```json
{
  "exercise": {
    "id": "calm-breathing-v1",
    "title": "Calm Breathing",
    "description": "...",
    "category": "stress-relief",
    "tags": ["beginner", "relaxation"],
    "duration_seconds": 300
  },

  "segments": [
    {
      "id": "intro",
      "type": "narration",
      "audio": {
        "fragments": [
          "Welcome to this breathing exercise.",
          "Find a comfortable position."
        ],
        "max_duration_ms": 15000
      }
    },
    {
      "id": "practice",
      "type": "breathing_cycle",
      "breathing": {
        "inhale_ms": 4000,
        "exhale_ms": 6000,
        "repetitions": 10
      },
      "audio": {
        "fragments": [
          "Breathe in slowly.",
          "Exhale gently."
        ],
        "max_duration_ms": 8500,
        "timing": "inhale_phase"
      }
    }
  ],

  "voice_config": {
    "provider": "elevenlabs",
    "voice_id": "your_voice_id",  # Optional if in env var
    "model": "eleven_multilingual_v2",
    "stability": 0.7,
    "similarity_boost": 0.75
  }
}
```

### Key Schema Features

**Flat segment array**: Easy iteration and reordering
**Explicit segment types**: `narration` vs `breathing_cycle`
**Breathing pattern presets**: `box`, `calm`, `4-7-8`, `natural`
**Clear naming**: `max_duration_ms` (upper bound) vs ambiguous `segment_length`
**Timing control**: Specify when audio plays (`inhale_phase`, `exhale_phase`, `full_cycle`)

See `examples/calm_breathing.json` for a complete example.

## Output Structure

```
audio_out/
  calm-breathing-v1/
    intro_0.wav
    practice_1.wav
    deepening_2.wav
    natural_breathing_3.wav
    closing_4.wav
    calm-breathing-v1_metadata.json
```

### Metadata JSON

```json
{
  "exercise_title": "Calm Breathing",
  "exercise_id": "calm-breathing-v1",
  "segments": {
    "intro": [
      {
        "segment_index": 0,
        "fragment_count": 4,
        "duration_ms": 18000,
        "audio_file": "intro_0.wav"
      }
    ]
  },
  "breath_cycles": [
    {
      "breathe_in": 4000,
      "breathe_out": 6000,
      "repetitions": 10,
      "voices": [
        {
          "key": "program_panic/calm-breathing-v1/practice_1.wav",
          "sound_level": 75
        }
      ],
      "audio_breathing_guides": [...]
    }
  ]
}
```

## Architecture

### Layered Pipeline

```
┌─────────────────────────────────────────┐
│  CLI / API                              │
│  - Argument parsing                     │
│  - Simple convenience wrappers          │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  Validation Layer                       │
│  - Pydantic schema validation           │
│  - Business rules validation            │
└─────────────────────────────────────────┘
                  ↓
┌─────────────────────────────────────────┐
│  Orchestrator (VoiceNarrationGenerator) │
│  - Workflow coordination                │
│  - Error aggregation                    │
└─────────────────────────────────────────┘
                  ↓
┌──────────────┬──────────────┬───────────┐
│  TTS Client  │  Audio       │  Metadata │
│  - ElevenLabs│  - Trim/pad  │  - Breath │
│  - Caching   │  - Stitch    │    cycles │
│  - Retry     │  - Duration  │  - JSON   │
└──────────────┴──────────────┴───────────┘
                  ↓
┌─────────────────────────────────────────┐
│  Storage Layer                          │
│  - FileSystemStorage (local files)      │
│  - Extensible (cloud storage possible)  │
└─────────────────────────────────────────┘
```

### Key Components

**Models** (`core/models.py`): Pydantic data models with validation
**Generator** (`core/generator.py`): Main orchestrator
**TTS Client** (`clients/elevenlabs.py`): ElevenLabs integration with caching
**Audio Processor** (`processors/audio.py`): Pure audio manipulation functions
**Metadata Builder** (`processors/metadata.py`): Breath cycle generation
**Storage** (`storage/filesystem.py`): File I/O abstraction
**Validator** (`core/validator.py`): Business rule validation

### Design Principles

1. **Dependency Injection**: Easy to mock and test
2. **Pure Functions**: Audio processing is side-effect-free
3. **Abstract Interfaces**: Swap TTS providers or storage backends
4. **Progressive Disclosure**: Simple API for common cases, advanced API for customization
5. **Validation-First**: Fail fast with clear error messages

## Testing

### Run Tests

```bash
# Install test dependencies
pip install pytest pytest-cov pytest-mock

# Run all tests with coverage
pytest tests/ --cov=voice_generation --cov-report=term-missing

# Run specific test file
pytest tests/test_audio_processor.py -v

# Run with verbose logging
pytest tests/ -v --log-cli-level=INFO
```

### Test Structure

```
tests/
  test_audio_processor.py   # Pure function tests
  test_models.py            # Pydantic validation tests
  test_storage.py           # Storage I/O tests
  test_generator.py         # Integration tests (mocked TTS)
  test_cli.py               # CLI interface tests
  fixtures/                 # Test data
```

## Linting & Type Checking

```bash
# Format code
black voice_generation/

# Lint code
ruff check voice_generation/

# Type check
mypy voice_generation/
```

## Cost Optimization

The library uses aggressive caching to minimize API costs:

- **File-based cache**: Keyed by text + context + voice config
- **TTL support**: Configurable expiration (default: 30 days)
- **Statistics tracking**: Monitor cache hit rate

```python
# Enable caching (default)
result = generate_narration("input.json", cache_dir=".cache")

# Disable caching
result = generate_narration("input.json", cache_dir=None)

# Custom cache TTL
tts_client = ElevenLabsClient(..., cache_ttl_days=7)
```

## Error Handling

The library provides detailed, actionable error messages:

```python
from voice_generation import generate_narration, ValidationError, TTSError

try:
    result = generate_narration("input.json")
except ValidationError as e:
    for error in e.errors:
        print(f"Validation error: {error}")
except TTSError as e:
    print(f"TTS API error: {e}")
    print(f"Status code: {e.status_code}")
```

### Common Errors

**Missing API key**: Set `XI_API_KEY` environment variable
**Missing voice ID**: Set in JSON or `VOICE_ID` environment variable
**Audio exceeds max_duration**: Enable `allow_shortening` or increase `max_duration_ms`
**FFmpeg not found**: Install via `conda install -c conda-forge ffmpeg`

## Migration from v1.x

**Old schema** (sections → paragraphs → voice_script):
```json
{
  "exercise_title": "...",
  "sections": {
    "intro": {
      "paragraphs": [
        {
          "voice_script": ["Text 1", "Text 2"],
          "segment_length": 8000
        }
      ]
    }
  }
}
```

**New schema** (flat segments array):
```json
{
  "exercise": {
    "id": "...",
    "title": "..."
  },
  "segments": [
    {
      "id": "intro",
      "type": "narration",
      "audio": {
        "fragments": ["Text 1", "Text 2"],
        "max_duration_ms": 8000
      }
    }
  ],
  "voice_config": {...}
}
```

**Key Changes**:
- `exercise_title` → `exercise.title`
- `sections` → `segments` (flat array)
- `voice_script` → `audio.fragments`
- `segment_length` → `max_duration_ms`
- Added `exercise.id` (required)
- Added `segment.type` (narration/breathing_cycle)
- Separated `voice_config` from exercise metadata

## Troubleshooting

### FFmpeg not found
```bash
conda install -c conda-forge ffmpeg
```

### Pydantic validation errors
Check your JSON matches the schema. Use `--dry-run` to validate:
```bash
python -m voice_generation input.json --dry-run
```

### Cache not working
Ensure cache directory is writable:
```bash
mkdir -p .audio_cache
chmod 755 .audio_cache
```

### High API costs
- Enable caching (`cache_dir=".cache"`)
- Validate scripts before generating (`--dry-run`)
- Estimate costs first (`--estimate-cost`)

## Contributing

This library follows best practices for Python projects:

- **PEP 8** code style (enforced by `black` and `ruff`)
- **Type hints** on all public APIs (checked by `mypy`)
- **Comprehensive docstrings** (Google style)
- **85%+ test coverage** (checked by `pytest-cov`)
- **Clean architecture** (SOLID principles)

## License

MIT License - see LICENSE file for details.

## Support

- **Documentation**: See `docs/` directory
- **Examples**: See `examples/` directory
- **Issues**: https://github.com/your-repo/voice-generation/issues
- **ElevenLabs API**: https://elevenlabs.io/docs

## Changelog

### v2.0.0 (2025-01-25)

**Major Refactoring**:
- ✅ Dual-mode architecture (CLI + Library)
- ✅ Simplified JSON schema
- ✅ Pydantic validation
- ✅ Aggressive caching
- ✅ Clean separation of concerns
- ✅ Comprehensive error handling
- ✅ 85%+ test coverage
- ✅ Type-safe APIs

**Breaking Changes**:
- New JSON schema (see Migration guide)
- Removed VST audio processing
- Removed fine-tuning code (separate project)
- CLI interface redesigned

**Removed**:
- `parse_xml_preset.py` (duplicate)
- `airscript_editor.py` (separate tool)
- `finetuning/` (separate project)

## Development

### Running Tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test group
python -m pytest tests/test_models.py -v
python -m pytest tests/test_integration.py -v

# Run tests with coverage
python -m pytest tests/ --cov=. --cov-report=html
open htmlcov/index.html  # View coverage report

# Run specific test
python -m pytest tests/test_models.py::TestExerciseModel::test_valid_exercise -v
```

### Test Coverage

✅ **187 tests** | ✅ **92.4% library coverage** | ✅ **100% pass rate**

| Module | Coverage | Tests |
|--------|----------|-------|
| api.py | 100.00% | 12 |
| __main__.py | 99.07% | 14 |
| processors/metadata.py | 99.17% | 17 |
| core/generator.py | 97.03% | 23 |
| core/validator.py | 96.12% | 18 |
| core/models.py | 90.43% | 36 |
| storage/filesystem.py | 88.76% | 22 |
| clients/elevenlabs.py | 85.09% | 19 |
| processors/audio.py | 77.78% | 17 |

See [TEST_COVERAGE_SUMMARY.md](TEST_COVERAGE_SUMMARY.md) for detailed coverage report.

### Code Quality

```bash
# Format code
black voice_generation/

# Lint code
ruff check voice_generation/

# Type check
mypy voice_generation/
```
