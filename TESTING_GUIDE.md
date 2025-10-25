# Testing Guide

This guide provides instructions for testing the voice generation library both manually and with automated tests.

## Prerequisites

### 1. Install Dependencies

```bash
# Activate conda environment (if using conda)
conda activate voice_generation

# Install development dependencies
pip install pytest pytest-cov pytest-mock black ruff mypy types-requests

# Install core dependencies (if not already installed)
pip install pydantic requests pydub python-dotenv
```

### 2. Set Up Credentials

Create a `.env` file in the `voice_generation/` directory:

```bash
XI_API_KEY=your_elevenlabs_api_key_here
VOICE_ID=your_voice_id_here
```

Or export as environment variables:

```bash
export XI_API_KEY="your_key"
export VOICE_ID="your_voice_id"
```

### 3. Verify FFmpeg

```bash
ffmpeg -version
# Should show FFmpeg version info
```

## Automated Tests

### Run All Tests

```bash
cd voice_generation/

# Run all tests with coverage
pytest tests/ -v --cov=voice_generation --cov-report=term-missing

# Expected output:
# ✓ test_audio_processor.py: 15+ passing tests
# ✓ test_models.py: 10+ passing tests (when created)
# ✓ Coverage: 85%+
```

### Run Specific Test Modules

```bash
# Audio processor tests (pure functions, no API calls)
pytest tests/test_audio_processor.py -v

# Model validation tests
pytest tests/test_models.py -v  # Create this file

# Storage tests
pytest tests/test_storage.py -v  # Create this file
```

### Test Coverage Report

```bash
# Generate HTML coverage report
pytest tests/ --cov=voice_generation --cov-report=html

# Open in browser
open htmlcov/index.html
```

## Manual Testing (No API Calls)

### Test 1: JSON Schema Validation

```bash
# Validate example script (no API calls)
python -m voice_generation examples/calm_breathing.json --dry-run
```

**Expected Output**:
```
Loading narration script from examples/calm_breathing.json
✓ Loaded: Calm Breathing
  Segments: 5
  Estimated duration: 300s

Validating...
✓ Validation passed
```

**If errors occur**: Check JSON schema matches documentation

### Test 2: Cost Estimation

```bash
# Estimate API costs (no API calls)
python -m voice_generation examples/calm_breathing.json --estimate-cost
```

**Expected Output**:
```
Loading narration script from examples/calm_breathing.json
✓ Loaded: Calm Breathing
  Segments: 5
  Estimated duration: 300s

Estimating costs...
Total characters: 450
Estimated cost: $0.14 USD
  (Based on $0.30 per 1K characters)
```

### Test 3: Python Import

```python
# Test imports work
python3 << 'EOF'
from voice_generation import (
    generate_narration,
    VoiceNarrationGenerator,
    NarrationScript,
    ElevenLabsClient,
    FileSystemStorage
)

print("✓ All imports successful")

# Test model loading
script = NarrationScript.from_file("examples/calm_breathing.json")
print(f"✓ Loaded script: {script.exercise.title}")
print(f"  Segments: {len(script.segments)}")
print(f"  Duration: {script.estimate_total_duration_ms() / 1000:.0f}s")
EOF
```

**Expected Output**:
```
✓ All imports successful
✓ Loaded script: Calm Breathing
  Segments: 5
  Duration: 300s
```

## Manual Testing (With API Calls)

⚠️ **Warning**: These tests will make real API calls and incur costs (~$0.14 for the example script).

### Test 4: End-to-End Generation (Simple API)

```bash
# Generate audio (will call ElevenLabs API)
python -m voice_generation examples/calm_breathing.json --output-dir test_output --verbose
```

**Expected Output**:
```
Loading narration script from examples/calm_breathing.json
✓ Loaded: Calm Breathing
  Segments: 5
  Estimated duration: 300s

Generating audio...
[INFO] Starting generation for 'calm-breathing-v1'
[INFO] Processing segment 1/5: 'intro'
[INFO] Calling ElevenLabs API for text (83 chars): Welcome to this calm breathing exercise...
[INFO]   ✓ Generated 18000ms audio (4 fragments)
[INFO] Processing segment 2/5: 'practice'
...

============================================================
GENERATION COMPLETE
============================================================
Exercise: calm-breathing-v1
Segments: 5
Total duration: 300.0s
Output directory: test_output/calm-breathing-v1
Metadata: calm-breathing-v1_metadata.json
Audio files: 5
Cache hit rate: 0.0%

Audio files:
  - intro_0.wav
  - practice_1.wav
  - deepening_2.wav
  - natural_breathing_3.wav
  - closing_4.wav
```

**Verify Output**:
```bash
ls -lh test_output/calm-breathing-v1/

# Expected files:
# -rw-r--r-- intro_0.wav
# -rw-r--r-- practice_1.wav
# -rw-r--r-- deepening_2.wav
# -rw-r--r-- natural_breathing_3.wav
# -rw-r--r-- closing_4.wav
# -rw-r--r-- calm-breathing-v1_metadata.json
```

**Play Audio** (macOS):
```bash
afplay test_output/calm-breathing-v1/intro_0.wav
```

**Check Metadata**:
```bash
python3 -m json.tool test_output/calm-breathing-v1/calm-breathing-v1_metadata.json | head -50
```

### Test 5: Caching Test

```bash
# First run (all cache misses)
python -m voice_generation examples/calm_breathing.json --output-dir test_cache_1 --verbose

# Second run (should have cache hits)
python -m voice_generation examples/calm_breathing.json --output-dir test_cache_2 --verbose
```

**Expected**: Second run should show cache hits:
```
[INFO] Cache HIT (5 hits, 0 misses): Welcome to this calm breathing exercise...
...
Cache hit rate: 100.0%
```

### Test 6: Python Library API

```python
python3 << 'EOF'
from voice_generation import generate_narration

# Generate using simple API
result = generate_narration(
    "examples/calm_breathing.json",
    output_dir="test_library_api",
    cache_dir=".test_cache",
    verbose=True
)

print(f"\n✓ Generation complete:")
print(f"  Exercise: {result.exercise_id}")
print(f"  Segments: {result.segment_count}")
print(f"  Duration: {result.total_duration_seconds:.1f}s")
print(f"  Files: {len(result.audio_files)}")
print(f"  Cache hit rate: {result.cache_hit_rate:.1f}%")
EOF
```

### Test 7: Error Handling

```bash
# Test missing API key
unset XI_API_KEY
python -m voice_generation examples/calm_breathing.json 2>&1 | grep "Configuration error"
# Expected: ✗ Configuration error: ElevenLabs API key required

# Test invalid JSON
echo '{"invalid": "json"}' > /tmp/invalid.json
python -m voice_generation /tmp/invalid.json --dry-run 2>&1 | grep "Validation error"
# Expected: Validation errors listed

# Test file not found
python -m voice_generation nonexistent.json 2>&1 | grep "File not found"
# Expected: ✗ File not found: nonexistent.json
```

## Code Quality Checks

### Linting

```bash
# Format code
black voice_generation/ --check
# Expected: All done! ✨ 🍰 ✨

# Lint code
ruff check voice_generation/
# Expected: All checks passed!
```

### Type Checking

```bash
# Type check with mypy
mypy voice_generation/
# Expected: Success: no issues found
```

## Performance Testing

### Cache Performance

```bash
# Measure cache impact
time python -m voice_generation examples/calm_breathing.json --output-dir perf_test_1 --no-cache
# Record time (e.g., 45 seconds)

time python -m voice_generation examples/calm_breathing.json --output-dir perf_test_2 --cache-dir .perf_cache
# Record time (first run, similar to above)

time python -m voice_generation examples/calm_breathing.json --output-dir perf_test_3 --cache-dir .perf_cache
# Record time (second run, should be much faster - ~5 seconds)
```

### Memory Usage

```bash
# Monitor memory during generation
/usr/bin/time -l python -m voice_generation examples/calm_breathing.json --output-dir mem_test 2>&1 | grep "maximum resident set size"
# Expected: < 200MB
```

## Integration Testing Checklist

- [ ] JSON validation catches invalid schemas
- [ ] Cost estimation matches actual costs (±10%)
- [ ] Audio files are generated correctly
- [ ] Metadata JSON is valid and complete
- [ ] Caching reduces API calls (100% hit rate on re-run)
- [ ] Verbose logging provides useful information
- [ ] Error messages are clear and actionable
- [ ] CLI help text is displayed (`python -m voice_generation --help`)
- [ ] Python imports work without errors
- [ ] Audio quality is acceptable (listen to samples)

## Troubleshooting

### Import Errors

```bash
# Check if package is importable
python3 -c "import voice_generation; print(voice_generation.__version__)"
# Expected: 2.0.0
```

### FFmpeg Issues

```bash
# Check FFmpeg
which ffmpeg
ffmpeg -version

# If missing, install via conda
conda install -c conda-forge ffmpeg
```

### Pydantic Validation Errors

```bash
# Validate JSON schema
python3 << 'EOF'
from voice_generation import NarrationScript

try:
    script = NarrationScript.from_file("examples/calm_breathing.json")
    print("✓ JSON schema valid")
except Exception as e:
    print(f"✗ Validation error: {e}")
EOF
```

### API Connectivity

```bash
# Test ElevenLabs API directly
curl -X GET "https://api.elevenlabs.io/v1/voices" \
  -H "xi-api-key: $XI_API_KEY" | python3 -m json.tool | head -20
# Expected: JSON response with voices list
```

## Test Data Cleanup

```bash
# Remove test outputs
rm -rf test_output test_cache_* test_library_api perf_test_* mem_test .test_cache .perf_cache

# Verify cleanup
ls | grep test
# Expected: No output (all test directories removed)
```

## Continuous Integration (Future)

For CI/CD pipelines (GitHub Actions, GitLab CI, etc.):

```yaml
# .github/workflows/test.yml (example)
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          sudo apt-get install -y ffmpeg
          pip install -r requirements-dev.txt

      - name: Run tests
        run: pytest tests/ -v --cov=voice_generation --cov-fail-under=85

      - name: Lint
        run: ruff check voice_generation/

      - name: Type check
        run: mypy voice_generation/
```

## Success Criteria

✅ All automated tests pass
✅ Manual validation works (--dry-run)
✅ Cost estimation is accurate
✅ Audio generation produces valid WAV files
✅ Metadata JSON is well-formed
✅ Caching reduces duplicate API calls
✅ Error messages are helpful
✅ Code passes linters (black, ruff)
✅ Type checking passes (mypy)
✅ Test coverage ≥ 85%

## Next Steps

After all tests pass:

1. Create more example narration scripts
2. Add unit tests for untested components
3. Set up CI/CD pipeline
4. Deploy to production environment
5. Monitor API costs and performance metrics
