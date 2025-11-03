"""
Unit tests for dependency extractor module.
"""

import pytest

from src.extractor import DependencyExtractor
from src.parser import PackageMetadata, Dependency


class TestDependencyExtractor:
    """Tests for DependencyExtractor class"""

    @pytest.fixture
    def extractor(self):
        """Create a DependencyExtractor instance"""
        return DependencyExtractor()

    @pytest.fixture
    def sample_packages_with_deps(self):
        """Create sample packages with dependencies for testing"""
        # Binary package 1
        pkg1_metadata = PackageMetadata(
            name="app-package", version="1.0.0", release="1", arch="x86_64", is_source=False
        )
        pkg1_deps = [
            Dependency(name="lib-package", type="requires"),
            Dependency(name="python3", type="requires"),
            Dependency(name="app-package", version="1.0.0", type="provides"),
        ]

        # Binary package 2
        pkg2_metadata = PackageMetadata(
            name="lib-package", version="2.0.0", release="1", arch="x86_64", is_source=False
        )
        pkg2_deps = [
            Dependency(name="libc.so.6", type="requires"),
            Dependency(name="lib-package", version="2.0.0", type="provides"),
        ]

        # Source package
        pkg3_metadata = PackageMetadata(
            name="app-package", version="1.0.0", release="1", arch="src", is_source=True
        )
        pkg3_deps = [
            Dependency(name="gcc", type="buildrequires"),
            Dependency(name="make", type="buildrequires"),
            Dependency(name="python3-devel", type="buildrequires"),
        ]

        # Package providing python3
        pkg4_metadata = PackageMetadata(
            name="python3", version="3.9.0", release="1", arch="x86_64", is_source=False
        )
        pkg4_deps = [
            Dependency(name="python3", version="3.9.0", type="provides"),
            Dependency(name="/usr/bin/python3", type="provides"),
        ]

        return [
            (pkg1_metadata, pkg1_deps),
            (pkg2_metadata, pkg2_deps),
            (pkg3_metadata, pkg3_deps),
            (pkg4_metadata, pkg4_deps),
        ]

    def test_extractor_initialization(self, extractor):
        """Test that extractor initializes correctly"""
        assert extractor is not None
        assert isinstance(extractor.virtual_provides_map, dict)
        assert len(extractor.virtual_provides_map) == 0

    def test_extract_runtime_deps(self, extractor, sample_packages_with_deps):
        """Test extracting runtime dependencies from binary packages"""
        runtime_deps = extractor.extract_runtime_deps(sample_packages_with_deps)

        # Should have runtime deps for binary packages only
        assert "app-package" in runtime_deps
        assert "lib-package" in runtime_deps
        assert "python3" in runtime_deps

        # Source package should not be in runtime deps
        # (Note: source packages are filtered out in extract_runtime_deps)

        # Check app-package dependencies
        app_deps = runtime_deps["app-package"]
        assert "lib-package" in app_deps
        assert "python3" in app_deps

        # lib-package should have filtered out system library
        lib_deps = runtime_deps["lib-package"]
        assert "libc.so.6" not in lib_deps  # System library filtered

    def test_extract_build_deps(self, extractor, sample_packages_with_deps):
        """Test extracting build dependencies from source packages"""
        build_deps = extractor.extract_build_deps(sample_packages_with_deps)

        # Should have build deps for source packages only
        assert "app-package" in build_deps

        # Check app-package build dependencies
        app_build_deps = build_deps["app-package"]
        assert "gcc" in app_build_deps
        assert "make" in app_build_deps
        assert "python3-devel" in app_build_deps

    def test_build_provides_map(self, extractor, sample_packages_with_deps):
        """Test building virtual provides map"""
        extractor._build_provides_map(sample_packages_with_deps)

        # Check that provides are mapped correctly
        assert "app-package" in extractor.virtual_provides_map
        assert "lib-package" in extractor.virtual_provides_map
        assert "python3" in extractor.virtual_provides_map
        assert "/usr/bin/python3" in extractor.virtual_provides_map

        # Check that packages are in the sets
        assert "app-package" in extractor.virtual_provides_map["app-package"]
        assert "python3" in extractor.virtual_provides_map["python3"]
        assert "python3" in extractor.virtual_provides_map["/usr/bin/python3"]

    def test_resolve_dependency_direct_package(self, extractor):
        """Test resolving a direct package name dependency"""
        resolved = extractor._resolve_dependency("some-package")
        assert resolved == ["some-package"]

    def test_resolve_dependency_virtual_provide(self, extractor):
        """Test resolving a virtual provide dependency"""
        # Setup provides map
        extractor.virtual_provides_map = {"virtual-package": {"real-package-1", "real-package-2"}}

        resolved = extractor._resolve_dependency("virtual-package")
        assert len(resolved) == 2
        assert "real-package-1" in resolved
        assert "real-package-2" in resolved

    def test_resolve_dependency_file_path(self, extractor):
        """Test resolving file path dependencies"""
        # Test known file mapping
        resolved = extractor._resolve_dependency("/usr/bin/python3")
        assert "python3" in resolved

        # Test file path in provides map
        extractor.virtual_provides_map = {"/usr/bin/custom": {"custom-package"}}
        resolved = extractor._resolve_dependency("/usr/bin/custom")
        assert "custom-package" in resolved

    def test_resolve_dependency_system_filter(self, extractor):
        """Test that system dependencies are filtered out"""
        # System dependencies should return empty list
        assert extractor._resolve_dependency("rpmlib(CompressedFileNames)") == []
        assert extractor._resolve_dependency("/bin/sh") == []
        assert extractor._resolve_dependency("libc.so.6") == []
        assert extractor._resolve_dependency("rtld(GNU_HASH)") == []

    def test_is_system_dependency(self, extractor):
        """Test system dependency detection"""
        # System dependencies
        assert extractor._is_system_dependency("rpmlib(PayloadFilesHavePrefix)") is True
        assert extractor._is_system_dependency("/bin/sh") is True
        assert extractor._is_system_dependency("libc.so.6") is True
        assert extractor._is_system_dependency("libpthread.so.0") is True
        assert extractor._is_system_dependency("config(package)") is True

        # Non-system dependencies
        assert extractor._is_system_dependency("python3") is False
        assert extractor._is_system_dependency("gcc") is False
        assert extractor._is_system_dependency("/usr/bin/python3") is False

    def test_resolve_file_dependency(self, extractor):
        """Test file dependency resolution"""
        # Known file mappings
        assert "python3" in extractor._resolve_file_dependency("/usr/bin/python3")
        assert "bash" in extractor._resolve_file_dependency("/bin/bash")
        assert "perl" in extractor._resolve_file_dependency("/usr/bin/perl")

        # Unknown file should return empty list
        assert extractor._resolve_file_dependency("/usr/bin/unknown") == []

        # File in provides map
        extractor.virtual_provides_map = {"/usr/bin/custom": {"custom-package"}}
        resolved = extractor._resolve_file_dependency("/usr/bin/custom")
        assert "custom-package" in resolved

    def test_extract_runtime_deps_removes_self_references(self, extractor):
        """Test that packages don't depend on themselves"""
        pkg_metadata = PackageMetadata(
            name="self-ref-package", version="1.0.0", release="1", arch="x86_64", is_source=False
        )
        pkg_deps = [
            Dependency(name="self-ref-package", type="requires"),
            Dependency(name="other-package", type="requires"),
        ]

        runtime_deps = extractor.extract_runtime_deps([(pkg_metadata, pkg_deps)])

        # Should not include self-reference
        assert "self-ref-package" not in runtime_deps["self-ref-package"]
        assert "other-package" in runtime_deps["self-ref-package"]

    def test_extract_build_deps_removes_self_references(self, extractor):
        """Test that source packages don't depend on themselves"""
        pkg_metadata = PackageMetadata(
            name="self-ref-src", version="1.0.0", release="1", arch="src", is_source=True
        )
        pkg_deps = [
            Dependency(name="self-ref-src", type="buildrequires"),
            Dependency(name="gcc", type="buildrequires"),
        ]

        build_deps = extractor.extract_build_deps([(pkg_metadata, pkg_deps)])

        # Should not include self-reference
        assert "self-ref-src" not in build_deps["self-ref-src"]
        assert "gcc" in build_deps["self-ref-src"]

    def test_extract_runtime_deps_removes_duplicates(self, extractor):
        """Test that duplicate dependencies are removed"""
        pkg_metadata = PackageMetadata(
            name="dup-package", version="1.0.0", release="1", arch="x86_64", is_source=False
        )
        pkg_deps = [
            Dependency(name="common-dep", type="requires"),
            Dependency(name="common-dep", type="requires"),
            Dependency(name="other-dep", type="requires"),
        ]

        runtime_deps = extractor.extract_runtime_deps([(pkg_metadata, pkg_deps)])

        # Should have unique dependencies only
        deps = runtime_deps["dup-package"]
        assert deps.count("common-dep") == 1
        assert "other-dep" in deps

    def test_extract_with_empty_package_list(self, extractor):
        """Test extraction with empty package list"""
        runtime_deps = extractor.extract_runtime_deps([])
        assert runtime_deps == {}

        build_deps = extractor.extract_build_deps([])
        assert build_deps == {}

    def test_extract_with_no_dependencies(self, extractor):
        """Test extraction when packages have no dependencies"""
        pkg_metadata = PackageMetadata(
            name="no-deps-package", version="1.0.0", release="1", arch="x86_64", is_source=False
        )

        runtime_deps = extractor.extract_runtime_deps([(pkg_metadata, [])])

        assert "no-deps-package" in runtime_deps
        assert runtime_deps["no-deps-package"] == []
