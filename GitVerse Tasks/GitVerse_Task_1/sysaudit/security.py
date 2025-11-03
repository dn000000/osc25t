"""
Security utilities for input validation and sanitization.
"""

import os
import re
from pathlib import Path
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class SecurityError(Exception):
    """Base exception for security-related errors"""
    pass


class PathTraversalError(SecurityError):
    """Exception raised when path traversal is detected"""
    pass


class InputValidationError(SecurityError):
    """Exception raised when input validation fails"""
    pass


def sanitize_path(path: str, base_path: Optional[str] = None) -> str:
    """
    Sanitize a file path to prevent path traversal attacks.
    
    Args:
        path: Path to sanitize
        base_path: Optional base path to restrict access to
        
    Returns:
        Sanitized path
        
    Raises:
        PathTraversalError: If path traversal is detected
        InputValidationError: If path is invalid
    """
    if not path:
        raise InputValidationError("Path cannot be empty")
    
    # Remove null bytes
    if '\x00' in path:
        raise InputValidationError("Path contains null bytes")
    
    # Normalize path
    try:
        normalized = os.path.normpath(path)
    except Exception as e:
        raise InputValidationError(f"Invalid path: {e}")
    
    # Check for path traversal attempts
    if '..' in Path(normalized).parts:
        logger.warning(f"Path traversal attempt detected: {path}")
        raise PathTraversalError(f"Path traversal not allowed: {path}")
    
    # If base_path is provided, ensure path is within it
    if base_path:
        try:
            base = Path(base_path).resolve()
            target = Path(normalized).resolve()
            
            # Check if target is within base
            try:
                target.relative_to(base)
            except ValueError:
                logger.warning(f"Path outside base directory: {path} (base: {base_path})")
                raise PathTraversalError(f"Path must be within {base_path}")
        except Exception as e:
            if isinstance(e, PathTraversalError):
                raise
            raise InputValidationError(f"Path validation failed: {e}")
    
    return normalized


def sanitize_pattern(pattern: str) -> str:
    """
    Sanitize a glob pattern to prevent malicious patterns.
    
    Args:
        pattern: Glob pattern to sanitize
        
    Returns:
        Sanitized pattern
        
    Raises:
        InputValidationError: If pattern is invalid
    """
    if not pattern:
        raise InputValidationError("Pattern cannot be empty")
    
    # Remove null bytes
    if '\x00' in pattern:
        raise InputValidationError("Pattern contains null bytes")
    
    # Limit pattern length to prevent DoS
    if len(pattern) > 1000:
        raise InputValidationError("Pattern too long (max 1000 characters)")
    
    # Check for excessive wildcards (potential DoS)
    wildcard_count = pattern.count('*') + pattern.count('?')
    if wildcard_count > 50:
        logger.warning(f"Pattern has excessive wildcards: {pattern}")
        raise InputValidationError("Pattern has too many wildcards (max 50)")
    
    # Check for unbalanced brackets
    if pattern.count('[') != pattern.count(']'):
        raise InputValidationError("Pattern has unbalanced brackets")
    
    if pattern.count('(') != pattern.count(')'):
        raise InputValidationError("Pattern has unbalanced parentheses")
    
    return pattern


def sanitize_commit_message(message: str) -> str:
    """
    Sanitize a commit message to prevent injection attacks.
    
    Args:
        message: Commit message to sanitize
        
    Returns:
        Sanitized message
        
    Raises:
        InputValidationError: If message is invalid
    """
    if not message:
        raise InputValidationError("Commit message cannot be empty")
    
    # Remove null bytes
    if '\x00' in message:
        raise InputValidationError("Commit message contains null bytes")
    
    # Limit message length
    if len(message) > 10000:
        logger.warning("Commit message truncated (too long)")
        message = message[:10000] + "\n[truncated]"
    
    # Remove control characters except newlines and tabs
    sanitized = ''.join(
        char for char in message
        if char in '\n\t' or not char.isspace() or char == ' '
    )
    
    return sanitized


def sanitize_url(url: str) -> str:
    """
    Sanitize a URL to prevent SSRF and other attacks.
    
    Args:
        url: URL to sanitize
        
    Returns:
        Sanitized URL
        
    Raises:
        InputValidationError: If URL is invalid
    """
    if not url:
        raise InputValidationError("URL cannot be empty")
    
    # Remove null bytes
    if '\x00' in url:
        raise InputValidationError("URL contains null bytes")
    
    # Check URL scheme
    if not url.startswith(('http://', 'https://')):
        raise InputValidationError("URL must use http:// or https://")
    
    # Warn about non-HTTPS URLs
    if url.startswith('http://'):
        logger.warning(f"Non-HTTPS URL used: {url}")
    
    # Check for localhost/internal IPs (SSRF prevention)
    internal_patterns = [
        r'localhost',
        r'127\.0\.0\.',
        r'0\.0\.0\.0',
        r'10\.\d+\.\d+\.\d+',
        r'172\.(1[6-9]|2[0-9]|3[0-1])\.\d+\.\d+',
        r'192\.168\.\d+\.\d+',
        r'\[::1\]',
        r'\[::ffff:127\.0\.0\.1\]',
    ]
    
    for pattern in internal_patterns:
        if re.search(pattern, url, re.IGNORECASE):
            logger.warning(f"Internal/localhost URL detected: {url}")
            raise InputValidationError("URLs to internal/localhost addresses not allowed")
    
    return url


def validate_file_permissions(path: str, max_permissions: int = 0o644) -> bool:
    """
    Validate that a file has appropriate permissions.
    
    Args:
        path: Path to file
        max_permissions: Maximum allowed permissions (default: 0o644)
        
    Returns:
        True if permissions are acceptable, False otherwise
    """
    try:
        stat_info = os.stat(path)
        mode = stat_info.st_mode & 0o777
        
        # Check if permissions exceed maximum
        if mode > max_permissions:
            logger.warning(f"File has excessive permissions: {path} ({oct(mode)})")
            return False
        
        # Check for world-writable
        if mode & 0o002:
            logger.warning(f"File is world-writable: {path}")
            return False
        
        return True
    except Exception as e:
        logger.error(f"Failed to check permissions for {path}: {e}")
        return False


def validate_config_value(value: any, value_type: type, min_value: Optional[any] = None, 
                         max_value: Optional[any] = None) -> bool:
    """
    Validate a configuration value.
    
    Args:
        value: Value to validate
        value_type: Expected type
        min_value: Minimum allowed value (for numeric types)
        max_value: Maximum allowed value (for numeric types)
        
    Returns:
        True if valid, False otherwise
    """
    # Check type
    if not isinstance(value, value_type):
        logger.warning(f"Config value has wrong type: expected {value_type}, got {type(value)}")
        return False
    
    # Check range for numeric types
    if isinstance(value, (int, float)):
        if min_value is not None and value < min_value:
            logger.warning(f"Config value below minimum: {value} < {min_value}")
            return False
        if max_value is not None and value > max_value:
            logger.warning(f"Config value above maximum: {value} > {max_value}")
            return False
    
    # Check length for strings
    if isinstance(value, str):
        if len(value) > 10000:
            logger.warning(f"Config string value too long: {len(value)} characters")
            return False
    
    return True


def is_safe_filename(filename: str) -> bool:
    """
    Check if a filename is safe (no special characters that could cause issues).
    
    Args:
        filename: Filename to check
        
    Returns:
        True if safe, False otherwise
    """
    # Check for null bytes
    if '\x00' in filename:
        return False
    
    # Check for path separators
    if '/' in filename or '\\' in filename:
        return False
    
    # Check for parent directory references
    if filename in ('.', '..'):
        return False
    
    # Check for control characters
    if any(ord(c) < 32 for c in filename):
        return False
    
    return True


def secure_delete(path: str) -> bool:
    """
    Securely delete a file by overwriting before deletion.
    
    Args:
        path: Path to file to delete
        
    Returns:
        True if successful, False otherwise
    """
    try:
        if not os.path.exists(path):
            return True
        
        if os.path.isfile(path):
            # Get file size
            size = os.path.getsize(path)
            
            # Overwrite with zeros (simple secure delete)
            with open(path, 'wb') as f:
                f.write(b'\x00' * size)
            
            # Delete file
            os.remove(path)
            return True
        else:
            logger.warning(f"Path is not a file: {path}")
            return False
    except Exception as e:
        logger.error(f"Failed to securely delete {path}: {e}")
        return False
