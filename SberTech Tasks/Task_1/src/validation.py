"""
Input validation utilities for security.

This module provides validation functions to ensure all external input
is properly validated before processing, preventing security vulnerabilities
like path traversal, injection attacks, and malformed data processing.
"""

import re
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


class ValidationError(Exception):
    """Raised when input validation fails"""

    pass


def validate_url(url: str, allowed_schemes: Optional[list] = None) -> str:
    """
    Validate and sanitize a URL.

    Args:
        url: URL string to validate
        allowed_schemes: List of allowed URL schemes (default: ['http', 'https'])

    Returns:
        Validated URL string

    Raises:
        ValidationError: If URL is invalid or uses disallowed scheme
    """
    if not url or not isinstance(url, str):
        raise ValidationError("URL must be a non-empty string")

    # Remove leading/trailing whitespace
    url = url.strip()

    if not url:
        raise ValidationError("URL cannot be empty or whitespace only")

    # Check length to prevent DoS
    if len(url) > 2048:
        raise ValidationError("URL exceeds maximum length of 2048 characters")

    # Parse URL
    try:
        parsed = urlparse(url)
    except Exception as e:
        raise ValidationError(f"Invalid URL format: {e}")

    # Validate scheme
    if allowed_schemes is None:
        allowed_schemes = ["http", "https"]

    if not parsed.scheme:
        raise ValidationError("URL must include a scheme (http:// or https://)")

    if parsed.scheme.lower() not in allowed_schemes:
        raise ValidationError(
            f"URL scheme '{parsed.scheme}' not allowed. "
            f"Allowed schemes: {', '.join(allowed_schemes)}"
        )

    # Validate netloc (hostname)
    if not parsed.netloc:
        raise ValidationError("URL must include a hostname")

    # Check for suspicious patterns
    suspicious_patterns = [
        r"\.\./",  # Path traversal
        r"file://",  # Local file access
        r"javascript:",  # JavaScript injection
        r"data:",  # Data URLs
    ]

    url_lower = url.lower()
    for pattern in suspicious_patterns:
        if re.search(pattern, url_lower):
            raise ValidationError(f"URL contains suspicious pattern: {pattern}")

    return url


def validate_package_name(name: str) -> str:
    """
    Validate and sanitize a package name.

    Args:
        name: Package name to validate

    Returns:
        Validated package name

    Raises:
        ValidationError: If package name is invalid
    """
    if not name or not isinstance(name, str):
        raise ValidationError("Package name must be a non-empty string")

    # Remove leading/trailing whitespace
    name = name.strip()

    if not name:
        raise ValidationError("Package name cannot be empty or whitespace only")

    # Check length
    if len(name) > 256:
        raise ValidationError("Package name exceeds maximum length of 256 characters")

    # Validate characters - allow alphanumeric, dash, underscore, dot, plus
    # This matches typical RPM package naming conventions
    if not re.match(r"^[a-zA-Z0-9._+-]+$", name):
        raise ValidationError(
            "Package name contains invalid characters. "
            "Only alphanumeric, dash, underscore, dot, and plus are allowed"
        )

    # Prevent path traversal attempts
    if ".." in name or "/" in name or "\\" in name:
        raise ValidationError("Package name cannot contain path separators or '..'")

    return name


def validate_file_path(
    file_path: str, base_dir: Optional[str] = None, must_exist: bool = False
) -> Path:
    """
    Validate a file path to prevent directory traversal attacks.

    Args:
        file_path: File path to validate
        base_dir: Base directory that the path must be within (optional)
        must_exist: If True, verify that the path exists

    Returns:
        Validated Path object

    Raises:
        ValidationError: If path is invalid or outside base_dir
    """
    if not file_path or not isinstance(file_path, str):
        raise ValidationError("File path must be a non-empty string")

    # Remove leading/trailing whitespace
    file_path = file_path.strip()

    if not file_path:
        raise ValidationError("File path cannot be empty or whitespace only")

    # Check length
    if len(file_path) > 4096:
        raise ValidationError("File path exceeds maximum length of 4096 characters")

    # Convert to Path object
    try:
        path = Path(file_path)
    except Exception as e:
        raise ValidationError(f"Invalid file path: {e}")

    # Resolve to absolute path to detect traversal attempts
    try:
        resolved_path = path.resolve()
    except Exception as e:
        raise ValidationError(f"Cannot resolve file path: {e}")

    # If base_dir specified, ensure path is within it
    if base_dir:
        try:
            base_path = Path(base_dir).resolve()

            # Check if resolved path is within base directory
            try:
                resolved_path.relative_to(base_path)
            except ValueError:
                raise ValidationError(
                    f"File path '{file_path}' is outside allowed directory '{base_dir}'"
                )
        except Exception as e:
            if isinstance(e, ValidationError):
                raise
            raise ValidationError(f"Invalid base directory: {e}")

    # Check if path must exist
    if must_exist and not resolved_path.exists():
        raise ValidationError(f"File path does not exist: {file_path}")

    return resolved_path


def validate_metadata_string(value: str, field_name: str, max_length: int = 1024) -> str:
    """
    Validate and sanitize metadata string values.

    Args:
        value: String value to validate
        field_name: Name of the field (for error messages)
        max_length: Maximum allowed length

    Returns:
        Validated string

    Raises:
        ValidationError: If value is invalid
    """
    if not isinstance(value, str):
        raise ValidationError(f"{field_name} must be a string")

    # Check length
    if len(value) > max_length:
        raise ValidationError(f"{field_name} exceeds maximum length of {max_length} characters")

    # Check for null bytes (can cause issues in C libraries)
    if "\x00" in value:
        raise ValidationError(f"{field_name} contains null bytes")

    # Check for control characters (except common whitespace)
    control_chars = set(chr(i) for i in range(32)) - {"\t", "\n", "\r"}
    if any(c in value for c in control_chars):
        raise ValidationError(f"{field_name} contains invalid control characters")

    return value


def validate_file_size(file_path: Path, max_size_mb: int = 100) -> int:
    """
    Validate file size to prevent DoS attacks.

    Args:
        file_path: Path to file
        max_size_mb: Maximum allowed file size in megabytes

    Returns:
        File size in bytes

    Raises:
        ValidationError: If file is too large or doesn't exist
    """
    if not file_path.exists():
        raise ValidationError(f"File does not exist: {file_path}")

    if not file_path.is_file():
        raise ValidationError(f"Path is not a file: {file_path}")

    try:
        file_size = file_path.stat().st_size
    except Exception as e:
        raise ValidationError(f"Cannot get file size: {e}")

    max_size_bytes = max_size_mb * 1024 * 1024

    if file_size > max_size_bytes:
        raise ValidationError(
            f"File size ({file_size / 1024 / 1024:.1f} MB) exceeds "
            f"maximum allowed size ({max_size_mb} MB)"
        )

    return file_size


def sanitize_log_message(message: str) -> str:
    """
    Sanitize log messages to prevent log injection attacks.

    Args:
        message: Log message to sanitize

    Returns:
        Sanitized message
    """
    if not isinstance(message, str):
        message = str(message)

    # Replace newlines and carriage returns to prevent log injection
    message = message.replace("\n", "\\n").replace("\r", "\\r")

    # Remove null bytes
    message = message.replace("\x00", "")

    # Limit length
    if len(message) > 10000:
        message = message[:10000] + "... (truncated)"

    return message
