"""
Unit tests for main orchestration module.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import logging

from src.main import (
    setup_logging,
    download_repository,
    parse_packages,
    build_dependency_graphs,
    save_graphs,
    clear_cache,
    PackageProcessingError,
)
from src.repository import PackageInfo, RepositoryDownloadError
from src.parser import PackageMetadata, Dependency
from src.graph import DependencyGraph


class TestSetupLogging:
    """Tests for logging setup"""

    def test_setup_logging_default(self):
        """Test default logging setup"""
        setup_logging(verbose=False)
        logger = logging.getLogger(__name__)
        assert logger.level <= logging.INFO

    def test_setup_logging_verbose(self):
        """Test verbose logging setup"""
        setup_logging(verbose=True)
        logger = logging.getLogger(__name__)
        assert logger.level <= logging.DEBUG

    def test_setup_logging_with_custom_log_file(self):
        """Test logging setup with custom log file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            log_file = str(Path(tmpdir) / "test.log")

            # Setup logging
            setup_logging(verbose=False, log_file=log_file)

            # Log a message
            test_logger = logging.getLogger("test_logger")
            test_logger.info("Test message")

            # Close all handlers to release file locks
            for handler in logging.root.handlers[:]:
                handler.close()
                logging.root.removeHandler(handler)

            # Check log file was created
            assert Path(log_file).exists()


class TestParsePackages:
    """Tests for parse_packages function"""

    def test_parse_packages_success(self):
        """Test successful package parsing"""
        package_list = [
            PackageInfo("pkg1", "1.0", "1", "x86_64", "Packages/pkg1.rpm", "abc123", False),
            PackageInfo("pkg2", "2.0", "1", "x86_64", "Packages/pkg2.rpm", "def456", False),
        ]

        result = parse_packages(package_list)

        assert len(result) == 2
        assert all(isinstance(metadata, PackageMetadata) for metadata, _ in result)
        assert result[0][0].name == "pkg1"
        assert result[1][0].name == "pkg2"

    def test_parse_packages_empty_list(self):
        """Test that empty package list raises error"""
        with pytest.raises(PackageProcessingError):
            parse_packages([])

    def test_parse_packages_creates_empty_dependencies(self):
        """Test that parse_packages creates empty dependency lists"""
        package_list = [
            PackageInfo("pkg1", "1.0", "1", "x86_64", "Packages/pkg1.rpm", "abc123", False),
        ]

        result = parse_packages(package_list)

        assert len(result) == 1
        metadata, deps = result[0]
        assert isinstance(deps, list)
        assert len(deps) == 0

    def test_parse_packages_handles_source_packages(self):
        """Test that parse_packages handles source packages"""
        package_list = [
            PackageInfo("pkg1", "1.0", "1", "src", "Packages/pkg1.src.rpm", "abc123", True),
        ]

        result = parse_packages(package_list)

        assert len(result) == 1
        metadata, _ = result[0]
        assert metadata.is_source is True


class TestBuildDependencyGraphs:
    """Tests for build_dependency_graphs function"""

    def test_build_graphs_success(self):
        """Test successful graph building"""
        packages_with_deps = [
            (PackageMetadata("pkg1", "1.0", "1", "x86_64", False), []),
            (PackageMetadata("pkg2", "1.0", "1", "x86_64", False), []),
            (PackageMetadata("pkg1", "1.0", "1", "src", True), []),
        ]

        runtime_graph, build_graph = build_dependency_graphs(packages_with_deps)

        assert isinstance(runtime_graph, DependencyGraph)
        assert isinstance(build_graph, DependencyGraph)
        assert runtime_graph.node_count() >= 2
        assert build_graph.node_count() >= 1

    def test_build_graphs_with_dependencies(self):
        """Test graph building with dependencies"""
        packages_with_deps = [
            (
                PackageMetadata("app", "1.0", "1", "x86_64", False),
                [Dependency("lib", type="requires")],
            ),
            (PackageMetadata("lib", "1.0", "1", "x86_64", False), []),
        ]

        runtime_graph, build_graph = build_dependency_graphs(packages_with_deps)

        assert runtime_graph.has_node("app")
        assert runtime_graph.has_node("lib")
        assert "lib" in runtime_graph.get_dependencies("app")

    def test_build_graphs_detects_cycles(self):
        """Test that graph building detects cycles"""
        packages_with_deps = [
            (
                PackageMetadata("pkg-a", "1.0", "1", "x86_64", False),
                [Dependency("pkg-b", type="requires")],
            ),
            (
                PackageMetadata("pkg-b", "1.0", "1", "x86_64", False),
                [Dependency("pkg-a", type="requires")],
            ),
        ]

        runtime_graph, build_graph = build_dependency_graphs(packages_with_deps)

        cycles = runtime_graph.detect_cycles()
        assert len(cycles) > 0


class TestSaveGraphs:
    """Tests for save_graphs function"""

    def test_save_graphs_creates_files(self):
        """Test that save_graphs creates output files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            runtime_graph = DependencyGraph()
            runtime_graph.add_node("pkg1")

            build_graph = DependencyGraph()
            build_graph.add_node("src-pkg")

            save_graphs(runtime_graph, build_graph, output_dir=tmpdir)

            runtime_file = Path(tmpdir) / "runtime_graph.json"
            build_file = Path(tmpdir) / "build_graph.json"
            summary_file = Path(tmpdir) / "graph_summary.json"

            assert runtime_file.exists()
            assert build_file.exists()
            assert summary_file.exists()

    def test_save_graphs_creates_output_dir(self):
        """Test that save_graphs creates output directory if it doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir) / "output"

            runtime_graph = DependencyGraph()
            build_graph = DependencyGraph()

            save_graphs(runtime_graph, build_graph, output_dir=str(output_dir))

            assert output_dir.exists()
            assert output_dir.is_dir()

    def test_save_graphs_valid_json(self):
        """Test that saved graphs contain valid JSON"""
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            runtime_graph = DependencyGraph()
            runtime_graph.add_node("pkg1")
            runtime_graph.add_node("pkg2")
            runtime_graph.add_edge("pkg1", "pkg2")

            build_graph = DependencyGraph()

            save_graphs(runtime_graph, build_graph, output_dir=tmpdir)

            runtime_file = Path(tmpdir) / "runtime_graph.json"
            with open(runtime_file, "r") as f:
                data = json.load(f)
                assert data["graph_type"] == "runtime"
                assert "nodes" in data
                assert "edges" in data


class TestClearCache:
    """Tests for clear_cache function"""

    def test_clear_cache_removes_files(self):
        """Test that clear_cache removes cached files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some cache files
            cache_file1 = Path(tmpdir) / "cache1.xml"
            cache_file2 = Path(tmpdir) / "cache2.xml"
            cache_file1.write_text("cache content 1")
            cache_file2.write_text("cache content 2")

            clear_cache(cache_dir=tmpdir)

            assert not cache_file1.exists()
            assert not cache_file2.exists()

    def test_clear_cache_nonexistent_dir(self):
        """Test that clear_cache handles non-existent directory"""
        # Should not raise an error
        clear_cache(cache_dir="/nonexistent/cache/dir")

    def test_clear_cache_empty_dir(self):
        """Test that clear_cache handles empty directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Should not raise an error
            clear_cache(cache_dir=tmpdir)


class TestDownloadRepository:
    """Tests for download_repository function"""

    @patch("src.repository.requests.Session.get")
    def test_download_repository_success(self, mock_get):
        """Test successful repository download"""
        import gzip

        # Mock responses
        repomd_xml = b"""<?xml version="1.0"?>
        <repomd xmlns="http://linux.duke.edu/metadata/repo">
          <data type="primary">
            <location href="repodata/primary.xml.gz"/>
          </data>
        </repomd>"""

        primary_xml = b"""<?xml version="1.0"?>
        <metadata xmlns="http://linux.duke.edu/metadata/common" packages="1">
          <package type="rpm">
            <name>test-pkg</name>
            <arch>x86_64</arch>
            <version ver="1.0" rel="1"/>
            <checksum type="sha256">abc123</checksum>
            <location href="Packages/test-pkg.rpm"/>
          </package>
        </metadata>"""

        repomd_response = Mock()
        repomd_response.content = repomd_xml
        repomd_response.raise_for_status = Mock()

        primary_response = Mock()
        primary_response.content = gzip.compress(primary_xml)
        primary_response.raise_for_status = Mock()

        mock_get.side_effect = [repomd_response, primary_response]

        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path, package_list = download_repository(
                "https://example.com/repo", cache_dir=tmpdir
            )

            assert cache_path.exists()
            assert len(package_list) == 1
            assert package_list[0].name == "test-pkg"

    @patch("src.repository.requests.Session.get")
    def test_download_repository_failure(self, mock_get):
        """Test repository download failure"""
        import requests

        mock_get.side_effect = requests.RequestException("Network error")

        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(RepositoryDownloadError):
                download_repository("https://example.com/repo", cache_dir=tmpdir)
