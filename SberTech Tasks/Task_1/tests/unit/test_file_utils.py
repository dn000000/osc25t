"""
Unit tests for file utilities module.
"""

import pytest
import tempfile
from pathlib import Path
import os

from src.file_utils import safe_write, TempFileManager


class TestSafeWrite:
    """Tests for safe_write context manager"""

    def test_safe_write_creates_file(self):
        """Test that safe_write creates a file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"

            with safe_write(file_path, mode="w") as f:
                f.write("test content")

            assert file_path.exists()
            assert file_path.read_text() == "test content"

    def test_safe_write_atomic_mode(self):
        """Test safe_write with atomic mode"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"

            with safe_write(file_path, mode="w", atomic=True) as f:
                f.write("atomic content")

            assert file_path.exists()
            assert file_path.read_text() == "atomic content"

    def test_safe_write_binary_mode(self):
        """Test safe_write with binary mode"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.bin"

            with safe_write(file_path, mode="wb") as f:
                f.write(b"binary content")

            assert file_path.exists()
            assert file_path.read_bytes() == b"binary content"

    def test_safe_write_creates_parent_dirs(self):
        """Test that safe_write creates parent directories"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "subdir" / "nested" / "test.txt"

            # Create parent directories first
            file_path.parent.mkdir(parents=True, exist_ok=True)

            with safe_write(file_path, mode="w") as f:
                f.write("nested content")

            assert file_path.exists()
            assert file_path.read_text() == "nested content"

    def test_safe_write_with_encoding(self):
        """Test safe_write with specific encoding"""
        with tempfile.TemporaryDirectory() as tmpdir:
            file_path = Path(tmpdir) / "test.txt"

            with safe_write(file_path, mode="w", encoding="utf-8") as f:
                f.write("test with encoding")

            assert file_path.exists()


class TestTempFileManager:
    """Tests for TempFileManager"""

    def test_temp_file_manager_creates_temp_file(self):
        """Test that TempFileManager creates a temporary file"""
        manager = TempFileManager()
        tmp_path = manager.create_temp_file()

        assert tmp_path.exists()
        tmp_path.write_text("temp content")
        assert tmp_path.read_text() == "temp content"

        # Cleanup
        manager.cleanup()
        assert not tmp_path.exists()

    def test_temp_file_manager_cleans_up(self):
        """Test that TempFileManager cleans up temporary file"""
        manager = TempFileManager()
        temp_file = manager.create_temp_file()
        temp_file.write_text("temp content")

        # Cleanup
        manager.cleanup()

        # File should be deleted after cleanup
        assert not temp_file.exists()

    def test_temp_file_manager_with_suffix(self):
        """Test TempFileManager with custom suffix"""
        manager = TempFileManager()
        tmp_path = manager.create_temp_file(suffix=".json")

        assert tmp_path.suffix == ".json"

        # Cleanup
        manager.cleanup()

    def test_temp_file_manager_with_prefix(self):
        """Test TempFileManager with custom prefix"""
        manager = TempFileManager()
        tmp_path = manager.create_temp_file(prefix="test_")

        assert tmp_path.name.startswith("test_")

        # Cleanup
        manager.cleanup()

    def test_temp_file_manager_with_custom_dir(self):
        """Test TempFileManager with custom directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = TempFileManager()
            tmp_path = manager.create_temp_file(dir=tmpdir)

            assert tmp_path.parent == Path(tmpdir)

            # Cleanup
            manager.cleanup()

    def test_temp_file_manager_exception_still_cleans_up(self):
        """Test that TempFileManager cleans up even on exception"""
        manager = TempFileManager()
        temp_file = None

        try:
            temp_file = manager.create_temp_file()
            temp_file.write_text("temp content")
            raise ValueError("Test exception")
        except ValueError:
            pass
        finally:
            manager.cleanup()

        # File should still be deleted
        assert not temp_file.exists()

    def test_temp_file_manager_create_temp_dir(self):
        """Test that TempFileManager can create temporary directories"""
        manager = TempFileManager()
        tmp_dir = manager.create_temp_dir()

        assert tmp_dir.exists()
        assert tmp_dir.is_dir()

        # Cleanup
        manager.cleanup()
