"""Tests for FileSystemStorage (file I/O operations).

Test Coverage Goals:
- Directory creation
- Audio file writing
- JSON file writing/reading
- File existence checks
- File listing
- Error handling
"""

import json
import pytest
from pathlib import Path

from pydub import AudioSegment

from voice_generation.storage.filesystem import FileSystemStorage
from voice_generation.core.exceptions import StorageError


# ============================================================================
# Directory Management Tests
# ============================================================================


class TestDirectoryManagement:
    """Test directory creation and management."""

    def test_init_creates_base_dir(self, tmp_path):
        """Test initialization creates base directory."""
        base_dir = tmp_path / "test_base"
        storage = FileSystemStorage(base_dir)

        assert storage.base_dir == base_dir
        assert base_dir.exists()
        assert base_dir.is_dir()

    def test_create_exercise_dir(self, temp_storage):
        """Test creating exercise directory."""
        exercise_dir = temp_storage.create_exercise_dir("test-exercise-v1")

        assert exercise_dir.exists()
        assert exercise_dir.is_dir()
        assert exercise_dir.name == "test-exercise-v1"

    def test_create_exercise_dir_idempotent(self, temp_storage):
        """Test creating same exercise directory twice is safe."""
        dir1 = temp_storage.create_exercise_dir("test-v1")
        dir2 = temp_storage.create_exercise_dir("test-v1")

        assert dir1 == dir2
        assert dir1.exists()

    def test_get_exercise_dir(self, temp_storage):
        """Test getting exercise directory path (without creating it)."""
        exercise_dir = temp_storage.get_exercise_dir("nonexistent-v1")

        assert not exercise_dir.exists()  # Should not create it
        assert exercise_dir.name == "nonexistent-v1"


# ============================================================================
# Audio File Writing Tests
# ============================================================================


class TestAudioWriting:
    """Test audio file writing operations."""

    def test_write_audio_wav(self, temp_storage, sample_audio):
        """Test writing audio as WAV file."""
        output_path = temp_storage.base_dir / "test.wav"
        result_path = temp_storage.write_audio(output_path, sample_audio, format="wav")

        assert result_path == output_path
        assert output_path.exists()
        assert output_path.suffix == ".wav"

        # Verify audio can be read back
        loaded_audio = AudioSegment.from_file(output_path)
        assert len(loaded_audio) == len(sample_audio)

    def test_write_audio_creates_parent_dirs(self, temp_storage, sample_audio):
        """Test writing audio creates parent directories if needed."""
        output_path = temp_storage.base_dir / "nested" / "deep" / "audio.wav"
        result_path = temp_storage.write_audio(output_path, sample_audio)

        assert result_path.exists()
        assert result_path.parent.exists()

    def test_write_audio_invalid_path_raises_error(self, temp_storage, sample_audio):
        """Test writing to invalid path raises StorageError."""
        # Try to write to a path with null bytes (invalid on all systems)
        with pytest.raises(StorageError):
            temp_storage.write_audio("/tmp/\x00invalid.wav", sample_audio)


# ============================================================================
# JSON File Writing Tests
# ============================================================================


class TestJSONWriting:
    """Test JSON file writing operations."""

    def test_write_json(self, temp_storage):
        """Test writing JSON data to file."""
        data = {"exercise": "test", "duration": 300, "tags": ["a", "b"]}
        output_path = temp_storage.base_dir / "metadata.json"

        result_path = temp_storage.write_json(output_path, data)

        assert result_path == output_path
        assert output_path.exists()

        # Verify JSON content
        with open(output_path, "r") as f:
            loaded_data = json.load(f)
        assert loaded_data == data

    def test_write_json_creates_parent_dirs(self, temp_storage):
        """Test writing JSON creates parent directories."""
        output_path = temp_storage.base_dir / "nested" / "data.json"
        temp_storage.write_json(output_path, {"test": "data"})

        assert output_path.exists()
        assert output_path.parent.exists()

    def test_write_json_non_serializable_raises_error(self, temp_storage):
        """Test writing non-JSON-serializable data raises StorageError."""
        output_path = temp_storage.base_dir / "bad.json"

        # Objects are not JSON-serializable by default
        class NonSerializable:
            pass

        with pytest.raises(StorageError) as exc_info:
            temp_storage.write_json(output_path, {"obj": NonSerializable()})
        # Check error mentions JSON serialization issue
        error_msg = str(exc_info.value).lower()
        assert "json" in error_msg and "serializable" in error_msg


# ============================================================================
# JSON File Reading Tests
# ============================================================================


class TestJSONReading:
    """Test JSON file reading operations."""

    def test_read_json(self, temp_storage):
        """Test reading JSON data from file."""
        data = {"exercise": "test", "segments": [1, 2, 3]}
        json_path = temp_storage.base_dir / "test.json"

        # Write first
        temp_storage.write_json(json_path, data)

        # Read back
        loaded_data = temp_storage.read_json(json_path)
        assert loaded_data == data

    def test_read_json_file_not_found(self, temp_storage):
        """Test reading non-existent JSON file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            temp_storage.read_json("nonexistent.json")

    def test_read_json_invalid_json_raises_error(self, temp_storage):
        """Test reading malformed JSON raises StorageError."""
        json_path = temp_storage.base_dir / "invalid.json"

        # Write invalid JSON
        with open(json_path, "w") as f:
            f.write("{broken json syntax}")

        with pytest.raises(StorageError) as exc_info:
            temp_storage.read_json(json_path)
        assert "invalid json" in str(exc_info.value).lower()


# ============================================================================
# File Existence and Listing Tests
# ============================================================================


class TestFileOperations:
    """Test file existence and listing operations."""

    def test_exists_returns_true_for_existing_file(self, temp_storage):
        """Test exists() returns True for existing file."""
        file_path = temp_storage.base_dir / "test.txt"
        file_path.write_text("test")

        assert temp_storage.exists(file_path)

    def test_exists_returns_false_for_nonexistent_file(self, temp_storage):
        """Test exists() returns False for nonexistent file."""
        assert not temp_storage.exists("nonexistent.txt")

    def test_list_files(self, temp_storage):
        """Test listing files in directory."""
        # Create some test files
        (temp_storage.base_dir / "file1.txt").write_text("test1")
        (temp_storage.base_dir / "file2.txt").write_text("test2")
        (temp_storage.base_dir / "file3.json").write_text("{}")

        files = temp_storage.list_files(temp_storage.base_dir)
        assert len(files) == 3
        assert all(f.is_file() for f in files)

    def test_list_files_with_pattern(self, temp_storage):
        """Test listing files with glob pattern."""
        (temp_storage.base_dir / "test1.txt").write_text("1")
        (temp_storage.base_dir / "test2.txt").write_text("2")
        (temp_storage.base_dir / "data.json").write_text("{}")

        txt_files = temp_storage.list_files(temp_storage.base_dir, "*.txt")
        assert len(txt_files) == 2
        assert all(f.suffix == ".txt" for f in txt_files)

    def test_list_files_directory_not_exist_raises_error(self, temp_storage):
        """Test listing files in nonexistent directory raises StorageError."""
        with pytest.raises(StorageError) as exc_info:
            temp_storage.list_files("nonexistent_dir")
        assert "does not exist" in str(exc_info.value).lower()

    def test_list_files_path_is_file_raises_error(self, temp_storage):
        """Test listing files on a file (not directory) raises StorageError."""
        file_path = temp_storage.base_dir / "test.txt"
        file_path.write_text("test")

        with pytest.raises(StorageError) as exc_info:
            temp_storage.list_files(file_path)
        assert "not a directory" in str(exc_info.value).lower()


# ============================================================================
# Exercise Deletion Tests
# ============================================================================


class TestExerciseDeletion:
    """Test exercise directory deletion."""

    def test_delete_exercise(self, temp_storage):
        """Test deleting exercise directory."""
        # Create exercise directory with files
        exercise_dir = temp_storage.create_exercise_dir("test-v1")
        (exercise_dir / "audio.wav").write_text("fake audio")
        (exercise_dir / "metadata.json").write_text("{}")

        # Delete
        temp_storage.delete_exercise("test-v1")

        assert not exercise_dir.exists()

    def test_delete_exercise_nonexistent_is_safe(self, temp_storage):
        """Test deleting nonexistent exercise is safe (no error)."""
        # Should not raise error
        temp_storage.delete_exercise("nonexistent-v1")


# ============================================================================
# Integration Tests
# ============================================================================


class TestStorageIntegration:
    """Test realistic storage workflows."""

    def test_complete_workflow(self, temp_storage, sample_audio):
        """Test complete workflow: create dir, write files, read back."""
        # Create exercise directory
        exercise_dir = temp_storage.create_exercise_dir("complete-test-v1")

        # Write audio file
        audio_path = exercise_dir / "segment_0.wav"
        temp_storage.write_audio(audio_path, sample_audio)

        # Write metadata
        metadata = {
            "exercise_id": "complete-test-v1",
            "segment_count": 1,
            "total_duration_ms": len(sample_audio),
        }
        metadata_path = exercise_dir / "metadata.json"
        temp_storage.write_json(metadata_path, metadata)

        # Verify everything exists
        assert exercise_dir.exists()
        assert audio_path.exists()
        assert metadata_path.exists()

        # Read back and verify
        loaded_metadata = temp_storage.read_json(metadata_path)
        assert loaded_metadata == metadata

        # List files
        files = temp_storage.list_files(exercise_dir)
        assert len(files) == 2

        # Cleanup
        temp_storage.delete_exercise("complete-test-v1")
        assert not exercise_dir.exists()
