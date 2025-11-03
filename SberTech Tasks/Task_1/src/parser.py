"""
RPM package parser module for extracting metadata and dependencies from RPM files.
"""

import logging
import struct
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict, Any

from src.validation import (
    validate_file_path,
    validate_package_name,
    validate_metadata_string,
    validate_file_size,
    ValidationError,
)

logger = logging.getLogger(__name__)


@dataclass
class PackageMetadata:
    """Represents metadata extracted from an RPM package"""

    name: str
    version: str
    release: str
    arch: str
    is_source: bool


@dataclass
class Dependency:
    """Represents a dependency relationship"""

    name: str
    version: Optional[str] = None
    flags: int = 0
    type: str = "requires"  # 'requires', 'buildrequires', 'provides'


class RPMParsingError(Exception):
    """Raised when RPM parsing fails"""

    pass


class RPMParser:
    """Parses RPM package files to extract metadata and dependencies"""

    # RPM header tags
    TAG_NAME = 1000
    TAG_VERSION = 1001
    TAG_RELEASE = 1002
    TAG_ARCH = 1022
    TAG_SOURCERPM = 1044
    TAG_REQUIRENAME = 1049
    TAG_REQUIREFLAGS = 1048
    TAG_REQUIREVERSION = 1050
    TAG_PROVIDENAME = 1047
    TAG_PROVIDEFLAGS = 1112
    TAG_PROVIDEVERSION = 1113
    TAG_BUILDREQUIRES = 1053  # Note: BuildRequires typically in SRPM

    # RPM file magic numbers
    RPM_LEAD_MAGIC = b"\xed\xab\xee\xdb"

    def __init__(self):
        """Initialize the RPM parser"""
        self.use_rpm_library = self._check_rpm_library()

    def _check_rpm_library(self) -> bool:
        """
        Check if rpm Python library is available.

        Returns:
            True if rpm library is available, False otherwise
        """
        try:
            import rpm  # noqa: F401

            return True
        except ImportError:
            logger.warning("rpm library not available, using manual header parsing")
            return False

    def parse_rpm_header(self, rpm_path: Path) -> PackageMetadata:
        """
        Parse RPM file header to extract package metadata.

        Args:
            rpm_path: Path to the RPM file

        Returns:
            PackageMetadata object containing extracted information

        Raises:
            RPMParsingError: If parsing fails
        """
        # Validate file path and size
        try:
            validate_file_path(str(rpm_path), must_exist=True)
            validate_file_size(rpm_path, max_size_mb=500)  # RPM files can be large
        except ValidationError as e:
            raise RPMParsingError(f"Invalid RPM file: {e}")

        if self.use_rpm_library:
            return self._parse_with_rpm_library(rpm_path)
        else:
            return self._parse_manually(rpm_path)

    def _parse_with_rpm_library(self, rpm_path: Path) -> PackageMetadata:
        """
        Parse RPM using the rpm Python library.

        Args:
            rpm_path: Path to the RPM file

        Returns:
            PackageMetadata object

        Raises:
            RPMParsingError: If parsing fails
        """
        try:
            import rpm

            # Open RPM file
            ts = rpm.TransactionSet()
            ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES)  # Skip signature verification

            with open(rpm_path, "rb") as f:
                header = ts.hdrFromFdno(f.fileno())

            # Extract metadata
            name = (
                header[rpm.RPMTAG_NAME].decode()
                if isinstance(header[rpm.RPMTAG_NAME], bytes)
                else header[rpm.RPMTAG_NAME]
            )
            version = (
                header[rpm.RPMTAG_VERSION].decode()
                if isinstance(header[rpm.RPMTAG_VERSION], bytes)
                else header[rpm.RPMTAG_VERSION]
            )
            release = (
                header[rpm.RPMTAG_RELEASE].decode()
                if isinstance(header[rpm.RPMTAG_RELEASE], bytes)
                else header[rpm.RPMTAG_RELEASE]
            )
            arch = (
                header[rpm.RPMTAG_ARCH].decode()
                if isinstance(header[rpm.RPMTAG_ARCH], bytes)
                else header[rpm.RPMTAG_ARCH]
            )

            # Validate extracted metadata
            try:
                name = validate_package_name(name)
                version = validate_metadata_string(version, "version", max_length=128)
                release = validate_metadata_string(release, "release", max_length=128)
                arch = validate_metadata_string(arch, "architecture", max_length=64)
            except ValidationError as e:
                raise RPMParsingError(f"Invalid metadata in RPM: {e}")

            # Determine if source package
            source_rpm = header.get(rpm.RPMTAG_SOURCERPM)
            is_source = source_rpm is None or arch in ("src", "nosrc")

            return PackageMetadata(
                name=name, version=version, release=release, arch=arch, is_source=is_source
            )

        except Exception as e:
            raise RPMParsingError(f"Failed to parse RPM with rpm library: {e}")

    def _parse_manually(self, rpm_path: Path) -> PackageMetadata:
        """
        Parse RPM manually by reading the file structure.

        Args:
            rpm_path: Path to the RPM file

        Returns:
            PackageMetadata object

        Raises:
            RPMParsingError: If parsing fails
        """
        try:
            with open(rpm_path, "rb") as f:
                # Read and verify lead (96 bytes)
                lead = f.read(96)
                if len(lead) < 96:
                    raise RPMParsingError("Invalid RPM file: too short")

                if lead[:4] != self.RPM_LEAD_MAGIC:
                    raise RPMParsingError("Invalid RPM file: bad magic number")

                # Skip signature header
                self._skip_header(f)

                # Parse main header
                header_data = self._read_header(f)

                # Extract metadata from header
                name = self._get_header_string(header_data, self.TAG_NAME)
                version = self._get_header_string(header_data, self.TAG_VERSION)
                release = self._get_header_string(header_data, self.TAG_RELEASE)
                arch = self._get_header_string(header_data, self.TAG_ARCH)
                source_rpm = self._get_header_string(header_data, self.TAG_SOURCERPM)

                if not all([name, version, release, arch]):
                    raise RPMParsingError("Missing required metadata fields")

                # Validate extracted metadata (type narrowing - not None after check)
                assert (
                    name is not None
                    and version is not None
                    and release is not None
                    and arch is not None
                )
                try:
                    name = validate_package_name(name)
                    version = validate_metadata_string(version, "version", max_length=128)
                    release = validate_metadata_string(release, "release", max_length=128)
                    arch = validate_metadata_string(arch, "architecture", max_length=64)
                except ValidationError as e:
                    raise RPMParsingError(f"Invalid metadata in RPM: {e}")

                # Determine if source package
                is_source = source_rpm is None or arch in ("src", "nosrc")

                return PackageMetadata(
                    name=name, version=version, release=release, arch=arch, is_source=is_source
                )

        except RPMParsingError:
            raise
        except Exception as e:
            raise RPMParsingError(f"Failed to parse RPM manually: {e}")

    def _skip_header(self, f) -> None:
        """
        Skip over an RPM header section.

        Args:
            f: File object positioned at start of header
        """
        # Read header magic and reserved bytes (8 bytes)
        header_intro = f.read(8)
        if len(header_intro) < 8:
            raise RPMParsingError("Invalid header: too short")

        # Read index count and data size (8 bytes)
        index_info = f.read(8)
        if len(index_info) < 8:
            raise RPMParsingError("Invalid header: missing index info")

        index_count = struct.unpack(">I", index_info[:4])[0]
        data_size = struct.unpack(">I", index_info[4:])[0]

        # Skip index entries (16 bytes each) and data
        skip_size = (index_count * 16) + data_size
        f.seek(skip_size, 1)

        # Align to 8-byte boundary
        pos = f.tell()
        alignment = (8 - (pos % 8)) % 8
        if alignment:
            f.seek(alignment, 1)

    def _read_header(self, f) -> Dict[int, Any]:
        """
        Read and parse an RPM header section.

        Args:
            f: File object positioned at start of header

        Returns:
            Dictionary mapping tag IDs to their values
        """
        # Read header magic and reserved bytes (8 bytes)
        header_intro = f.read(8)
        if len(header_intro) < 8:
            raise RPMParsingError("Invalid header: too short")

        # Read index count and data size (8 bytes)
        index_info = f.read(8)
        if len(index_info) < 8:
            raise RPMParsingError("Invalid header: missing index info")

        index_count = struct.unpack(">I", index_info[:4])[0]
        data_size = struct.unpack(">I", index_info[4:])[0]

        # Read index entries
        index_data = f.read(index_count * 16)
        if len(index_data) < index_count * 16:
            raise RPMParsingError("Invalid header: incomplete index")

        # Read data store
        store_data = f.read(data_size)
        if len(store_data) < data_size:
            raise RPMParsingError("Invalid header: incomplete data store")

        # Parse index entries
        header_dict = {}
        for i in range(index_count):
            offset = i * 16
            tag = struct.unpack(">I", index_data[offset : offset + 4])[0]
            data_type = struct.unpack(">I", index_data[offset + 4 : offset + 8])[0]
            data_offset = struct.unpack(">I", index_data[offset + 8 : offset + 12])[0]
            count = struct.unpack(">I", index_data[offset + 12 : offset + 16])[0]

            header_dict[tag] = {
                "type": data_type,
                "offset": data_offset,
                "count": count,
                "data": store_data,
            }

        return header_dict

    def _get_header_string(self, header_data: Dict[int, Any], tag: int) -> Optional[str]:
        """
        Extract a string value from header data.

        Args:
            header_data: Parsed header dictionary
            tag: Tag ID to extract

        Returns:
            String value or None if not found
        """
        if tag not in header_data:
            return None

        entry = header_data[tag]
        offset = entry["offset"]
        data = entry["data"]

        # Find null terminator
        end = data.find(b"\x00", offset)
        if end == -1:
            end = len(data)

        try:
            return data[offset:end].decode("utf-8")
        except UnicodeDecodeError:
            return data[offset:end].decode("latin-1")

    def extract_dependencies(self, rpm_path: Path) -> List[Dependency]:
        """
        Extract all dependencies from an RPM file.

        Args:
            rpm_path: Path to the RPM file

        Returns:
            List of Dependency objects

        Raises:
            RPMParsingError: If extraction fails
        """
        # Validate file path and size
        try:
            validate_file_path(str(rpm_path), must_exist=True)
            validate_file_size(rpm_path, max_size_mb=500)
        except ValidationError as e:
            raise RPMParsingError(f"Invalid RPM file: {e}")

        if self.use_rpm_library:
            return self._extract_deps_with_rpm_library(rpm_path)
        else:
            return self._extract_deps_manually(rpm_path)

    def _extract_deps_with_rpm_library(self, rpm_path: Path) -> List[Dependency]:
        """
        Extract dependencies using the rpm Python library.

        Args:
            rpm_path: Path to the RPM file

        Returns:
            List of Dependency objects

        Raises:
            RPMParsingError: If extraction fails
        """
        try:
            import rpm

            # Open RPM file
            ts = rpm.TransactionSet()
            ts.setVSFlags(rpm._RPMVSF_NOSIGNATURES)

            with open(rpm_path, "rb") as f:
                header = ts.hdrFromFdno(f.fileno())

            dependencies = []

            # Extract Requires dependencies
            requires_names = header.get(rpm.RPMTAG_REQUIRENAME, [])
            requires_flags = header.get(rpm.RPMTAG_REQUIREFLAGS, [])
            requires_versions = header.get(rpm.RPMTAG_REQUIREVERSION, [])

            for i, name in enumerate(requires_names):
                dep_name = name.decode() if isinstance(name, bytes) else name
                dep_flags = requires_flags[i] if i < len(requires_flags) else 0
                dep_version = None
                if i < len(requires_versions):
                    ver = requires_versions[i]
                    dep_version = ver.decode() if isinstance(ver, bytes) else ver

                dependencies.append(
                    Dependency(
                        name=dep_name,
                        version=dep_version if dep_version else None,
                        flags=dep_flags,
                        type="requires",
                    )
                )

            # Extract Provides information
            provides_names = header.get(rpm.RPMTAG_PROVIDENAME, [])
            provides_flags = header.get(rpm.RPMTAG_PROVIDEFLAGS, [])
            provides_versions = header.get(rpm.RPMTAG_PROVIDEVERSION, [])

            for i, name in enumerate(provides_names):
                dep_name = name.decode() if isinstance(name, bytes) else name
                dep_flags = provides_flags[i] if i < len(provides_flags) else 0
                dep_version = None
                if i < len(provides_versions):
                    ver = provides_versions[i]
                    dep_version = ver.decode() if isinstance(ver, bytes) else ver

                dependencies.append(
                    Dependency(
                        name=dep_name,
                        version=dep_version if dep_version else None,
                        flags=dep_flags,
                        type="provides",
                    )
                )

            # For source RPMs, try to extract BuildRequires
            # Note: BuildRequires may not always be in the header
            source_rpm = header.get(rpm.RPMTAG_SOURCERPM)
            arch = header[rpm.RPMTAG_ARCH]
            arch_str = arch.decode() if isinstance(arch, bytes) else arch
            is_source = source_rpm is None or arch_str in ("src", "nosrc")

            if is_source:
                # BuildRequires are typically stored as regular Requires in SRPMs
                # Mark them as buildrequires based on context
                for dep in dependencies:
                    if dep.type == "requires":
                        dep.type = "buildrequires"

            return dependencies

        except Exception as e:
            raise RPMParsingError(f"Failed to extract dependencies with rpm library: {e}")

    def _extract_deps_manually(self, rpm_path: Path) -> List[Dependency]:
        """
        Extract dependencies manually by reading the file structure.

        Args:
            rpm_path: Path to the RPM file

        Returns:
            List of Dependency objects

        Raises:
            RPMParsingError: If extraction fails
        """
        try:
            with open(rpm_path, "rb") as f:
                # Read and verify lead
                lead = f.read(96)
                if len(lead) < 96 or lead[:4] != self.RPM_LEAD_MAGIC:
                    raise RPMParsingError("Invalid RPM file")

                # Skip signature header
                self._skip_header(f)

                # Parse main header
                header_data = self._read_header(f)

                dependencies = []

                # Extract Requires dependencies
                requires_names = self._get_header_string_array(header_data, self.TAG_REQUIRENAME)
                requires_flags = self._get_header_int_array(header_data, self.TAG_REQUIREFLAGS)
                requires_versions = self._get_header_string_array(
                    header_data, self.TAG_REQUIREVERSION
                )

                for i, name in enumerate(requires_names):
                    flags = requires_flags[i] if i < len(requires_flags) else 0
                    version = requires_versions[i] if i < len(requires_versions) else None

                    dependencies.append(
                        Dependency(name=name, version=version, flags=flags, type="requires")
                    )

                # Extract Provides information
                provides_names = self._get_header_string_array(header_data, self.TAG_PROVIDENAME)
                provides_flags = self._get_header_int_array(header_data, self.TAG_PROVIDEFLAGS)
                provides_versions = self._get_header_string_array(
                    header_data, self.TAG_PROVIDEVERSION
                )

                for i, name in enumerate(provides_names):
                    flags = provides_flags[i] if i < len(provides_flags) else 0
                    version = provides_versions[i] if i < len(provides_versions) else None

                    dependencies.append(
                        Dependency(name=name, version=version, flags=flags, type="provides")
                    )

                # Check if source package and mark requires as buildrequires
                arch = self._get_header_string(header_data, self.TAG_ARCH)
                source_rpm = self._get_header_string(header_data, self.TAG_SOURCERPM)
                is_source = source_rpm is None or arch in ("src", "nosrc")

                if is_source:
                    for dep in dependencies:
                        if dep.type == "requires":
                            dep.type = "buildrequires"

                return dependencies

        except RPMParsingError:
            raise
        except Exception as e:
            raise RPMParsingError(f"Failed to extract dependencies manually: {e}")

    def _get_header_string_array(self, header_data: Dict[int, Any], tag: int) -> List[str]:
        """
        Extract an array of strings from header data.

        Args:
            header_data: Parsed header dictionary
            tag: Tag ID to extract

        Returns:
            List of strings (empty list if not found)
        """
        if tag not in header_data:
            return []

        entry = header_data[tag]
        offset = entry["offset"]
        count = entry["count"]
        data = entry["data"]

        strings = []
        current_offset = offset

        for _ in range(count):
            # Find null terminator
            end = data.find(b"\x00", current_offset)
            if end == -1:
                break

            try:
                string_val = data[current_offset:end].decode("utf-8")
            except UnicodeDecodeError:
                string_val = data[current_offset:end].decode("latin-1")

            strings.append(string_val)
            current_offset = end + 1

        return strings

    def _get_header_int_array(self, header_data: Dict[int, Any], tag: int) -> List[int]:
        """
        Extract an array of integers from header data.

        Args:
            header_data: Parsed header dictionary
            tag: Tag ID to extract

        Returns:
            List of integers (empty list if not found)
        """
        if tag not in header_data:
            return []

        entry = header_data[tag]
        offset = entry["offset"]
        count = entry["count"]
        data = entry["data"]
        data_type = entry["type"]

        integers = []

        # Type 4 = INT32
        if data_type == 4:
            for i in range(count):
                int_offset = offset + (i * 4)
                if int_offset + 4 <= len(data):
                    int_val = struct.unpack(">I", data[int_offset : int_offset + 4])[0]
                    integers.append(int_val)
        # Type 3 = INT16
        elif data_type == 3:
            for i in range(count):
                int_offset = offset + (i * 2)
                if int_offset + 2 <= len(data):
                    int_val = struct.unpack(">H", data[int_offset : int_offset + 2])[0]
                    integers.append(int_val)

        return integers
