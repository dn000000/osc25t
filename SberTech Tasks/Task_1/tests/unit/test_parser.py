"""
Unit tests for RPM parser module.
"""

import struct
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest

from src.parser import RPMParser, RPMParsingError, PackageMetadata, Dependency


def create_minimal_rpm_file(
    path: Path,
    name: str = "test-package",
    version: str = "1.0.0",
    release: str = "1",
    arch: str = "x86_64",
    is_source: bool = False,
) -> None:
    """
    Create a minimal valid RPM file for testing.

    Args:
        path: Path where to create the RPM file
        name: Package name
        version: Package version
        release: Package release
        arch: Package architecture
        is_source: Whether this is a source RPM
    """
    with open(path, "wb") as f:
        # Write RPM lead (96 bytes)
        lead = bytearray(96)
        lead[0:4] = b"\xed\xab\xee\xdb"  # Magic number
        lead[4:6] = struct.pack(">H", 3)  # Major version
        lead[6:8] = struct.pack(">H", 0)  # Minor version
        lead[8:10] = struct.pack(">H", 0 if not is_source else 1)  # Type (0=binary, 1=source)
        f.write(lead)

        # Write signature header (minimal)
        sig_header = _create_minimal_header({})
        f.write(sig_header)

        # Align to 8-byte boundary
        pos = f.tell()
        alignment = (8 - (pos % 8)) % 8
        if alignment:
            f.write(b"\x00" * alignment)

        # Write main header with metadata
        tags = {
            1000: ("string", name),  # NAME
            1001: ("string", version),  # VERSION
            1002: ("string", release),  # RELEASE
            1022: ("string", arch if not is_source else "src"),  # ARCH
        }

        if not is_source:
            tags[1044] = ("string", f"{name}-{version}-{release}.src.rpm")  # SOURCERPM

        main_header = _create_minimal_header(tags)
        f.write(main_header)


def _create_minimal_header(tags: dict) -> bytes:
    """
    Create a minimal RPM header structure.

    Args:
        tags: Dictionary of tag_id -> (type, value) pairs

    Returns:
        Bytes representing the header
    """
    # Header magic
    header = bytearray()
    header.extend(b"\x8e\xad\xe8\x01")  # Header magic
    header.extend(b"\x00\x00\x00\x00")  # Reserved

    # Build data store and index
    index_entries = []
    data_store = bytearray()

    for tag_id, (data_type, value) in tags.items():
        offset = len(data_store)

        if data_type == "string":
            # String type (6)
            value_bytes = value.encode("utf-8") + b"\x00"
            data_store.extend(value_bytes)

            # Create index entry: tag, type, offset, count
            index_entry = struct.pack(">IIII", tag_id, 6, offset, 1)
            index_entries.append(index_entry)

    # Write index count and data size
    index_count = len(index_entries)
    data_size = len(data_store)
    header.extend(struct.pack(">I", index_count))
    header.extend(struct.pack(">I", data_size))

    # Write index entries
    for entry in index_entries:
        header.extend(entry)

    # Write data store
    header.extend(data_store)

    return bytes(header)


class TestRPMParser:
    """Tests for RPMParser class"""

    @pytest.fixture
    def parser(self):
        """Create an RPMParser instance"""
        return RPMParser()

    @pytest.fixture
    def temp_rpm_dir(self):
        """Create a temporary directory for RPM files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    def test_parser_initialization(self, parser):
        """Test that parser initializes correctly"""
        assert parser is not None
        assert isinstance(parser.use_rpm_library, bool)

    def test_parse_nonexistent_file_raises_error(self, parser):
        """Test that parsing nonexistent file raises error"""
        nonexistent = Path("/nonexistent/file.rpm")

        with pytest.raises(RPMParsingError, match="Invalid RPM file"):
            parser.parse_rpm_header(nonexistent)

    def test_parse_invalid_rpm_raises_error(self, parser, temp_rpm_dir):
        """Test that parsing invalid RPM file raises error"""
        invalid_rpm = temp_rpm_dir / "invalid.rpm"
        with open(invalid_rpm, "wb") as f:
            f.write(b"This is not an RPM file")

        with pytest.raises(RPMParsingError):
            parser.parse_rpm_header(invalid_rpm)

    def test_parse_binary_rpm_metadata(self, parser, temp_rpm_dir):
        """Test parsing metadata from binary RPM"""
        rpm_path = temp_rpm_dir / "test-package.rpm"
        create_minimal_rpm_file(
            rpm_path,
            name="test-package",
            version="1.0.0",
            release="1",
            arch="x86_64",
            is_source=False,
        )

        metadata = parser.parse_rpm_header(rpm_path)

        assert metadata.name == "test-package"
        assert metadata.version == "1.0.0"
        assert metadata.release == "1"
        assert metadata.arch == "x86_64"
        assert metadata.is_source is False

    def test_parse_source_rpm_metadata(self, parser, temp_rpm_dir):
        """Test parsing metadata from source RPM"""
        rpm_path = temp_rpm_dir / "test-package.src.rpm"
        create_minimal_rpm_file(
            rpm_path, name="test-package", version="2.0.0", release="2", arch="src", is_source=True
        )

        metadata = parser.parse_rpm_header(rpm_path)

        assert metadata.name == "test-package"
        assert metadata.version == "2.0.0"
        assert metadata.release == "2"
        assert metadata.arch == "src"
        assert metadata.is_source is True

    def test_extract_dependencies_from_nonexistent_file(self, parser):
        """Test that extracting dependencies from nonexistent file raises error"""
        nonexistent = Path("/nonexistent/file.rpm")

        with pytest.raises(RPMParsingError, match="Invalid RPM file"):
            parser.extract_dependencies(nonexistent)

    def test_parse_with_rpm_library_mock(self, temp_rpm_dir):
        """Test parsing with mocked rpm library"""
        # Create parser
        parser = RPMParser()

        # Mock the rpm module import
        with patch.dict("sys.modules", {"rpm": MagicMock()}):
            import sys

            mock_rpm = sys.modules["rpm"]

            # Setup mock transaction set
            mock_ts = MagicMock()
            mock_rpm.TransactionSet.return_value = mock_ts
            mock_rpm._RPMVSF_NOSIGNATURES = 0

            # Setup mock header
            mock_header = {
                mock_rpm.RPMTAG_NAME: b"test-pkg",
                mock_rpm.RPMTAG_VERSION: b"1.0",
                mock_rpm.RPMTAG_RELEASE: b"1",
                mock_rpm.RPMTAG_ARCH: b"x86_64",
                mock_rpm.RPMTAG_SOURCERPM: b"test-pkg-1.0-1.src.rpm",
            }
            mock_ts.hdrFromFdno.return_value = mock_header

            # Create a dummy RPM file
            rpm_path = temp_rpm_dir / "test.rpm"
            rpm_path.write_bytes(b"dummy")

            # Parse
            metadata = parser._parse_with_rpm_library(rpm_path)

            assert metadata.name == "test-pkg"
            assert metadata.version == "1.0"
            assert metadata.release == "1"
            assert metadata.arch == "x86_64"

    def test_extract_dependencies_with_rpm_library_mock(self, temp_rpm_dir):
        """Test dependency extraction with mocked rpm library"""
        parser = RPMParser()

        with patch.dict("sys.modules", {"rpm": MagicMock()}):
            import sys

            mock_rpm = sys.modules["rpm"]

            # Setup mock transaction set
            mock_ts = MagicMock()
            mock_rpm.TransactionSet.return_value = mock_ts
            mock_rpm._RPMVSF_NOSIGNATURES = 0

            # Setup mock header with dependencies
            mock_header = MagicMock()
            mock_header.get.side_effect = lambda tag, default=[]: {
                mock_rpm.RPMTAG_REQUIRENAME: [b"libc.so.6", b"python3"],
                mock_rpm.RPMTAG_REQUIREFLAGS: [0, 8],
                mock_rpm.RPMTAG_REQUIREVERSION: [b"", b"3.8"],
                mock_rpm.RPMTAG_PROVIDENAME: [b"test-pkg"],
                mock_rpm.RPMTAG_PROVIDEFLAGS: [8],
                mock_rpm.RPMTAG_PROVIDEVERSION: [b"1.0"],
                mock_rpm.RPMTAG_SOURCERPM: b"test-pkg-1.0-1.src.rpm",
            }.get(tag, default)

            mock_header.__getitem__ = (
                lambda self, key: b"x86_64" if key == mock_rpm.RPMTAG_ARCH else None
            )
            mock_ts.hdrFromFdno.return_value = mock_header

            # Create a dummy RPM file
            rpm_path = temp_rpm_dir / "test.rpm"
            rpm_path.write_bytes(b"dummy")

            # Extract dependencies
            deps = parser._extract_deps_with_rpm_library(rpm_path)

            # Should have requires and provides
            assert len(deps) > 0

            requires_deps = [d for d in deps if d.type == "requires"]
            provides_deps = [d for d in deps if d.type == "provides"]

            assert len(requires_deps) >= 2
            assert len(provides_deps) >= 1

    def test_get_header_string_missing_tag(self, parser):
        """Test getting string from header with missing tag"""
        header_data = {}
        result = parser._get_header_string(header_data, 1000)
        assert result is None

    def test_get_header_string_array_missing_tag(self, parser):
        """Test getting string array from header with missing tag"""
        header_data = {}
        result = parser._get_header_string_array(header_data, 1000)
        assert result == []

    def test_get_header_int_array_missing_tag(self, parser):
        """Test getting int array from header with missing tag"""
        header_data = {}
        result = parser._get_header_int_array(header_data, 1000)
        assert result == []

    def test_corrupted_rpm_file_handling(self, parser, temp_rpm_dir):
        """Test handling of corrupted RPM file"""
        corrupted_rpm = temp_rpm_dir / "corrupted.rpm"

        # Create file with valid magic but truncated content
        with open(corrupted_rpm, "wb") as f:
            f.write(b"\xed\xab\xee\xdb")  # Valid magic
            f.write(b"\x00" * 50)  # Truncated lead

        with pytest.raises(RPMParsingError):
            parser.parse_rpm_header(corrupted_rpm)
