# Quick Start Guide

## Installation (5 minutes)

```bash
cd voice_generation/

# Install dependencies
pip install pydantic requests pydub python-dotenv pytest black ruff mypy

# Set credentials
export XI_API_KEY="your_elevenlabs_api_key"
export VOICE_ID="your_voice_id"
```

## Test Without API Calls (30 seconds)

```bash
# Validate JSON schema
python -m voice_generation examples/calm_breathing.json --dry-run

# Estimate costs
python -m voice_generation examples/calm_breathing.json --estimate-cost

# Test Python imports
python3 -c "from voice_generation import generate_narration; print('✓ Works')"
```

## Generate Audio (2 minutes + API time)

```bash
# Generate voice narration
python -m voice_generation examples/calm_breathing.json --output-dir test_output --verbose

# Play result (macOS)
afplay test_output/calm-breathing-v1/intro_0.wav

# Check metadata
python3 -m json.tool test_output/calm-breathing-v1/calm-breathing-v1_metadata.json | head -30
```

## CLI Commands

```bash
# Validate only (no API calls, no cost)
python -m voice_generation INPUT.json --dry-run

# Estimate costs (no API calls)
python -m voice_generation INPUT.json --estimate-cost

# Generate with caching (recommended)
python -m voice_generation INPUT.json --output-dir OUTPUT_DIR --verbose

# Generate without caching
python -m voice_generation INPUT.json --no-cache

# Show help
python -m voice_generation --help
```

## Python API (Simple)

```python
from voice_generation import generate_narration

result = generate_narration("input.json", output_dir="audio_out")

print(f"Generated {result.segment_count} segments")
print(f"Duration: {result.total_duration_seconds:.1f}s")
print(f"Files: {result.audio_files}")
```

## Python API (Advanced)

```python
from voice_generation import (
    VoiceNarrationGenerator,
    NarrationScript,
    ElevenLabsClient,
    FileSystemStorage
)
import os

# Load script
script = NarrationScript.from_file("input.json")

# Setup
tts = ElevenLabsClient(
    api_key=os.getenv("XI_API_KEY"),
    voice_id=os.getenv("VOICE_ID"),
    cache_dir=".cache"
)

generator = VoiceNarrationGenerator(
    tts_client=tts,
    storage=FileSystemStorage("audio_out")
)

# Validate
validation = generator.validate(script)
if not validation.is_valid:
    for error in validation.errors:
        print(f"Error: {error}")
    exit(1)

# Estimate cost
cost = generator.estimate_cost(script)
print(f"Cost: ${cost.estimated_usd:.2f}")

# Generate
result = generator.generate(script)
print(f"Done! {result.segment_count} segments")
```

## JSON Schema Template

```json
{
  "exercise": {
    "id": "my-exercise-v1",
    "title": "My Exercise",
    "category": "stress-relief",
    "tags": ["beginner"]
  },
  "segments": [
    {
      "id": "intro",
      "type": "narration",
      "audio": {
        "fragments": ["Welcome to this exercise."],
        "max_duration_ms": 10000
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
        "fragments": ["Breathe in.", "Breathe out."],
        "max_duration_ms": 8000,
        "timing": "inhale_phase"
      }
    }
  ],
  "voice_config": {
    "provider": "elevenlabs",
    "model": "eleven_multilingual_v2",
    "stability": 0.7
  }
}
```

## Troubleshooting

**Import errors**:
```bash
pip install pydantic requests pydub python-dotenv
```

**FFmpeg not found**:
```bash
conda install -c conda-forge ffmpeg
```

**Missing API key**:
```bash
export XI_API_KEY="your_key"
export VOICE_ID="your_voice_id"
```

**Validation errors**:
```bash
python -m voice_generation INPUT.json --dry-run
# Read error messages and fix JSON
```

## Next Steps

- Read **README.md** for complete documentation
- Read **TESTING_GUIDE.md** for testing instructions
- Check **examples/calm_breathing.json** for schema reference
- Review **IMPLEMENTATION_COMPLETE.md** for architecture details

---

**That's it!** You now have a production-ready TTS library. 🎉
