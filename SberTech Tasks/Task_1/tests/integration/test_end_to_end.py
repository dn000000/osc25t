"""
Integration tests for end-to-end workflow.

Tests the complete workflow from repository download to graph generation.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import gzip

import pytest

from src.main import (
    download_repository,
    parse_packages,
    build_dependency_graphs,
    save_graphs,
    PackageProcessingError,
)
from src.repository import RepositoryDownloader, PackageInfo
from src.parser import PackageMetadata, Dependency
from src.graph import DependencyGraph


# Sample repository metadata for testing
SAMPLE_REPOMD_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<repomd xmlns="http://linux.duke.edu/metadata/repo">
  <data type="primary">
    <location href="repodata/primary.xml.gz"/>
    <checksum type="sha256">abc123</checksum>
  </data>
</repomd>
"""

SAMPLE_PRIMARY_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<metadata xmlns="http://linux.duke.edu/metadata/common" packages="4">
  <package type="rpm">
    <name>app-package</name>
    <arch>x86_64</arch>
    <version ver="1.0.0" rel="1"/>
    <checksum type="sha256">abc123</checksum>
    <location href="Packages/app-package-1.0.0-1.x86_64.rpm"/>
  </package>
  <package type="rpm">
    <name>lib-package</name>
    <arch>x86_64</arch>
    <version ver="2.0.0" rel="1"/>
    <checksum type="sha256">def456</checksum>
    <location href="Packages/lib-package-2.0.0-1.x86_64.rpm"/>
  </package>
  <package type="rpm">
    <name>app-package</name>
    <arch>src</arch>
    <version ver="1.0.0" rel="1"/>
    <checksum type="sha256">ghi789</checksum>
    <location href="Packages/app-package-1.0.0-1.src.rpm"/>
  </package>
  <package type="rpm">
    <name>python3</name>
    <arch>x86_64</arch>
    <version ver="3.9.0" rel="1"/>
    <checksum type="sha256">jkl012</checksum>
    <location href="Packages/python3-3.9.0-1.x86_64.rpm"/>
  </package>
</metadata>
"""


class TestEndToEndWorkflow:
    """Integration tests for complete workflow"""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing"""
        with tempfile.TemporaryDirectory() as cache_dir:
            with tempfile.TemporaryDirectory() as output_dir:
                yield {"cache": cache_dir, "output": output_dir}

    @pytest.fixture
    def sample_package_list(self):
        """Create a sample package list for testing"""
        return [
            PackageInfo(
                name="app-package",
                version="1.0.0",
                release="1",
                arch="x86_64",
                location="Packages/app-package-1.0.0-1.x86_64.rpm",
                checksum="abc123",
                is_source=False,
            ),
            PackageInfo(
                name="lib-package",
                version="2.0.0",
                release="1",
                arch="x86_64",
                location="Packages/lib-package-2.0.0-1.x86_64.rpm",
                checksum="def456",
                is_source=False,
            ),
            PackageInfo(
                name="app-package",
                version="1.0.0",
                release="1",
                arch="src",
                location="Packages/app-package-1.0.0-1.src.rpm",
                checksum="ghi789",
                is_source=True,
            ),
            PackageInfo(
                name="python3",
                version="3.9.0",
                release="1",
                arch="x86_64",
                location="Packages/python3-3.9.0-1.x86_64.rpm",
                checksum="jkl012",
                is_source=False,
            ),
        ]

    @patch("src.repository.requests.Session.get")
    def test_complete_workflow_with_mocked_repository(
        self, mock_get, temp_dirs, sample_package_list
    ):
        """Test complete workflow from download to graph generation"""
        # Setup mock responses
        repomd_response = Mock()
        repomd_response.content = SAMPLE_REPOMD_XML
        repomd_response.raise_for_status = Mock()

        primary_gz_data = gzip.compress(SAMPLE_PRIMARY_XML)
        primary_response = Mock()
        primary_response.content = primary_gz_data
        primary_response.raise_for_status = Mock()

        mock_get.side_effect = [repomd_response, primary_response]

        # Step 1: Download repository
        cache_path, package_list = download_repository(
            "https://example.com/repo", cache_dir=temp_dirs["cache"]
        )

        assert cache_path.exists()
        assert len(package_list) == 4
        assert any(pkg.name == "app-package" and not pkg.is_source for pkg in package_list)
        assert any(pkg.name == "app-package" and pkg.is_source for pkg in package_list)

        # Step 2: Parse packages
        packages_with_deps = parse_packages(package_list)

        assert len(packages_with_deps) == 4
        assert all(isinstance(metadata, PackageMetadata) for metadata, _ in packages_with_deps)

        # Step 3: Build dependency graphs
        runtime_graph, build_graph = build_dependency_graphs(packages_with_deps)

        assert isinstance(runtime_graph, DependencyGraph)
        assert isinstance(build_graph, DependencyGraph)
        assert runtime_graph.node_count() > 0

        # Step 4: Save graphs
        save_graphs(runtime_graph, build_graph, output_dir=temp_dirs["output"])

        # Verify output files exist
        runtime_file = Path(temp_dirs["output"]) / "runtime_graph.json"
        build_file = Path(temp_dirs["output"]) / "build_graph.json"
        summary_file = Path(temp_dirs["output"]) / "graph_summary.json"

        assert runtime_file.exists()
        assert build_file.exists()
        assert summary_file.exists()

        # Verify JSON content
        with open(runtime_file, "r") as f:
            runtime_data = json.load(f)
            assert runtime_data["graph_type"] == "runtime"
            assert "nodes" in runtime_data
            assert "edges" in runtime_data

        with open(build_file, "r") as f:
            build_data = json.load(f)
            assert build_data["graph_type"] == "build"
            assert "nodes" in build_data
            assert "edges" in build_data

        with open(summary_file, "r") as f:
            summary_data = json.load(f)
            assert "runtime_graph" in summary_data
            assert "build_graph" in summary_data

    def test_parse_packages_creates_metadata(self, sample_package_list):
        """Test that parse_packages creates PackageMetadata from PackageInfo"""
        packages_with_deps = parse_packages(sample_package_list)

        assert len(packages_with_deps) == 4

        # Check that metadata is correctly created
        for metadata, deps in packages_with_deps:
            assert isinstance(metadata, PackageMetadata)
            assert metadata.name in ["app-package", "lib-package", "python3"]
            assert metadata.version
            assert metadata.release
            assert metadata.arch
            assert isinstance(metadata.is_source, bool)
            assert isinstance(deps, list)

    def test_build_graphs_with_sample_dependencies(self):
        """Test building graphs with sample dependency data"""
        # Create sample packages with dependencies
        packages_with_deps = [
            (
                PackageMetadata("app-package", "1.0.0", "1", "x86_64", False),
                [
                    Dependency("lib-package", type="requires"),
                    Dependency("python3", type="requires"),
                ],
            ),
            (PackageMetadata("lib-package", "2.0.0", "1", "x86_64", False), []),
            (PackageMetadata("python3", "3.9.0", "1", "x86_64", False), []),
            (
                PackageMetadata("app-package", "1.0.0", "1", "src", True),
                [
                    Dependency("gcc", type="buildrequires"),
                    Dependency("make", type="buildrequires"),
                ],
            ),
        ]

        runtime_graph, build_graph = build_dependency_graphs(packages_with_deps)

        # Verify runtime graph
        assert runtime_graph.node_count() >= 3
        assert runtime_graph.has_node("app-package")
        assert runtime_graph.has_node("lib-package")
        assert runtime_graph.has_node("python3")

        # Verify build graph
        assert build_graph.node_count() >= 1
        assert build_graph.has_node("app-package")

    def test_save_graphs_creates_valid_json(self, temp_dirs):
        """Test that saved graphs contain valid JSON"""
        # Create simple graphs
        runtime_graph = DependencyGraph()
        runtime_graph.add_node("pkg-a")
        runtime_graph.add_node("pkg-b")
        runtime_graph.add_edge("pkg-a", "pkg-b")

        build_graph = DependencyGraph()
        build_graph.add_node("src-pkg")

        # Save graphs
        save_graphs(runtime_graph, build_graph, output_dir=temp_dirs["output"])

        # Verify files exist and contain valid JSON
        runtime_file = Path(temp_dirs["output"]) / "runtime_graph.json"
        build_file = Path(temp_dirs["output"]) / "build_graph.json"

        with open(runtime_file, "r") as f:
            runtime_data = json.load(f)
            assert runtime_data["graph_type"] == "runtime"
            assert len(runtime_data["nodes"]) == 2
            assert len(runtime_data["edges"]) == 1

        with open(build_file, "r") as f:
            build_data = json.load(f)
            assert build_data["graph_type"] == "build"
            assert len(build_data["nodes"]) == 1

    def test_workflow_handles_empty_package_list(self):
        """Test that workflow handles empty package list gracefully"""
        # Empty package list should raise an error
        with pytest.raises(PackageProcessingError):
            parse_packages([])

    def test_workflow_with_circular_dependencies(self):
        """Test workflow with circular dependencies"""
        # Create packages with circular dependencies
        packages_with_deps = [
            (
                PackageMetadata("pkg-a", "1.0", "1", "x86_64", False),
                [Dependency("pkg-b", type="requires")],
            ),
            (
                PackageMetadata("pkg-b", "1.0", "1", "x86_64", False),
                [Dependency("pkg-c", type="requires")],
            ),
            (
                PackageMetadata("pkg-c", "1.0", "1", "x86_64", False),
                [Dependency("pkg-a", type="requires")],
            ),
        ]

        runtime_graph, build_graph = build_dependency_graphs(packages_with_deps)

        # Verify graph was built
        assert runtime_graph.node_count() == 3
        assert runtime_graph.edge_count() == 3

        # Verify cycle detection works
        cycles = runtime_graph.detect_cycles()
        assert len(cycles) > 0
        assert any("pkg-a" in cycle for cycle in cycles)

    def test_workflow_with_missing_dependencies(self):
        """Test workflow with missing package dependencies"""
        # Create packages with dependencies on non-existent packages
        packages_with_deps = [
            (
                PackageMetadata("pkg-a", "1.0", "1", "x86_64", False),
                [Dependency("pkg-b", type="requires"), Dependency("missing-pkg", type="requires")],
            ),
            (PackageMetadata("pkg-b", "1.0", "1", "x86_64", False), []),
        ]

        runtime_graph, build_graph = build_dependency_graphs(packages_with_deps)

        # Verify graph was built with placeholder nodes
        assert runtime_graph.node_count() >= 3
        assert runtime_graph.has_node("pkg-a")
        assert runtime_graph.has_node("pkg-b")
        assert runtime_graph.has_node("missing-pkg")

        # Verify placeholder metadata
        missing_node = runtime_graph.nodes["missing-pkg"]
        assert missing_node.metadata.get("placeholder") == "true"

    @patch("src.repository.requests.Session.get")
    def test_download_repository_with_retry(self, mock_get, temp_dirs):
        """Test repository download with retry logic"""
        # First attempt fails, second succeeds
        repomd_response = Mock()
        repomd_response.content = SAMPLE_REPOMD_XML
        repomd_response.raise_for_status = Mock()

        primary_gz_data = gzip.compress(SAMPLE_PRIMARY_XML)
        primary_response = Mock()
        primary_response.content = primary_gz_data
        primary_response.raise_for_status = Mock()

        import requests

        mock_get.side_effect = [
            requests.RequestException("Network error"),
            repomd_response,
            primary_response,
        ]

        # Should succeed after retry
        cache_path, package_list = download_repository(
            "https://example.com/repo", cache_dir=temp_dirs["cache"]
        )

        assert cache_path.exists()
        assert len(package_list) > 0

    def test_graphs_separate_runtime_and_build_deps(self):
        """Test that runtime and build graphs are properly separated"""
        packages_with_deps = [
            (
                PackageMetadata("app", "1.0", "1", "x86_64", False),
                [Dependency("lib", type="requires")],
            ),
            (PackageMetadata("lib", "1.0", "1", "x86_64", False), []),
            (
                PackageMetadata("app", "1.0", "1", "src", True),
                [Dependency("gcc", type="buildrequires")],
            ),
        ]

        runtime_graph, build_graph = build_dependency_graphs(packages_with_deps)

        # Runtime graph should have binary packages
        assert runtime_graph.has_node("app")
        assert runtime_graph.has_node("lib")

        # Build graph should have source packages
        assert build_graph.has_node("app")
        assert build_graph.has_node("gcc")

        # Verify dependencies are in correct graphs
        app_runtime_deps = runtime_graph.get_dependencies("app")
        assert "lib" in app_runtime_deps

        app_build_deps = build_graph.get_dependencies("app")
        assert "gcc" in app_build_deps
