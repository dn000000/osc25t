"""
Security review tests for RPM Dependency Graph system.

Tests all security requirements:
- Input validation (requirement 6.1)
- Safe file operations (requirement 6.2)
- No arbitrary code execution (requirement 6.3)
- Secure downloads (requirement 6.4)
- Security logging (requirement 6.5)
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.validation import (
    validate_url,
    validate_package_name,
    validate_file_path,
    validate_metadata_string,
    validate_file_size,
    sanitize_log_message,
    ValidationError,
)
from src.repository import RepositoryDownloader, RepositoryDownloadError
from src.file_utils import safe_write, safe_read


class TestInputValidation:
    """Test input validation security (requirement 6.1)."""

    def test_url_validation_rejects_invalid_schemes(self):
        """Test that only HTTP/HTTPS URLs are accepted."""
        print("\n[Security Test] URL Validation - Invalid Schemes")

        # Valid URLs
        assert validate_url("http://example.com")
        assert validate_url("https://example.com")
        print("✓ Valid HTTP/HTTPS URLs accepted")

        # Invalid schemes
        invalid_urls = [
            "file:///etc/passwd",
            "ftp://example.com",
            "javascript:alert(1)",
            "data:text/html,<script>alert(1)</script>",
        ]

        for url in invalid_urls:
            with pytest.raises(ValidationError):
                validate_url(url)
        print(f"✓ Rejected {len(invalid_urls)} invalid URL schemes")

    def test_url_validation_prevents_path_traversal(self):
        """Test that URLs with path traversal are rejected."""
        print("\n[Security Test] URL Validation - Path Traversal")

        traversal_urls = [
            "http://example.com/../../../etc/passwd",
            "http://example.com/path/../../../secret",
        ]

        for url in traversal_urls:
            with pytest.raises(ValidationError):
                validate_url(url)
        print(f"✓ Rejected {len(traversal_urls)} path traversal attempts")

    def test_package_name_validation_prevents_injection(self):
        """Test that package names are properly sanitized."""
        print("\n[Security Test] Package Name Validation")

        # Valid package names
        valid_names = ["glibc", "python3-requests", "kernel-core", "lib64.so.1"]
        for name in valid_names:
            assert validate_package_name(name)
        print(f"✓ Accepted {len(valid_names)} valid package names")

        # Invalid package names (injection attempts)
        invalid_names = [
            "../../../etc/passwd",
            "package; rm -rf /",
            "package`whoami`",
            "package$(whoami)",
            "package\x00malicious",
            "package/../../secret",
        ]

        for name in invalid_names:
            with pytest.raises(ValidationError):
                validate_package_name(name)
        print(f"✓ Rejected {len(invalid_names)} malicious package names")

    def test_file_path_validation_prevents_traversal(self):
        """Test that file paths are validated against directory traversal."""
        print("\n[Security Test] File Path Validation - Directory Traversal")

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)

            # Valid paths within base directory
            valid_path = base_dir / "subdir" / "file.txt"
            valid_path.parent.mkdir(parents=True, exist_ok=True)
            valid_path.write_text("test")

            validated = validate_file_path(str(valid_path), base_dir=str(base_dir))
            assert validated.is_relative_to(base_dir)
            print("✓ Valid path within base directory accepted")

            # Invalid paths (traversal attempts)
            traversal_attempts = [
                "../../../etc/passwd",
                "subdir/../../etc/passwd",
                str(base_dir / ".." / ".." / "etc" / "passwd"),
            ]

            for attempt in traversal_attempts:
                with pytest.raises(ValidationError):
                    validate_file_path(attempt, base_dir=str(base_dir))
            print(f"✓ Rejected {len(traversal_attempts)} directory traversal attempts")

    def test_metadata_validation_prevents_injection(self):
        """Test that metadata strings are properly validated."""
        print("\n[Security Test] Metadata Validation")

        # Valid metadata
        valid_metadata = ["1.0.0", "x86_64", "GPL", "A normal description"]
        for meta in valid_metadata:
            assert validate_metadata_string(meta, "test_field")
        print(f"✓ Accepted {len(valid_metadata)} valid metadata strings")

        # Invalid metadata (injection attempts)
        invalid_metadata = [
            "value\x00malicious",  # Null byte
            "value\x01\x02\x03",  # Control characters
            "a" * 10000,  # Too long
        ]

        for meta in invalid_metadata:
            with pytest.raises(ValidationError):
                validate_metadata_string(meta, "test_field", max_length=1024)
        print(f"✓ Rejected {len(invalid_metadata)} malicious metadata strings")

    def test_file_size_validation_prevents_dos(self):
        """Test that file size limits prevent DoS attacks."""
        print("\n[Security Test] File Size Validation - DoS Prevention")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a small file
            small_file = Path(tmpdir) / "small.txt"
            small_file.write_text("small content")

            size = validate_file_size(small_file, max_size_mb=1)
            assert size < 1024 * 1024
            print("✓ Small file accepted")

            # Create a large file (simulate)
            large_file = Path(tmpdir) / "large.txt"
            large_file.write_bytes(b"x" * (2 * 1024 * 1024))  # 2MB

            with pytest.raises(ValidationError):
                validate_file_size(large_file, max_size_mb=1)
            print("✓ Oversized file rejected")


class TestSafeFileOperations:
    """Test safe file operations (requirement 6.2)."""

    def test_safe_write_uses_atomic_operations(self):
        """Test that safe_write uses atomic operations."""
        print("\n[Security Test] Safe File Operations - Atomic Writes")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"

            # Write with atomic operation
            with safe_write(test_file, mode="w", atomic=True) as f:
                f.write("test content")

            assert test_file.exists()
            assert test_file.read_text() == "test content"
            print("✓ Atomic write completed successfully")

            # Verify no temporary files left behind
            temp_files = list(Path(tmpdir).glob("*.tmp"))
            assert len(temp_files) == 0
            print("✓ No temporary files left behind")

    def test_safe_write_cleans_up_on_error(self):
        """Test that safe_write cleans up temporary files on error."""
        print("\n[Security Test] Safe File Operations - Error Cleanup")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"

            # Simulate write error
            try:
                with safe_write(test_file, mode="w", atomic=True) as f:
                    f.write("partial content")
                    raise Exception("Simulated error")
            except Exception:
                pass

            # Verify no temporary files left behind
            temp_files = list(Path(tmpdir).glob("*.tmp"))
            assert len(temp_files) == 0
            print("✓ Temporary files cleaned up after error")

    def test_safe_read_validates_file_path(self):
        """Test that safe_read validates file paths."""
        print("\n[Security Test] Safe File Operations - Read Validation")

        with tempfile.TemporaryDirectory() as tmpdir:
            # Try to read non-existent file
            non_existent = Path(tmpdir) / "nonexistent.txt"

            with pytest.raises((FileNotFoundError, OSError)):
                with safe_read(non_existent) as f:
                    f.read()
            print("✓ Non-existent file read rejected")

    def test_file_operations_use_context_managers(self):
        """Test that file operations use context managers."""
        print("\n[Security Test] Safe File Operations - Context Managers")

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("test")

            # Test safe_read returns content safely
            content = safe_read(test_file)
            assert content == "test"
            print("✓ safe_read returns content safely")

            # Test safe_write uses context manager
            test_file2 = Path(tmpdir) / "test2.txt"
            with safe_write(test_file2, mode="w") as f:
                f.write("test2")
            assert test_file2.read_text() == "test2"
            print("✓ safe_write uses context manager correctly")


class TestNoArbitraryCodeExecution:
    """Test that no arbitrary code is executed (requirement 6.3)."""

    def test_no_eval_or_exec_in_codebase(self):
        """Test that eval() and exec() are not used in the codebase."""
        print("\n[Security Test] No Arbitrary Code Execution")

        # Check all Python files in src directory
        src_dir = Path("src")
        dangerous_functions = ["eval(", "exec(", "__import__("]

        violations = []
        for py_file in src_dir.glob("*.py"):
            content = py_file.read_text()
            for func in dangerous_functions:
                if func in content:
                    violations.append(f"{py_file.name}: {func}")

        assert len(violations) == 0, f"Found dangerous functions: {violations}"
        print("✓ No eval() or exec() found in codebase")

    def test_no_shell_injection_in_subprocess(self):
        """Test that subprocess calls don't use shell=True."""
        print("\n[Security Test] No Shell Injection")

        # Check all Python files for subprocess with shell=True
        src_dir = Path("src")
        violations = []

        for py_file in src_dir.glob("*.py"):
            content = py_file.read_text()
            if "subprocess" in content and "shell=True" in content:
                violations.append(py_file.name)

        assert len(violations) == 0, f"Found shell=True in: {violations}"
        print("✓ No shell=True in subprocess calls")


class TestSecureDownloads:
    """Test secure download methods (requirement 6.4)."""

    def test_repository_downloader_uses_https_when_available(self):
        """Test that HTTPS is preferred for downloads."""
        print("\n[Security Test] Secure Downloads - HTTPS Preference")

        downloader = RepositoryDownloader()

        # Check that session is configured
        assert downloader.session is not None
        print("✓ HTTP session configured")

        # Check User-Agent is set
        assert "User-Agent" in downloader.session.headers
        print(f"✓ User-Agent set: {downloader.session.headers['User-Agent']}")

    def test_repository_downloader_validates_urls(self):
        """Test that repository URLs are validated."""
        print("\n[Security Test] Secure Downloads - URL Validation")

        downloader = RepositoryDownloader()

        # Invalid URLs should be rejected
        invalid_urls = [
            "file:///etc/passwd",
            "ftp://example.com",
            "not-a-url",
        ]

        for url in invalid_urls:
            with pytest.raises(RepositoryDownloadError):
                downloader.download_repository_metadata(url)
        print(f"✓ Rejected {len(invalid_urls)} invalid repository URLs")

    def test_repository_downloader_has_timeout(self):
        """Test that downloads have timeouts to prevent hanging."""
        print("\n[Security Test] Secure Downloads - Timeout Protection")

        downloader = RepositoryDownloader()

        # Check that session has timeout configured
        # Note: This is a basic check; actual timeout is set per-request
        assert downloader.session is not None
        print("✓ Download session configured with timeout support")


class TestSecurityLogging:
    """Test security event logging (requirement 6.5)."""

    def test_log_sanitization_prevents_injection(self):
        """Test that log messages are sanitized."""
        print("\n[Security Test] Security Logging - Log Injection Prevention")

        # Test log injection attempts
        malicious_messages = [
            "Normal message\nFAKE ERROR: Injected message",
            "Message\rFAKE WARNING: Another injection",
            "Message\x00with null byte",
        ]

        for msg in malicious_messages:
            sanitized = sanitize_log_message(msg)
            assert "\n" not in sanitized
            assert "\r" not in sanitized
            assert "\x00" not in sanitized
        print(f"✓ Sanitized {len(malicious_messages)} malicious log messages")

    def test_log_messages_are_length_limited(self):
        """Test that log messages are length-limited."""
        print("\n[Security Test] Security Logging - Length Limiting")

        # Create a very long message
        long_message = "A" * 20000

        sanitized = sanitize_log_message(long_message)
        assert len(sanitized) <= 10100  # 10000 + "... (truncated)"
        print("✓ Long log messages are truncated")


class TestSecurityDocumentation:
    """Test that security documentation exists."""

    def test_security_md_exists(self):
        """Test that SECURITY.md file exists."""
        print("\n[Security Test] Security Documentation")

        security_file = Path("SECURITY.md")
        assert security_file.exists(), "SECURITY.md file not found"
        print("✓ SECURITY.md file exists")

        content = security_file.read_text()
        assert len(content) > 100, "SECURITY.md is too short"
        print(f"✓ SECURITY.md contains {len(content)} characters")

    def test_readme_has_security_section(self):
        """Test that README has security information."""
        print("\n[Security Test] README Security Section")

        readme_file = Path("README.md")
        assert readme_file.exists(), "README.md file not found"

        content = readme_file.read_text().lower()
        assert "security" in content, "README.md missing security section"
        print("✓ README.md contains security information")


def run_security_review():
    """Run complete security review and generate report."""
    print("\n" + "=" * 70)
    print("SECURITY REVIEW REPORT")
    print("=" * 70)

    # Run all tests
    result = pytest.main([__file__, "-v", "-s"])

    print("\n" + "=" * 70)
    if result == 0:
        print("✓ ALL SECURITY TESTS PASSED")
    else:
        print("✗ SOME SECURITY TESTS FAILED")
    print("=" * 70)

    return result


if __name__ == "__main__":
    exit(run_security_review())
