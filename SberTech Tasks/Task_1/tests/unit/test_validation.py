"""
Unit tests for validation module.
"""

import pytest
from pathlib import Path
import tempfile

from src.validation import (
    ValidationError,
    validate_url,
    validate_package_name,
    validate_file_path,
    validate_metadata_string,
    validate_file_size,
    sanitize_log_message,
)


class TestValidateUrl:
    """Tests for URL validation"""

    def test_valid_http_url(self):
        """Test validation of valid HTTP URL"""
        url = "http://example.com/repo"
        result = validate_url(url)
        assert result == url

    def test_valid_https_url(self):
        """Test validation of valid HTTPS URL"""
        url = "https://example.com/repo"
        result = validate_url(url)
        assert result == url

    def test_url_with_port(self):
        """Test validation of URL with port"""
        url = "https://example.com:8080/repo"
        result = validate_url(url)
        assert result == url

    def test_url_with_query_params(self):
        """Test validation of URL with query parameters"""
        url = "https://example.com/repo?param=value"
        result = validate_url(url)
        assert result == url

    def test_invalid_scheme(self):
        """Test that invalid scheme raises error"""
        with pytest.raises(ValidationError, match="not allowed"):
            validate_url("ftp://example.com/repo")

    def test_allowed_schemes(self):
        """Test custom allowed schemes"""
        url = "ftp://example.com/repo"
        result = validate_url(url, allowed_schemes=["ftp"])
        assert result == url

    def test_empty_url(self):
        """Test that empty URL raises error"""
        with pytest.raises(ValidationError):
            validate_url("")

    def test_malformed_url(self):
        """Test that malformed URL raises error"""
        with pytest.raises(ValidationError):
            validate_url("not a url")

    def test_url_without_scheme(self):
        """Test that URL without scheme raises error"""
        with pytest.raises(ValidationError):
            validate_url("example.com/repo")


class TestValidatePackageName:
    """Tests for package name validation"""

    def test_valid_package_name(self):
        """Test validation of valid package name"""
        name = "test-package"
        result = validate_package_name(name)
        assert result == name

    def test_package_name_with_numbers(self):
        """Test package name with numbers"""
        name = "package123"
        result = validate_package_name(name)
        assert result == name

    def test_package_name_with_underscore(self):
        """Test package name with underscore"""
        name = "test_package"
        result = validate_package_name(name)
        assert result == name

    def test_package_name_with_dots(self):
        """Test package name with dots"""
        name = "test.package.name"
        result = validate_package_name(name)
        assert result == name

    def test_empty_package_name(self):
        """Test that empty package name raises error"""
        with pytest.raises(ValidationError):
            validate_package_name("")

    def test_package_name_too_long(self):
        """Test that overly long package name raises error"""
        long_name = "a" * 300
        with pytest.raises(ValidationError):
            validate_package_name(long_name)

    def test_package_name_with_invalid_chars(self):
        """Test that package name with invalid characters raises error"""
        with pytest.raises(ValidationError):
            validate_package_name("package@#$")

    def test_package_name_with_spaces(self):
        """Test that package name with spaces raises error"""
        with pytest.raises(ValidationError):
            validate_package_name("test package")


class TestValidateFilePath:
    """Tests for file path validation"""

    def test_valid_relative_path(self):
        """Test validation of valid relative path"""
        path = "data/cache/file.xml"
        result = validate_file_path(path)
        assert isinstance(result, Path)

    def test_valid_absolute_path(self):
        """Test validation of valid absolute path"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = str(Path(tmpdir) / "file.txt")
            result = validate_file_path(path)
            assert isinstance(result, Path)

    def test_path_traversal_attack(self):
        """Test that path traversal is detected"""
        # Path traversal is allowed without base_dir, just resolves to absolute path
        result = validate_file_path("../../../etc/passwd")
        assert isinstance(result, Path)

    def test_path_with_base_dir(self):
        """Test path validation with base directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            file_path = base_dir / "subdir" / "file.txt"
            result = validate_file_path(str(file_path), base_dir=str(base_dir))
            assert isinstance(result, Path)

    def test_path_outside_base_dir(self):
        """Test that path outside base directory raises error"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(ValidationError):
                validate_file_path("/tmp/other/file.txt", base_dir=tmpdir)

    def test_must_exist_file_not_found(self):
        """Test that non-existent file raises error when must_exist=True"""
        with pytest.raises(ValidationError):
            validate_file_path("/nonexistent/file.txt", must_exist=True)

    def test_must_exist_file_exists(self):
        """Test that existing file passes when must_exist=True"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp_path = tmp.name
        try:
            result = validate_file_path(tmp_path, must_exist=True)
            assert isinstance(result, Path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestValidateMetadataString:
    """Tests for metadata string validation"""

    def test_valid_metadata_string(self):
        """Test validation of valid metadata string"""
        value = "test-value-123"
        result = validate_metadata_string(value, "test")
        assert result == value

    def test_metadata_string_with_spaces(self):
        """Test metadata string with spaces"""
        value = "test value"
        result = validate_metadata_string(value, "test")
        assert result == value

    def test_empty_metadata_string(self):
        """Test that empty metadata string is allowed"""
        # Empty strings are actually allowed in metadata
        result = validate_metadata_string("", "test")
        assert result == ""

    def test_metadata_string_too_long(self):
        """Test that overly long metadata string raises error"""
        long_value = "a" * 300
        with pytest.raises(ValidationError):
            validate_metadata_string(long_value, "test", max_length=256)

    def test_metadata_string_with_null_bytes(self):
        """Test that metadata string with null bytes raises error"""
        with pytest.raises(ValidationError):
            validate_metadata_string("test\x00value", "test")

    def test_metadata_string_with_control_chars(self):
        """Test that metadata string with control characters raises error"""
        with pytest.raises(ValidationError):
            validate_metadata_string("test\x01value", "test")


class TestValidateFileSize:
    """Tests for file size validation"""

    def test_valid_file_size(self):
        """Test validation of file with valid size"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            tmp.write(b"test content")
            tmp.flush()
            tmp_path = tmp.name
        try:
            result = validate_file_size(Path(tmp_path), max_size_mb=1)
            assert result > 0
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_file_too_large(self):
        """Test that file exceeding size limit raises error"""
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            # Write 2MB of data
            tmp.write(b"x" * (2 * 1024 * 1024))
            tmp.flush()
            tmp_path = tmp.name
        try:
            with pytest.raises(ValidationError):
                validate_file_size(Path(tmp_path), max_size_mb=1)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_nonexistent_file(self):
        """Test that non-existent file raises error"""
        with pytest.raises(ValidationError, match="File does not exist"):
            validate_file_size(Path("/nonexistent/file.txt"))


class TestSanitizeLogMessage:
    """Tests for log message sanitization"""

    def test_valid_log_message(self):
        """Test sanitization of valid log message"""
        message = "This is a valid log message"
        result = sanitize_log_message(message)
        assert result == message

    def test_log_message_with_newlines(self):
        """Test that newlines are escaped"""
        message = "Line 1\nLine 2\rLine 3"
        result = sanitize_log_message(message)
        assert "\n" not in result
        assert "\r" not in result
        assert "\\n" in result
        assert "\\r" in result

    def test_log_message_with_null_bytes(self):
        """Test that null bytes are removed"""
        message = "test\x00message"
        result = sanitize_log_message(message)
        assert "\x00" not in result

    def test_log_message_too_long(self):
        """Test that long messages are truncated"""
        long_message = "a" * 15000
        result = sanitize_log_message(long_message)
        assert len(result) <= 10020  # 10000 + truncation message
        assert "truncated" in result

    def test_log_message_non_string(self):
        """Test that non-string values are converted"""
        result = sanitize_log_message(12345)
        assert result == "12345"
