# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Python-based voice generation system for creating narration audio for breathing exercises using ElevenLabs Text-to-Speech API. The system processes JSON metadata files ("narration scripts") that define breathing exercise structures, generates professional narration audio with VST effects, and outputs metadata for mobile app integration.

### Core Workflow

```
Narration Script (JSON)
  → ElevenLabs TTS
  → VST Audio Processing (8-stage chain)
  → Audio Stitching + Breath Cycles
  → Production-Ready Audio + Metadata
```

## Environment Setup

### Conda Environment

**IMPORTANT**: This project uses conda for environment management, not pip-only.

```bash
# Create environment from existing conda exports
# (Note: environment.yml not in repo, but can be recreated from exports)
conda create -n voice_generation python=3.11.9
conda activate voice_generation

# Install core dependencies
conda install -c conda-forge ffmpeg=4.2.2 pydub=0.25.1

# Install pip dependencies
pip install requests openai elevenlabs pedalboard python-dotenv
```

**Required System Dependencies**:
- **ffmpeg**: Audio processing (included via conda)
- **VST3 Plugins** (optional): `/Library/Audio/Plug-Ins/VST3/`
  - FabFilter Pro-Q 3, Pro-L 2
  - iZotope RX 11 De-ess, Nectar 4, Ozone 11
  - Oeksound Soothe2
  - Sonnox Oxford Inflator

### Environment Variables

Create `.env` file in `voice_generation/` directory:

```bash
XI_API_KEY=your_elevenlabs_api_key
VOICE_ID=your_elevenlabs_voice_id
OPENAI_API_KEY=your_openai_api_key
```

**Security Note**: `finedtuned.py:5-7` contains hardcoded API keys - DO NOT commit changes to this file.

## Common Commands

### Generate Voice Narration

```bash
# Run narration generator with metadata file
python -m voice_generation.narration_generator

# NOTE: Update metadata file path in narration_generator.py:23 before running:
# metadata_file = "voice_generation/narration_scripts/your_file.json"
```

**What It Does**:
1. Loads narration script JSON from `narration_scripts/`
2. Generates audio via ElevenLabs TTS with context support
3. Applies 8-stage VST effects chain (if plugins available)
4. Trims/pads audio to exact segment lengths
5. Stitches sections with breath-aligned silences
6. Outputs to `audio_out/<exercise_name>/`
7. Generates `<exercise_name>_metadata.json` with breath cycles

### Audio Processing Utilities

```bash
# Trim silence from audio files
python -m voice_generation.trim_audio input_dir output_dir --silence_threshold -50.0 --chunk_size 10

# Edit airscript metadata (GUI editor)
python -m voice_generation.airscript_editor
```

### Fine-Tuning Data Generation

```bash
# Generate stratified sampling plan (200 examples)
python voice_generation/finetuning/scripts/generate_narration_training_data.py

# Validate narration scripts
python -c 'from voice_generation.finetuning.scripts.generate_narration_training_data import validate_example; validate_example(0)'

# Validate all examples
python -c 'from voice_generation.finetuning.scripts.generate_narration_training_data import validate_all'

# Generate airscript training data
python voice_generation/finetuning/scripts/generate_airscript_training_data.py

# Validate airscripts with Go tests
python -c 'from voice_generation.finetuning.scripts.generate_airscript_training_data import run_go_tests'
```

## Architecture

### Core Components

**1. AudioGenerator** (`narration_generator.py:35-250`)
Main voice generation pipeline orchestrator.

Key Methods:
- `process_metadata()` - Main loop processing sections/paragraphs
- `generate_and_process_audio()` - TTS generation with context (`previous_text`, `next_text`)
- `shorten_text()` - GPT-4 text reduction when audio exceeds `segment_length`
- `apply_effects_chain()` - 8-stage VST plugin processing
- `create_breath_cycle()` - Creates breath cycle objects for mobile app

**2. Audio Processing** (`trim_audio.py`, `trim_audio_utils.py`)
Audio manipulation utilities.

Functions:
- `round_down_to_previous_second()` - Precise timing control
- `round_up_to_next_second()` - Ceiling rounding
- `pad_to_nearest_second()` - Silence padding
- `trim_silence()` - Intelligent silence detection and removal

**3. Airscript Editor** (`airscript_editor.py:19-200`)
CustomTkinter GUI for batch editing production airscript JSON files.

Features:
- Batch edit: `title`, `card_description`, `presentation.top_tip`, `airscript_tag`
- Export to Excel or save to JSON
- Hardcoded file paths (`airscript_editor.py:26-42`) - update before use

### Narration Script Structure

Narration scripts are simplified JSON inputs for voice generation (subset of full airscript).

**Minimal Example**:
```json
{
  "exercise_title": "Calm Breathing",
  "card_description": "A calming breathing exercise...",
  "sections": {
    "introduction": {
      "paragraphs": [
        {
          "voice_script": ["Welcome to this breathing exercise."],
          "segment_length": 8000
        }
      ]
    },
    "practice": {
      "breathe_in": 4000,
      "breathe_out": 6000,
      "repeat": 10,
      "paragraphs": [
        {
          "voice_script": ["Breathe in slowly.", "Exhale gently."],
          "segment_length": 90000
        }
      ]
    }
  }
}
```

**Key Fields**:
- `breathe_in/breathe_out` - Breathing durations (milliseconds)
- `repeat` - Number of breath cycle repetitions
- `voice_script` - Array of narration sentences
- `segment_length` - Max audio duration (typically 85% of total cycle time)
- `hold_after_inhale/hold_after_exhale` - Optional breath holds

**Examples**: 23 narration scripts in `narration_scripts/` directory

### Voice Generation Pipeline

```
For each section → For each paragraph:
  1. Generate audio via ElevenLabs TTS
     - Pass previous_text and next_text for better prosody
  2. Trim silence and pad to nearest second
  3. If audio > segment_length:
     - Shorten text with GPT-4
     - Regenerate audio
  4. Apply VST effects chain (8 plugins)
  5. Export to WAV

Stitch sections:
  - Voice plays during inhale
  - Silence during exhale
  - Create breath_cycle objects

Output:
  - audio_out/<exercise_name>/*.wav
  - <exercise_name>_metadata.json
```

### 8-Stage VST Processing Chain

When `apply_effect_chain=True` in AudioGenerator:

1. Nectar 4 Auto-Level (normalization)
2. FabFilter Pro-Q 3 (EQ)
3. RX 11 De-ess (sibilance reduction)
4. Soothe2 (resonance control)
5. Nectar 4 (vocal processing)
6. FabFilter Pro-L 2 (limiting)
7. Oxford Inflator (saturation/warmth)
8. Ozone 11 (mastering)

Loaded via `pedalboard.load_plugin()` and applied via `Pedalboard()` chain.

**Fallback**: If plugins unavailable, system uses unprocessed audio.

### Fine-Tuning System

Two-model distillation pipeline for automated breathing exercise generation.

**Model₁**: User Intent → Narration Script (voice guide generator)
**Model₂**: (Intent + Narration) → Complete Airscript (executable exercise)

**Training Data Generation**:
- 200 examples per model
- Stratified sampling: 8 categories × 6 patterns × 3 durations × 3 difficulties
- Validation: JSON schema + 7 style rules + timing estimation
- Production validation: Go tests + official airscript schema

**Key Validation Rules** (narration scripts):
1. Second-person address (you/your, NEVER we/our/us)
2. Present tense imperative + invitation
3. Permission-based language (allow, let, notice)
4. Sensory-focused & embodied
5. Minimal sentences (5-15 words)
6. Non-judgmental acceptance
7. Breath-aligned pacing

**Category-Specific WPM** (timing estimation):
- Deep Relief: 65 WPM (slow, soothing)
- Energy: 100 WPM (fast, activating)
- Sleep: 55 WPM (very slow, hypnotic)
- Resilience/Flow: 75 WPM (patient, steady)
- Quick Fix: 80 WPM (efficient, direct)

**See**: `finetuning/README.md` for complete documentation

## Key Design Patterns

### 1. Metadata-Driven Architecture
Everything defined in JSON. Mobile apps are universal players executing "airscripts" like sheet music.

### 2. Adaptive Length Control
If generated audio exceeds `segment_length`, GPT-4 shortens text and regenerates audio automatically (`narration_generator.py:150-180`).

### 3. Context-Aware TTS
ElevenLabs receives `previous_text` and `next_text` parameters for natural prosody and emotional continuity (`narration_generator.py:120-145`).

### 4. Breath-Aligned Stitching
Voice plays during inhale phase, silence during exhale phase. Creates natural pacing that matches breathing rhythm.

### 5. Hardcoded Configuration
Multiple files have hardcoded paths/settings:
- `narration_generator.py:23` - metadata file path
- `airscript_editor.py:26-42` - production airscript paths
- `finedtuned.py:5-7` - API keys (NEVER commit changes)

**Always update these before running scripts.**

## Output Structure

```
audio_out/
  <exercise_name>/
    <exercise_name>_<section_key>_<paragraph_index>.wav     # Individual paragraphs
    <exercise_name>_<section_key>_stitched.wav              # Section-level stitched
    <exercise_name>_metadata.json                           # Exercise metadata + breath cycles
```

**Metadata JSON includes**:
- Exercise title and structure
- Section-level breath cycle definitions
- Audio file paths and durations
- Text modifications (if shortened by GPT-4)

## Integration with Production

Voice generation creates **partial airscripts** (breath_cycles + audio). Production airscripts require additional configuration:

**Missing from voice generation output**:
- Audio channels: 9 independent layers (voices, background, soundscapes, breathing guides)
- Biofeedback modulation: Real-time audio adjustment based on heart rate/coherence/calmness
- Feedback triggers: Conditional actions based on user metrics
- UI configuration: Vitals display, graphs, presentation settings
- Haptic patterns: Vibration feedback

**Production Example**: See `oxa_airscripts/airscripts/production/airscript/*.json` for complete airscripts.

## Troubleshooting

### Issue: FFmpeg not found
**Cause**: FFmpeg not in PATH
**Fix**: Ensure conda environment activated (`conda activate voice_generation`) or install via conda (`conda install -c conda-forge ffmpeg`)

### Issue: VST plugins not loading
**Cause**: Plugins missing from `/Library/Audio/Plug-Ins/VST3/`
**Fix**: System falls back to unprocessed audio (this is expected behavior). No action required unless professional audio processing needed.

### Issue: ElevenLabs API rate limit exceeded
**Cause**: Too many requests in short period
**Fix**: System should auto-retry. If persistent, check API key quota at elevenlabs.io

### Issue: Audio exceeds segment_length repeatedly
**Cause**: Text too long for target duration, GPT-4 shortening insufficient
**Fix**:
1. Manually reduce `voice_script` text in narration script JSON
2. Increase `segment_length` to accommodate longer audio
3. Check category WPM in `generate_narration_training_data.py:22-31`

### Issue: Generated audio sounds unnatural
**Cause**: Lack of context for TTS prosody
**Fix**: Ensure `previous_text` and `next_text` are provided in `generate_and_process_audio()` calls. This is automatic in current implementation.

## Development Notes

- Use `rg` instead of `grep`, `fd` instead of `find`, `jq` for JSON processing
- Metadata file path must be updated in `narration_generator.py:23` before each run
- All audio trimmed/padded to whole seconds for precise timing control
- ElevenLabs context support (`previous_text`, `next_text`) improves prosody continuity
- Fine-tuning system uses Claude Sonnet 4.5 or GPT-4o for training data generation
- Production airscripts validated with Go test suite (`oxa_airscripts/airscripts/go test ./...`)
