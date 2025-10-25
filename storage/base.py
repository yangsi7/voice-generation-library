"""Abstract storage interface."""

import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Union, Any

from pydub import AudioSegment


class Storage(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def create_exercise_dir(self, exercise_id: str) -> Path:
        """
        Create directory for exercise outputs.

        Args:
            exercise_id: Unique exercise identifier

        Returns:
            Path to created directory

        Raises:
            StorageError: If directory creation fails
        """
        pass

    @abstractmethod
    def write_audio(self, path: Union[str, Path], audio: AudioSegment, format: str = "wav") -> Path:
        """
        Write audio segment to file.

        Args:
            path: Output file path
            audio: Audio segment to write
            format: Audio format (default: "wav")

        Returns:
            Path to written file

        Raises:
            StorageError: If write operation fails
        """
        pass

    @abstractmethod
    def write_json(self, path: Union[str, Path], data: Any) -> Path:
        """
        Write JSON data to file.

        Args:
            path: Output file path
            data: Data to serialize (must be JSON-serializable)

        Returns:
            Path to written file

        Raises:
            StorageError: If write operation fails
        """
        pass

    @abstractmethod
    def read_json(self, path: Union[str, Path]) -> Any:
        """
        Read JSON data from file.

        Args:
            path: Input file path

        Returns:
            Deserialized JSON data

        Raises:
            StorageError: If read operation fails
            FileNotFoundError: If file doesn't exist
        """
        pass

    @abstractmethod
    def exists(self, path: Union[str, Path]) -> bool:
        """
        Check if file or directory exists.

        Args:
            path: Path to check

        Returns:
            True if exists, False otherwise
        """
        pass

    @abstractmethod
    def list_files(self, directory: Union[str, Path], pattern: str = "*") -> list[Path]:
        """
        List files in directory matching pattern.

        Args:
            directory: Directory to search
            pattern: Glob pattern (default: "*" = all files)

        Returns:
            List of matching file paths

        Raises:
            StorageError: If listing fails
        """
        pass
