"""Event filtering system for file monitoring"""

import fnmatch
import re
from pathlib import Path
from typing import List, Set, Optional, Pattern
from functools import lru_cache
import logging

logger = logging.getLogger(__name__)


class FilterManager:
    """
    Manages filtering of file system events based on blacklist/whitelist patterns.
    
    Supports glob patterns for flexible file matching. Default ignore patterns
    are applied automatically to filter out temporary files, logs, and other
    noise from monitoring.
    """
    
    # Default patterns to ignore (Requirements 3.1)
    DEFAULT_IGNORE_PATTERNS = [
        '*.tmp',
        '*.swp',
        '*.swo',
        '*~',
        '*.bak',
        '*.backup',
        '*.log',
        '*.log.*',
        '*.pyc',
        '*.pyo',
        '__pycache__/*',
        '*.egg-info/*',
        '.git/*',
        '.gitignore',
        '.*.sw?',
        '.vscode/*',
        '.idea/*',
        '*.sublime-*',
        '.DS_Store',
        'Thumbs.db',
        '*.lock',
        '.*.lock',
        'node_modules/*',
        '.npm/*',
        '.cache/*',
        '*.o',
        '*.so',
        '*.a',
        '*.out',
        'dist/*',
        'build/*',
        '/tmp/*',
        '/var/tmp/*',
        '/var/cache/*',
    ]
    
    def __init__(
        self,
        blacklist_file: Optional[str] = None,
        whitelist_file: Optional[str] = None,
        use_defaults: bool = True
    ):
        """
        Initialize FilterManager with optional blacklist/whitelist files.
        
        Args:
            blacklist_file: Path to file containing blacklist patterns (one per line)
            whitelist_file: Path to file containing whitelist patterns (one per line)
            use_defaults: Whether to include default ignore patterns (default: True)
        """
        self.blacklist: Set[str] = set()
        self.whitelist: Set[str] = set()
        
        # Load default ignore patterns (Requirement 3.1)
        if use_defaults:
            self.blacklist.update(self.DEFAULT_IGNORE_PATTERNS)
            logger.debug(f"Loaded {len(self.DEFAULT_IGNORE_PATTERNS)} default ignore patterns")
        
        # Load blacklist from file (Requirement 3.3, 3.4)
        if blacklist_file:
            self._load_patterns_from_file(blacklist_file, self.blacklist)
            logger.info(f"Loaded blacklist from {blacklist_file}: {len(self.blacklist)} total patterns")
        
        # Load whitelist from file (Requirement 3.3, 3.5)
        if whitelist_file:
            self._load_patterns_from_file(whitelist_file, self.whitelist)
            logger.info(f"Loaded whitelist from {whitelist_file}: {len(self.whitelist)} patterns")
    
    def _load_patterns_from_file(self, filepath: str, pattern_set: Set[str]) -> None:
        """
        Load patterns from a file into the given set.
        
        Args:
            filepath: Path to the pattern file
            pattern_set: Set to add patterns to
            
        Raises:
            FileNotFoundError: If the file doesn't exist
        """
        path = Path(filepath)
        
        if not path.exists():
            logger.warning(f"Pattern file not found: {filepath}")
            raise FileNotFoundError(f"Pattern file not found: {filepath}")
        
        if not path.is_file():
            logger.warning(f"Pattern path is not a file: {filepath}")
            raise ValueError(f"Pattern path is not a file: {filepath}")
        
        try:
            with open(path, 'r') as f:
                for line in f:
                    # Strip whitespace and skip empty lines and comments
                    line = line.strip()
                    if line and not line.startswith('#'):
                        pattern_set.add(line)
                        logger.debug(f"Added pattern: {line}")
        except Exception as e:
            logger.error(f"Error reading pattern file {filepath}: {e}")
            raise
    
    def should_ignore(self, path: str) -> bool:
        """
        Check if a file path should be ignored based on filter rules.
        
        Filter logic (Requirements 3.4, 3.5):
        1. If whitelist exists and path doesn't match any whitelist pattern -> ignore
        2. If path matches any blacklist pattern -> ignore
        3. Otherwise -> don't ignore
        
        Args:
            path: File path to check
            
        Returns:
            True if the path should be ignored, False otherwise
        """
        # Normalize path for consistent matching
        normalized_path = self._normalize_path(path)
        
        # If whitelist exists, only allow whitelisted files (Requirement 3.5)
        if self.whitelist:
            if not self._matches_any(normalized_path, self.whitelist):
                logger.debug(f"Path not in whitelist, ignoring: {path}")
                return True
        
        # Check blacklist (Requirement 3.4)
        if self._matches_any(normalized_path, self.blacklist):
            logger.debug(f"Path matches blacklist, ignoring: {path}")
            return True
        
        # Path passes all filters
        logger.debug(f"Path passes filters: {path}")
        return False
    
    @lru_cache(maxsize=1024)
    def _matches_any_cached(self, path: str, patterns_tuple: tuple) -> bool:
        """
        Cached version of pattern matching for performance.
        Uses tuple instead of set for hashability.
        
        Args:
            path: File path to check
            patterns_tuple: Tuple of glob patterns
            
        Returns:
            True if path matches any pattern, False otherwise
        """
        for pattern in patterns_tuple:
            if self._matches_pattern(path, pattern):
                return True
        return False
    
    def _matches_any(self, path: str, patterns: Set[str]) -> bool:
        """
        Check if path matches any pattern in the set.
        
        Supports glob patterns with * and ? wildcards (Requirement 3.4, 3.5).
        Uses caching for improved performance.
        
        Args:
            path: File path to check
            patterns: Set of glob patterns
            
        Returns:
            True if path matches any pattern, False otherwise
        """
        # Convert set to tuple for caching
        patterns_tuple = tuple(sorted(patterns))
        return self._matches_any_cached(path, patterns_tuple)
    
    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """
        Check if a path matches a glob pattern.
        
        Supports:
        - * matches any sequence of characters
        - ? matches any single character
        - Patterns ending with /* match directory contents
        
        Args:
            path: File path to check
            pattern: Glob pattern
            
        Returns:
            True if path matches pattern, False otherwise
        """
        # Use fnmatch for glob pattern matching
        if fnmatch.fnmatch(path, pattern):
            return True
        
        # Also check if just the filename matches (for patterns without path)
        filename = Path(path).name
        if fnmatch.fnmatch(filename, pattern):
            return True
        
        # Check if path is within a directory pattern (e.g., ".git/*")
        if pattern.endswith('/*'):
            dir_pattern = pattern[:-2]  # Remove /*
            if path.startswith(dir_pattern + '/') or path.startswith(dir_pattern + '\\'):
                return True
            # Also check normalized path
            if '/' in path and path.split('/')[0] == dir_pattern.lstrip('/'):
                return True
        
        return False
    
    def _normalize_path(self, path: str) -> str:
        """
        Normalize path for consistent matching across platforms.
        
        Args:
            path: File path to normalize
            
        Returns:
            Normalized path string
        """
        # Convert backslashes to forward slashes for consistent matching
        normalized = path.replace('\\', '/')
        
        # Remove leading ./ if present
        if normalized.startswith('./'):
            normalized = normalized[2:]
        
        return normalized
    
    def add_blacklist_pattern(self, pattern: str) -> None:
        """
        Add a pattern to the blacklist at runtime.
        
        Args:
            pattern: Glob pattern to add
        """
        self.blacklist.add(pattern)
        logger.debug(f"Added blacklist pattern: {pattern}")
    
    def add_whitelist_pattern(self, pattern: str) -> None:
        """
        Add a pattern to the whitelist at runtime.
        
        Args:
            pattern: Glob pattern to add
        """
        self.whitelist.add(pattern)
        logger.debug(f"Added whitelist pattern: {pattern}")
    
    def remove_blacklist_pattern(self, pattern: str) -> None:
        """
        Remove a pattern from the blacklist.
        
        Args:
            pattern: Glob pattern to remove
        """
        self.blacklist.discard(pattern)
        logger.debug(f"Removed blacklist pattern: {pattern}")
    
    def remove_whitelist_pattern(self, pattern: str) -> None:
        """
        Remove a pattern from the whitelist.
        
        Args:
            pattern: Glob pattern to remove
        """
        self.whitelist.discard(pattern)
        logger.debug(f"Removed whitelist pattern: {pattern}")
    
    def get_blacklist_patterns(self) -> List[str]:
        """
        Get all blacklist patterns.
        
        Returns:
            List of blacklist patterns
        """
        return sorted(list(self.blacklist))
    
    def get_whitelist_patterns(self) -> List[str]:
        """
        Get all whitelist patterns.
        
        Returns:
            List of whitelist patterns
        """
        return sorted(list(self.whitelist))
    
    def clear_blacklist(self, keep_defaults: bool = True) -> None:
        """
        Clear all blacklist patterns.
        
        Args:
            keep_defaults: If True, keep default ignore patterns
        """
        self.blacklist.clear()
        if keep_defaults:
            self.blacklist.update(self.DEFAULT_IGNORE_PATTERNS)
        logger.info("Cleared blacklist patterns")
    
    def clear_whitelist(self) -> None:
        """Clear all whitelist patterns."""
        self.whitelist.clear()
        logger.info("Cleared whitelist patterns")
