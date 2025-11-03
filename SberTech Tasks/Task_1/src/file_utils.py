"""
Safe file operation utilities.

This module provides utilities for safe file operations including
temporary file management, atomic writes, and proper cleanup.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional, Union
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class TempFileManager:
    """
    Manager for temporary files with automatic cleanup.

    Tracks temporary files and ensures they are cleaned up even if
    exceptions occur during processing.
    """

    def __init__(self):
        """Initialize the temporary file manager."""
        self.temp_files = []
        self.temp_dirs = []

    def create_temp_file(
        self,
        suffix: str = "",
        prefix: str = "rpm_",
        dir: Optional[str] = None,
        delete: bool = False,
    ) -> Path:
        """
        Create a temporary file.

        Args:
            suffix: File suffix (e.g., '.xml')
            prefix: File prefix
            dir: Directory to create file in (default: system temp)
            delete: If True, file is deleted when closed

        Returns:
            Path to temporary file
        """
        try:
            fd, path = tempfile.mkstemp(suffix=suffix, prefix=prefix, dir=dir)
            os.close(fd)  # Close file descriptor

            temp_path = Path(path)
            if not delete:
                self.temp_files.append(temp_path)

            logger.debug(f"Created temporary file: {temp_path}")
            return temp_path

        except Exception as e:
            logger.error(f"Failed to create temporary file: {e}")
            raise

    def create_temp_dir(
        self, suffix: str = "", prefix: str = "rpm_", dir: Optional[str] = None
    ) -> Path:
        """
        Create a temporary directory.

        Args:
            suffix: Directory suffix
            prefix: Directory prefix
            dir: Parent directory (default: system temp)

        Returns:
            Path to temporary directory
        """
        try:
            path = tempfile.mkdtemp(suffix=suffix, prefix=prefix, dir=dir)
            temp_path = Path(path)
            self.temp_dirs.append(temp_path)

            logger.debug(f"Created temporary directory: {temp_path}")
            return temp_path

        except Exception as e:
            logger.error(f"Failed to create temporary directory: {e}")
            raise

    def cleanup(self) -> None:
        """
        Clean up all tracked temporary files and directories.

        This method is safe to call multiple times.
        """
        # Clean up temporary files
        for temp_file in self.temp_files:
            try:
                if temp_file.exists():
                    temp_file.unlink()
                    logger.debug(f"Cleaned up temporary file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {temp_file}: {e}")

        self.temp_files.clear()

        # Clean up temporary directories
        for temp_dir in self.temp_dirs:
            try:
                if temp_dir.exists():
                    # Remove all files in directory first
                    for file_path in temp_dir.rglob("*"):
                        if file_path.is_file():
                            try:
                                file_path.unlink()
                            except Exception as e:
                                logger.warning(f"Failed to remove file {file_path}: {e}")

                    # Remove directory
                    temp_dir.rmdir()
                    logger.debug(f"Cleaned up temporary directory: {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary directory {temp_dir}: {e}")

        self.temp_dirs.clear()

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - ensures cleanup."""
        self.cleanup()
        return False


@contextmanager
def safe_write(
    file_path: Union[str, Path],
    mode: str = "w",
    encoding: Optional[str] = "utf-8",
    atomic: bool = True,
):
    """
    Context manager for safe file writing with atomic operations.

    If atomic=True, writes to a temporary file first and then moves it
    to the target location only if the write succeeds. This prevents
    corruption of existing files if an error occurs during writing.

    Args:
        file_path: Path to file to write
        mode: File mode ('w' for text, 'wb' for binary)
        encoding: Text encoding (only for text mode)
        atomic: If True, use atomic write operation

    Yields:
        File object for writing

    Example:
        with safe_write('output.json') as f:
            json.dump(data, f)
    """
    file_path = Path(file_path)

    if not atomic:
        # Simple non-atomic write
        if "b" in mode:
            with open(file_path, mode) as f:
                yield f
        else:
            with open(file_path, mode, encoding=encoding) as f:
                yield f
        return

    # Atomic write using temporary file
    temp_file = None
    try:
        # Create temporary file in same directory as target
        # This ensures atomic move works (same filesystem)
        temp_fd, temp_path = tempfile.mkstemp(
            dir=file_path.parent, prefix=f".tmp_{file_path.name}_"
        )
        temp_file = Path(temp_path)

        # Close the file descriptor and reopen with proper mode
        os.close(temp_fd)

        # Write to temporary file
        if "b" in mode:
            with open(temp_file, mode) as f:
                yield f
        else:
            with open(temp_file, mode, encoding=encoding) as f:
                yield f

        # If we get here, write was successful - move temp file to target
        # Use replace() for atomic operation on most systems
        temp_file.replace(file_path)
        temp_file = None  # Prevent cleanup since we moved it

        logger.debug(f"Atomically wrote file: {file_path}")

    except Exception as e:
        logger.error(f"Failed to write file {file_path}: {e}")
        raise
    finally:
        # Clean up temporary file if it still exists (error occurred)
        if temp_file and temp_file.exists():
            try:
                temp_file.unlink()
                logger.debug(f"Cleaned up temporary file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to clean up temporary file {temp_file}: {e}")


def safe_read(
    file_path: Union[str, Path],
    mode: str = "r",
    encoding: Optional[str] = "utf-8",
    max_size_mb: Optional[int] = None,
):
    """
    Safely read a file with size limits.

    Args:
        file_path: Path to file to read
        mode: File mode ('r' for text, 'rb' for binary)
        encoding: Text encoding (only for text mode)
        max_size_mb: Maximum file size in MB (None for no limit)

    Returns:
        File contents

    Raises:
        ValueError: If file exceeds size limit
        IOError: If file cannot be read
    """
    file_path = Path(file_path)

    # Check file size if limit specified
    if max_size_mb is not None:
        file_size = file_path.stat().st_size
        max_size_bytes = max_size_mb * 1024 * 1024

        if file_size > max_size_bytes:
            raise ValueError(
                f"File size ({file_size / 1024 / 1024:.1f} MB) exceeds "
                f"maximum allowed size ({max_size_mb} MB)"
            )

    # Read file with context manager
    try:
        if "b" in mode:
            with open(file_path, mode) as f:
                return f.read()
        else:
            with open(file_path, mode, encoding=encoding) as f:
                return f.read()
    except Exception as e:
        logger.error(f"Failed to read file {file_path}: {e}")
        raise


def ensure_directory(dir_path: Union[str, Path], mode: int = 0o755) -> Path:
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        dir_path: Path to directory
        mode: Directory permissions (Unix only)

    Returns:
        Path object for the directory

    Raises:
        OSError: If directory cannot be created
    """
    dir_path = Path(dir_path)

    try:
        dir_path.mkdir(parents=True, exist_ok=True, mode=mode)
        return dir_path
    except Exception as e:
        logger.error(f"Failed to create directory {dir_path}: {e}")
        raise
