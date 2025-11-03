"""
Unit tests for repository downloader module.
"""

import gzip
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
import requests

from src.repository import RepositoryDownloader, RepositoryDownloadError, PackageInfo


# Sample repomd.xml content
SAMPLE_REPOMD_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<repomd xmlns="http://linux.duke.edu/metadata/repo">
  <data type="primary">
    <location href="repodata/primary.xml.gz"/>
    <checksum type="sha256">abc123</checksum>
  </data>
</repomd>
"""

# Sample primary.xml content
SAMPLE_PRIMARY_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<metadata xmlns="http://linux.duke.edu/metadata/common" packages="2">
  <package type="rpm">
    <name>test-package</name>
    <arch>x86_64</arch>
    <version ver="1.0.0" rel="1"/>
    <checksum type="sha256">def456</checksum>
    <location href="Packages/test-package-1.0.0-1.x86_64.rpm"/>
  </package>
  <package type="rpm">
    <name>source-package</name>
    <arch>src</arch>
    <version ver="2.0.0" rel="1"/>
    <checksum type="sha256">ghi789</checksum>
    <location href="Packages/source-package-2.0.0-1.src.rpm"/>
  </package>
</metadata>
"""


class TestRepositoryDownloader:
    """Tests for RepositoryDownloader class"""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create a temporary cache directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield tmpdir

    @pytest.fixture
    def downloader(self, temp_cache_dir):
        """Create a RepositoryDownloader instance with temp cache"""
        return RepositoryDownloader(cache_dir=temp_cache_dir)

    def test_init_creates_cache_directory(self, temp_cache_dir):
        """Test that initialization creates cache directory"""
        cache_path = Path(temp_cache_dir) / "test_cache"
        downloader = RepositoryDownloader(cache_dir=str(cache_path))
        assert cache_path.exists()
        assert cache_path.is_dir()

    def test_invalid_url_raises_error(self, downloader):
        """Test that invalid URLs raise RepositoryDownloadError"""
        with pytest.raises(RepositoryDownloadError, match="Invalid repository URL"):
            downloader.download_repository_metadata("ftp://invalid.com")

    @patch("src.repository.requests.Session.get")
    def test_download_repository_metadata_success(self, mock_get, downloader):
        """Test successful repository metadata download"""
        # Mock repomd.xml response
        repomd_response = Mock()
        repomd_response.content = SAMPLE_REPOMD_XML
        repomd_response.raise_for_status = Mock()

        # Mock primary.xml.gz response
        primary_gz_data = gzip.compress(SAMPLE_PRIMARY_XML)
        primary_response = Mock()
        primary_response.content = primary_gz_data
        primary_response.raise_for_status = Mock()

        # Configure mock to return different responses
        mock_get.side_effect = [repomd_response, primary_response]

        # Download metadata
        cache_path = downloader.download_repository_metadata("https://example.com/repo")

        # Verify cache file was created
        assert cache_path.exists()
        assert cache_path.is_file()

        # Verify content
        with open(cache_path, "rb") as f:
            content = f.read()
            assert b"test-package" in content

    @patch("src.repository.requests.Session.get")
    def test_download_with_retry_on_network_failure(self, mock_get, downloader):
        """Test retry logic on network failures"""
        # First two attempts fail, third succeeds
        mock_get.side_effect = [
            requests.RequestException("Network error"),
            requests.RequestException("Network error"),
            Mock(content=SAMPLE_REPOMD_XML, raise_for_status=Mock()),
        ]

        # Should succeed after retries
        result = downloader._download_with_retry("https://example.com/test", max_retries=3)
        assert result == SAMPLE_REPOMD_XML
        assert mock_get.call_count == 3

    @patch("src.repository.requests.Session.get")
    def test_download_fails_after_max_retries(self, mock_get, downloader):
        """Test that download fails after exhausting retries"""
        mock_get.side_effect = requests.RequestException("Network error")

        with pytest.raises(RepositoryDownloadError, match="Failed to download"):
            downloader._download_with_retry("https://example.com/test", max_retries=3)

        assert mock_get.call_count == 3

    def test_parse_repomd_extracts_primary_location(self, downloader):
        """Test parsing repomd.xml to extract primary.xml location"""
        location = downloader._parse_repomd(SAMPLE_REPOMD_XML)
        assert location == "repodata/primary.xml.gz"

    def test_parse_repomd_missing_primary_raises_error(self, downloader):
        """Test that missing primary metadata raises error"""
        invalid_repomd = b"""<?xml version="1.0" encoding="UTF-8"?>
        <repomd xmlns="http://linux.duke.edu/metadata/repo">
          <data type="other">
            <location href="repodata/other.xml.gz"/>
          </data>
        </repomd>
        """

        with pytest.raises(RepositoryDownloadError, match="Primary metadata not found"):
            downloader._parse_repomd(invalid_repomd)

    def test_parse_repomd_invalid_xml_raises_error(self, downloader):
        """Test that invalid XML raises error"""
        invalid_xml = b"<invalid>xml"

        with pytest.raises(RepositoryDownloadError, match="Failed to parse repomd.xml"):
            downloader._parse_repomd(invalid_xml)

    def test_cache_metadata_creates_file(self, downloader, temp_cache_dir):
        """Test that caching creates a file with correct content"""
        test_data = b"test metadata content"
        repo_url = "https://example.com/repo"

        cache_path = downloader._cache_metadata(test_data, repo_url)

        assert cache_path.exists()
        assert cache_path.parent == Path(temp_cache_dir)

        with open(cache_path, "rb") as f:
            assert f.read() == test_data

    def test_get_package_list_parses_packages(self, downloader, temp_cache_dir):
        """Test parsing primary.xml to extract package list"""
        # Create a temporary primary.xml file
        primary_xml_path = Path(temp_cache_dir) / "primary.xml"
        with open(primary_xml_path, "wb") as f:
            f.write(SAMPLE_PRIMARY_XML)

        packages = downloader.get_package_list(primary_xml_path)

        assert len(packages) == 2

        # Check first package (binary)
        pkg1 = packages[0]
        assert pkg1.name == "test-package"
        assert pkg1.version == "1.0.0"
        assert pkg1.release == "1"
        assert pkg1.arch == "x86_64"
        assert pkg1.location == "Packages/test-package-1.0.0-1.x86_64.rpm"
        assert pkg1.checksum == "def456"
        assert pkg1.is_source is False

        # Check second package (source)
        pkg2 = packages[1]
        assert pkg2.name == "source-package"
        assert pkg2.arch == "src"
        assert pkg2.is_source is True

    def test_get_package_list_handles_malformed_packages(self, downloader, temp_cache_dir):
        """Test that malformed packages are skipped with logging"""
        malformed_xml = b"""<?xml version="1.0" encoding="UTF-8"?>
        <metadata xmlns="http://linux.duke.edu/metadata/common" packages="2">
          <package type="rpm">
            <name>valid-package</name>
            <arch>x86_64</arch>
            <version ver="1.0.0" rel="1"/>
            <checksum type="sha256">abc123</checksum>
            <location href="Packages/valid-package-1.0.0-1.x86_64.rpm"/>
          </package>
          <package type="rpm">
            <arch>x86_64</arch>
            <version ver="1.0.0" rel="1"/>
          </package>
        </metadata>
        """

        primary_xml_path = Path(temp_cache_dir) / "primary.xml"
        with open(primary_xml_path, "wb") as f:
            f.write(malformed_xml)

        packages = downloader.get_package_list(primary_xml_path)

        # Should only get the valid package
        assert len(packages) == 1
        assert packages[0].name == "valid-package"

    def test_get_package_list_invalid_file_raises_error(self, downloader, temp_cache_dir):
        """Test that invalid XML file raises error"""
        invalid_path = Path(temp_cache_dir) / "nonexistent.xml"

        with pytest.raises(RepositoryDownloadError):
            downloader.get_package_list(invalid_path)
