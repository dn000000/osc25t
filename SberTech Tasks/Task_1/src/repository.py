"""
Repository downloader module for fetching and parsing RPM repository metadata.
"""

import gzip
import hashlib
import logging
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Dict
from urllib.parse import urljoin
from html.parser import HTMLParser

import requests

from src.validation import (
    validate_url,
    validate_package_name,
    validate_file_path,
    validate_metadata_string,
    validate_file_size,
    ValidationError,
)

logger = logging.getLogger(__name__)


@dataclass
class PackageInfo:
    """Represents a package in the repository"""

    name: str
    version: str
    release: str
    arch: str
    location: str
    checksum: str
    is_source: bool
    requires: List[str] = None  # List of dependency names
    provides: List[str] = None  # List of provided capabilities
    
    def __post_init__(self):
        if self.requires is None:
            self.requires = []
        if self.provides is None:
            self.provides = []


class RepositoryDownloadError(Exception):
    """Raised when repository download fails"""

    pass


class HTMLDirectoryParser(HTMLParser):
    """Parse HTML directory listing to extract RPM file links"""

    def __init__(self):
        super().__init__()
        self.rpm_files = []
        self.current_tag = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            for attr, value in attrs:
                if attr == "href" and value.endswith((".rpm", ".src.rpm")):
                    self.rpm_files.append(value)

    def get_rpm_files(self):
        return self.rpm_files


class RepositoryDownloader:
    """Downloads and parses RPM repository metadata"""

    def __init__(self, cache_dir: str = "data/cache"):
        """
        Initialize the repository downloader.

        Args:
            cache_dir: Directory to store cached repository metadata
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "RPM-Dependency-Graph/1.0"})

    def download_repository_metadata(self, repo_url: str, max_retries: int = 3) -> Path:
        """
        Download repository metadata from the given URL.

        Args:
            repo_url: Base URL of the RPM repository
            max_retries: Maximum number of retry attempts for failed downloads

        Returns:
            Path to the cached primary.xml file

        Raises:
            RepositoryDownloadError: If download fails after all retries
        """
        # Validate URL
        try:
            repo_url = validate_url(repo_url, allowed_schemes=["http", "https"])
        except ValidationError as e:
            raise RepositoryDownloadError(f"Invalid repository URL: {e}")

        # Ensure URL ends with /
        if not repo_url.endswith("/"):
            repo_url += "/"

        # Try standard repodata approach first
        try:
            return self._download_standard_metadata(repo_url, max_retries)
        except RepositoryDownloadError as e:
            error_msg = str(e)
            logger.warning(f"Standard metadata download failed: {e}")
            
            # Only try HTML listing if it's a 404 error (no repodata)
            # Don't try HTML listing for other errors like file too large
            if "404" in error_msg or "Not Found" in error_msg:
                logger.info("Attempting to parse HTML directory listing...")
                return self._download_from_html_listing(repo_url, max_retries)
            else:
                # Re-raise the original error for other cases
                raise

    def _download_standard_metadata(self, repo_url: str, max_retries: int) -> Path:
        """
        Download repository metadata using standard repodata structure.

        Args:
            repo_url: Base URL of the RPM repository
            max_retries: Maximum number of retry attempts

        Returns:
            Path to the cached primary.xml file

        Raises:
            RepositoryDownloadError: If download fails
        """
        # Download repomd.xml to find primary.xml location
        repomd_url = urljoin(repo_url, "repodata/repomd.xml")
        logger.info(f"Downloading repository metadata from {repomd_url}")

        repomd_data = self._download_with_retry(repomd_url, max_retries)

        # Parse repomd.xml to find primary.xml.gz location
        primary_location = self._parse_repomd(repomd_data)

        # Download primary.xml.gz or primary.xml.zst
        primary_url = urljoin(repo_url, primary_location)
        logger.info(f"Downloading primary metadata from {primary_url}")

        primary_compressed_data = self._download_with_retry(primary_url, max_retries)

        # Decompress based on file extension
        if primary_location.endswith('.zst'):
            try:
                import zstandard as zstd
                dctx = zstd.ZstdDecompressor()
                primary_xml_data = dctx.decompress(primary_compressed_data, max_output_size=500*1024*1024)  # 500MB max
            except ImportError:
                raise RepositoryDownloadError(
                    "Zstandard compression detected but 'zstandard' library not installed. "
                    "Install it with: pip install zstandard"
                )
        elif primary_location.endswith('.gz'):
            primary_xml_data = gzip.decompress(primary_compressed_data)
        else:
            # Assume uncompressed
            primary_xml_data = primary_compressed_data
        
        cache_path = self._cache_metadata(primary_xml_data, repo_url)

        logger.info(f"Repository metadata cached at {cache_path}")
        return cache_path

    def _download_from_html_listing(self, repo_url: str, max_retries: int) -> Path:
        """
        Download RPM files from HTML directory listing and create metadata.

        Args:
            repo_url: Base URL of the RPM repository
            max_retries: Maximum number of retry attempts

        Returns:
            Path to the cached metadata file

        Raises:
            RepositoryDownloadError: If download fails
        """
        logger.info(f"Fetching HTML directory listing from {repo_url}")
        
        # Download HTML page
        html_data = self._download_with_retry(repo_url, max_retries)
        html_content = html_data.decode('utf-8', errors='ignore')
        
        # Parse HTML to find RPM files
        parser = HTMLDirectoryParser()
        parser.feed(html_content)
        rpm_files = parser.get_rpm_files()
        
        if not rpm_files:
            raise RepositoryDownloadError("No RPM files found in directory listing")
        
        logger.info(f"Found {len(rpm_files)} RPM files in directory listing")
        
        # Ask user if they want to download RPMs for dependency extraction
        logger.info("=" * 70)
        logger.info("DEPENDENCY EXTRACTION OPTIONS:")
        logger.info("=" * 70)
        logger.info("Option 1: Create basic metadata without dependencies (fast)")
        logger.info("Option 2: Download RPM files and extract dependencies (slow, accurate)")
        logger.info(f"Note: Option 2 will download {len(rpm_files)} RPM files")
        logger.info("=" * 70)
        
        # For now, create synthetic metadata without downloading
        # This can be enhanced later with a command-line flag
        metadata_xml = self._create_synthetic_metadata(rpm_files, repo_url)
        cache_path = self._cache_metadata(metadata_xml.encode('utf-8'), repo_url)
        
        logger.info(f"Synthetic metadata cached at {cache_path}")
        logger.info("Note: To extract dependencies, use --extract-deps flag (feature coming soon)")
        return cache_path
    
    def download_and_parse_rpms(self, repo_url: str, rpm_files: List[str], max_retries: int = 3, 
                                max_packages: Optional[int] = None) -> Path:
        """
        Download RPM files and extract full metadata including dependencies.

        Args:
            repo_url: Base URL of the RPM repository
            rpm_files: List of RPM filenames to download
            max_retries: Maximum number of retry attempts
            max_packages: Maximum number of packages to process (None for all)

        Returns:
            Path to the cached metadata file with dependencies

        Raises:
            RepositoryDownloadError: If download fails
        """
        from src.parser import RPMParser
        
        # Ensure URL ends with /
        if not repo_url.endswith("/"):
            repo_url += "/"
        
        # Limit number of packages if specified
        if max_packages:
            rpm_files = rpm_files[:max_packages]
            logger.info(f"Processing first {max_packages} packages only")
        
        logger.info(f"Downloading and parsing {len(rpm_files)} RPM files...")
        logger.info("This may take a while depending on file sizes and network speed")
        
        parser = RPMParser()
        rpm_cache_dir = self.cache_dir / "rpms"
        rpm_cache_dir.mkdir(exist_ok=True)
        
        packages_data = []
        processed = 0
        failed = 0
        
        for idx, rpm_file in enumerate(rpm_files, 1):
            try:
                # Download RPM file
                rpm_url = urljoin(repo_url, rpm_file)
                rpm_local_path = rpm_cache_dir / rpm_file
                
                # Skip if already cached
                if not rpm_local_path.exists():
                    logger.info(f"[{idx}/{len(rpm_files)}] Downloading {rpm_file}...")
                    rpm_data = self._download_with_retry(rpm_url, max_retries)
                    
                    with open(rpm_local_path, 'wb') as f:
                        f.write(rpm_data)
                else:
                    logger.info(f"[{idx}/{len(rpm_files)}] Using cached {rpm_file}")
                
                # Parse RPM to extract metadata and dependencies
                metadata = parser.parse_rpm_header(rpm_local_path)
                dependencies = parser.extract_dependencies(rpm_local_path)
                
                # Fix: Source RPM files should have arch='src'
                # The parser may extract the target arch, but we need to check the filename
                if rpm_file.endswith('.src.rpm'):
                    from src.parser import PackageMetadata
                    metadata = PackageMetadata(
                        name=metadata.name,
                        version=metadata.version,
                        release=metadata.release,
                        arch='src',
                        is_source=True
                    )
                
                packages_data.append({
                    'metadata': metadata,
                    'dependencies': dependencies,
                    'location': rpm_file
                })
                
                processed += 1
                
                # Progress indicator
                if idx % 100 == 0 or idx == len(rpm_files):
                    logger.info(f"Progress: {idx}/{len(rpm_files)} ({(idx/len(rpm_files)*100):.1f}%)")
                
            except Exception as e:
                failed += 1
                logger.warning(f"Failed to process {rpm_file}: {e}")
                continue
        
        logger.info(f"Successfully processed {processed} packages, {failed} failed")
        
        # Create metadata XML with dependencies
        metadata_xml = self._create_metadata_with_deps(packages_data)
        cache_path = self._cache_metadata(metadata_xml.encode('utf-8'), repo_url)
        
        logger.info(f"Metadata with dependencies cached at {cache_path}")
        return cache_path
    
    def _create_metadata_with_deps(self, packages_data: List[Dict]) -> str:
        """
        Create primary.xml metadata with full dependency information.

        Args:
            packages_data: List of dictionaries containing metadata and dependencies

        Returns:
            XML string in primary.xml format
        """
        xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_parts.append('<metadata xmlns="http://linux.duke.edu/metadata/common" xmlns:rpm="http://linux.duke.edu/metadata/rpm" packages="{}">'.format(len(packages_data)))
        
        for pkg_data in packages_data:
            metadata = pkg_data['metadata']
            dependencies = pkg_data['dependencies']
            location = pkg_data['location']
            
            xml_parts.append('  <package type="rpm">')
            xml_parts.append(f'    <name>{self._escape_xml(metadata.name)}</name>')
            xml_parts.append(f'    <arch>{self._escape_xml(metadata.arch)}</arch>')
            xml_parts.append(f'    <version epoch="0" ver="{self._escape_xml(metadata.version)}" rel="{self._escape_xml(metadata.release)}"/>')
            xml_parts.append(f'    <checksum type="sha256"></checksum>')
            xml_parts.append('    <summary></summary>')
            xml_parts.append('    <description></description>')
            xml_parts.append('    <packager></packager>')
            xml_parts.append('    <url></url>')
            xml_parts.append('    <time file="0" build="0"/>')
            xml_parts.append('    <size package="0" installed="0" archive="0"/>')
            xml_parts.append(f'    <location href="{self._escape_xml(location)}"/>')
            xml_parts.append('    <format>')
            xml_parts.append('      <rpm:license></rpm:license>')
            xml_parts.append('      <rpm:vendor></rpm:vendor>')
            xml_parts.append('      <rpm:group></rpm:group>')
            xml_parts.append('      <rpm:buildhost></rpm:buildhost>')
            xml_parts.append('      <rpm:sourcerpm></rpm:sourcerpm>')
            
            # Add provides
            provides = [d for d in dependencies if d.type == 'provides']
            if provides:
                xml_parts.append('      <rpm:provides>')
                for dep in provides:
                    if dep.version:
                        xml_parts.append(f'        <rpm:entry name="{self._escape_xml(dep.name)}" ver="{self._escape_xml(dep.version)}"/>')
                    else:
                        xml_parts.append(f'        <rpm:entry name="{self._escape_xml(dep.name)}"/>')
                xml_parts.append('      </rpm:provides>')
            else:
                xml_parts.append('      <rpm:provides/>')
            
            # Add requires/buildrequires
            requires = [d for d in dependencies if d.type in ('requires', 'buildrequires')]
            if requires:
                xml_parts.append('      <rpm:requires>')
                for dep in requires:
                    if dep.version:
                        xml_parts.append(f'        <rpm:entry name="{self._escape_xml(dep.name)}" ver="{self._escape_xml(dep.version)}"/>')
                    else:
                        xml_parts.append(f'        <rpm:entry name="{self._escape_xml(dep.name)}"/>')
                xml_parts.append('      </rpm:requires>')
            else:
                xml_parts.append('      <rpm:requires/>')
            
            xml_parts.append('    </format>')
            xml_parts.append('  </package>')
        
        xml_parts.append('</metadata>')
        return '\n'.join(xml_parts)

    def _create_synthetic_metadata(self, rpm_files: List[str], repo_url: str) -> str:
        """
        Create synthetic primary.xml metadata from RPM file list.

        Args:
            rpm_files: List of RPM filenames
            repo_url: Base repository URL

        Returns:
            XML string in primary.xml format
        """
        xml_parts = ['<?xml version="1.0" encoding="UTF-8"?>']
        xml_parts.append('<metadata xmlns="http://linux.duke.edu/metadata/common" xmlns:rpm="http://linux.duke.edu/metadata/rpm" packages="{}">'.format(len(rpm_files)))
        
        for rpm_file in rpm_files:
            # Parse RPM filename: name-version-release.arch.rpm
            # Example: bash-4.2.46-35.el7.x86_64.rpm
            match = re.match(r'^(.+)-([^-]+)-([^-]+)\.([^.]+)\.rpm$', rpm_file)
            
            if not match:
                logger.warning(f"Could not parse RPM filename: {rpm_file}")
                continue
            
            name, version, release, arch = match.groups()
            
            # Handle .src.rpm files
            if rpm_file.endswith('.src.rpm'):
                arch = 'src'
                # Re-parse for source RPMs
                match = re.match(r'^(.+)-([^-]+)-([^-]+)\.src\.rpm$', rpm_file)
                if match:
                    name, version, release = match.groups()
            
            is_source = arch in ('src', 'nosrc')
            
            xml_parts.append('  <package type="rpm">')
            xml_parts.append(f'    <name>{self._escape_xml(name)}</name>')
            xml_parts.append(f'    <arch>{self._escape_xml(arch)}</arch>')
            xml_parts.append(f'    <version epoch="0" ver="{self._escape_xml(version)}" rel="{self._escape_xml(release)}"/>')
            xml_parts.append(f'    <checksum type="sha256"></checksum>')
            xml_parts.append('    <summary></summary>')
            xml_parts.append('    <description></description>')
            xml_parts.append('    <packager></packager>')
            xml_parts.append('    <url></url>')
            xml_parts.append('    <time file="0" build="0"/>')
            xml_parts.append('    <size package="0" installed="0" archive="0"/>')
            xml_parts.append(f'    <location href="{self._escape_xml(rpm_file)}"/>')
            xml_parts.append('    <format>')
            xml_parts.append('      <rpm:license></rpm:license>')
            xml_parts.append('      <rpm:vendor></rpm:vendor>')
            xml_parts.append('      <rpm:group></rpm:group>')
            xml_parts.append('      <rpm:buildhost></rpm:buildhost>')
            xml_parts.append('      <rpm:sourcerpm></rpm:sourcerpm>')
            xml_parts.append('      <rpm:provides/>')
            xml_parts.append('      <rpm:requires/>')
            xml_parts.append('    </format>')
            xml_parts.append('  </package>')
        
        xml_parts.append('</metadata>')
        return '\n'.join(xml_parts)

    def _escape_xml(self, text: str) -> str:
        """Escape special XML characters"""
        return (text.replace('&', '&amp;')
                   .replace('<', '&lt;')
                   .replace('>', '&gt;')
                   .replace('"', '&quot;')
                   .replace("'", '&apos;'))

    def _download_with_retry(self, url: str, max_retries: int) -> bytes:
        """
        Download data from URL with exponential backoff retry logic.

        Args:
            url: URL to download from
            max_retries: Maximum number of retry attempts

        Returns:
            Downloaded data as bytes

        Raises:
            RepositoryDownloadError: If all retry attempts fail
        """
        last_error = None

        for attempt in range(max_retries):
            try:
                response = self.session.get(url, timeout=30)
                response.raise_for_status()
                return response.content
            except requests.RequestException as e:
                last_error = e
                if attempt < max_retries - 1:
                    wait_time = 2**attempt  # Exponential backoff: 1s, 2s, 4s
                    logger.warning(
                        f"Download failed (attempt {attempt + 1}/{max_retries}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"Download failed after {max_retries} attempts: {e}")

        raise RepositoryDownloadError(
            f"Failed to download {url} after {max_retries} attempts: {last_error}"
        )

    def _parse_repomd(self, repomd_data: bytes) -> str:
        """
        Parse repomd.xml to find the location of primary.xml.gz.

        Args:
            repomd_data: Raw repomd.xml data

        Returns:
            Relative path to primary.xml.gz

        Raises:
            RepositoryDownloadError: If primary metadata location not found
        """
        try:
            root = ET.fromstring(repomd_data)

            # Handle XML namespace
            namespace = {"repo": "http://linux.duke.edu/metadata/repo"}

            # Find primary data element
            primary_elem = root.find(".//repo:data[@type='primary']", namespace)

            if primary_elem is None:
                # Try without namespace
                primary_elem = root.find(".//*[@type='primary']")

            if primary_elem is None:
                raise RepositoryDownloadError("Primary metadata not found in repomd.xml")

            # Get location
            location_elem = primary_elem.find("repo:location", namespace)
            if location_elem is None:
                location_elem = primary_elem.find("location")

            if location_elem is None:
                raise RepositoryDownloadError("Primary metadata location not found")

            href = location_elem.get("href")
            if not href:
                raise RepositoryDownloadError("Primary metadata href attribute missing")

            return href

        except ET.ParseError as e:
            raise RepositoryDownloadError(f"Failed to parse repomd.xml: {e}")

    def _cache_metadata(self, data: bytes, repo_url: str) -> Path:
        """
        Cache metadata to local filesystem.

        Args:
            data: Metadata content to cache
            repo_url: Repository URL (used to generate cache filename)

        Returns:
            Path to cached file
        """
        # Validate data size (limit to 500MB for large repositories)
        if len(data) > 500 * 1024 * 1024:
            raise RepositoryDownloadError("Metadata file too large (>500MB)")

        # Generate cache filename from repo URL hash
        url_hash = hashlib.md5(repo_url.encode()).hexdigest()
        cache_path = self.cache_dir / f"primary_{url_hash}.xml"

        # Validate cache path is within cache directory
        try:
            validate_file_path(str(cache_path), base_dir=str(self.cache_dir))
        except ValidationError as e:
            raise RepositoryDownloadError(f"Invalid cache path: {e}")

        # Use context manager for safe file operations
        try:
            with open(cache_path, "wb") as f:
                f.write(data)
        except (OSError, IOError) as e:
            raise RepositoryDownloadError(f"Failed to write cache file: {e}")

        return cache_path

    def get_package_list(self, primary_xml_path: Path) -> List[PackageInfo]:
        """
        Parse primary.xml to extract package information.

        Args:
            primary_xml_path: Path to primary.xml file

        Returns:
            List of PackageInfo objects

        Raises:
            RepositoryDownloadError: If parsing fails
        """
        logger.info(f"Parsing package list from {primary_xml_path}")

        # Validate file path and size
        try:
            validate_file_path(str(primary_xml_path), must_exist=True)
            # Increase limit to 500MB for large repositories
            validate_file_size(primary_xml_path, max_size_mb=500)
        except ValidationError as e:
            raise RepositoryDownloadError(f"Invalid primary.xml file: {e}")

        try:
            tree = ET.parse(primary_xml_path)
            root = tree.getroot()

            # Handle XML namespace
            namespace = {"common": "http://linux.duke.edu/metadata/common"}

            packages = []
            package_elements = root.findall(".//common:package", namespace)

            # Try without namespace if no packages found
            if not package_elements:
                package_elements = root.findall(".//package")

            total_elements = len(package_elements)
            logger.info(f"Found {total_elements} package entries to parse")

            error_count = 0
            progress_interval = max(1, total_elements // 10)

            for idx, pkg_elem in enumerate(package_elements, 1):
                try:
                    package_info = self._extract_package_info(pkg_elem, namespace)
                    if package_info:
                        packages.append(package_info)
                    else:
                        error_count += 1

                    # Progress indicator
                    if idx % progress_interval == 0 or idx == total_elements:
                        progress_pct = (idx / total_elements) * 100
                        logger.debug(
                            f"Parsing progress: {idx}/{total_elements} ({progress_pct:.1f}%)"
                        )

                except Exception as e:
                    error_count += 1
                    # Log error but continue processing other packages
                    pkg_name = pkg_elem.find(".//name")
                    pkg_name_text = pkg_name.text if pkg_name is not None else "unknown"
                    logger.warning(f"Failed to parse package {pkg_name_text}: {e}")
                    logger.debug("Package parsing error details:", exc_info=True)
                    continue

            if error_count > 0:
                logger.warning(f"Encountered {error_count} errors while parsing packages")

            if not packages:
                raise RepositoryDownloadError("No valid packages found in repository metadata")

            logger.info(f"Successfully parsed {len(packages)} packages")
            return packages

        except ET.ParseError as e:
            logger.error(f"XML parsing error: {e}")
            raise RepositoryDownloadError(f"Failed to parse primary.xml: {e}")
        except RepositoryDownloadError:
            raise
        except Exception as e:
            logger.error(f"Unexpected error reading primary.xml: {e}", exc_info=True)
            raise RepositoryDownloadError(f"Error reading primary.xml: {e}")

    def _extract_package_info(self, pkg_elem: ET.Element, namespace: dict) -> Optional[PackageInfo]:
        """
        Extract package information from a package XML element.

        Args:
            pkg_elem: XML element representing a package
            namespace: XML namespace dictionary

        Returns:
            PackageInfo object or None if extraction fails
        """
        # Extract name
        name_elem = pkg_elem.find("common:name", namespace)
        if name_elem is None:
            name_elem = pkg_elem.find("name")
        if name_elem is None or name_elem.text is None:
            return None
        name = name_elem.text

        # Validate package name
        try:
            name = validate_package_name(name)
        except ValidationError as e:
            logger.warning(f"Invalid package name: {e}")
            return None

        # Extract version info
        version_elem = pkg_elem.find("common:version", namespace)
        if version_elem is None:
            version_elem = pkg_elem.find("version")
        if version_elem is None:
            return None

        version = version_elem.get("ver", "")
        release = version_elem.get("rel", "")

        # Validate version and release
        try:
            version = validate_metadata_string(version, "version", max_length=128)
            release = validate_metadata_string(release, "release", max_length=128)
        except ValidationError as e:
            logger.warning(f"Invalid version/release for package {name}: {e}")
            return None

        # Extract architecture
        arch_elem = pkg_elem.find("common:arch", namespace)
        if arch_elem is None:
            arch_elem = pkg_elem.find("arch")
        arch = arch_elem.text if arch_elem is not None and arch_elem.text is not None else "noarch"

        # Validate architecture
        try:
            arch = validate_metadata_string(arch, "architecture", max_length=64)
        except ValidationError as e:
            logger.warning(f"Invalid architecture for package {name}: {e}")
            return None

        # Extract location
        location_elem = pkg_elem.find("common:location", namespace)
        if location_elem is None:
            location_elem = pkg_elem.find("location")
        if location_elem is None:
            return None
        location = location_elem.get("href", "")

        # Validate location (should be a relative path)
        try:
            location = validate_metadata_string(location, "location", max_length=512)
            # Ensure no absolute paths or path traversal
            if location.startswith("/") or ".." in location:
                logger.warning(f"Suspicious location path for package {name}: {location}")
                return None
        except ValidationError as e:
            logger.warning(f"Invalid location for package {name}: {e}")
            return None

        # Extract checksum
        checksum_elem = pkg_elem.find("common:checksum", namespace)
        if checksum_elem is None:
            checksum_elem = pkg_elem.find("checksum")
        checksum = (
            checksum_elem.text
            if checksum_elem is not None and checksum_elem.text is not None
            else ""
        )

        # Validate checksum (should be hex string)
        if checksum:
            try:
                checksum = validate_metadata_string(checksum, "checksum", max_length=128)
                if not re.match(r"^[a-fA-F0-9]+$", checksum):
                    logger.warning(f"Invalid checksum format for package {name}")
                    checksum = ""
            except ValidationError:
                checksum = ""

        # Ensure checksum is not None for PackageInfo
        if not checksum:
            checksum = ""

        # Determine if source package
        # Source packages typically have arch='src' or name ends with '.src'
        is_source = arch == "src" or arch == "nosrc" or name.endswith(".src")

        # Extract dependencies from format section
        requires_list = []
        provides_list = []
        
        format_elem = pkg_elem.find("common:format", namespace)
        if format_elem is None:
            format_elem = pkg_elem.find("format")
        
        if format_elem is not None:
            # Extract requires
            rpm_ns = {"rpm": "http://linux.duke.edu/metadata/rpm"}
            requires_elem = format_elem.find("rpm:requires", rpm_ns)
            if requires_elem is None:
                requires_elem = format_elem.find("requires")
            
            if requires_elem is not None:
                for entry in requires_elem.findall("rpm:entry", rpm_ns):
                    dep_name = entry.get("name")
                    if dep_name:
                        requires_list.append(dep_name)
                # Try without namespace
                if not requires_list:
                    for entry in requires_elem.findall("entry"):
                        dep_name = entry.get("name")
                        if dep_name:
                            requires_list.append(dep_name)
            
            # Extract provides
            provides_elem = format_elem.find("rpm:provides", rpm_ns)
            if provides_elem is None:
                provides_elem = format_elem.find("provides")
            
            if provides_elem is not None:
                for entry in provides_elem.findall("rpm:entry", rpm_ns):
                    prov_name = entry.get("name")
                    if prov_name:
                        provides_list.append(prov_name)
                # Try without namespace
                if not provides_list:
                    for entry in provides_elem.findall("entry"):
                        prov_name = entry.get("name")
                        if prov_name:
                            provides_list.append(prov_name)

        return PackageInfo(
            name=name,
            version=version,
            release=release,
            arch=arch,
            location=location,
            checksum=checksum,
            is_source=is_source,
            requires=requires_list,
            provides=provides_list,
        )
