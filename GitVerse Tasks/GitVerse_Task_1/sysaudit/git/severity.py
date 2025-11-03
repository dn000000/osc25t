"""Severity scoring for file changes"""

from typing import Dict, List
import fnmatch


class SeverityScorer:
    """
    Assigns severity levels to file changes based on path patterns.
    
    Classifies changes as HIGH, MEDIUM, or LOW severity based on the
    criticality of the affected files and directories.
    
    Scoring Logic:
    - HIGH: Critical system files that directly impact security and system integrity
      * /etc/sudoers, /etc/shadow, /etc/passwd - Authentication and authorization
      * /etc/ssh/sshd_config, /etc/ssh/* - SSH configuration
      * /etc/pam.d/* - PAM authentication modules
      * /etc/security/* - Security policies
      * /boot/* - Boot configuration and kernel files
      * /etc/systemd/system/* - System service definitions
      
    - MEDIUM: Important configuration files and system binaries
      * /etc/* - General system configuration
      * /usr/local/bin/*, /usr/bin/*, /bin/* - System binaries
      * /usr/local/sbin/*, /usr/sbin/*, /sbin/* - System administration binaries
      * /lib/systemd/* - Systemd libraries
      * /etc/cron.* - Scheduled tasks
      
    - LOW: All other files
      * User files, logs, temporary files, application data
    """
    
    # Critical paths that warrant HIGH severity
    # Format: (pattern, severity)
    CRITICAL_PATTERNS = [
        # Authentication and authorization
        ('/etc/sudoers', 'HIGH'),
        ('/etc/sudoers.d/*', 'HIGH'),
        ('/etc/shadow', 'HIGH'),
        ('/etc/shadow-', 'HIGH'),
        ('/etc/passwd', 'HIGH'),
        ('/etc/passwd-', 'HIGH'),
        ('/etc/group', 'HIGH'),
        ('/etc/gshadow', 'HIGH'),
        
        # SSH configuration
        ('/etc/ssh/sshd_config', 'HIGH'),
        ('/etc/ssh/ssh_config', 'HIGH'),
        ('/etc/ssh/*_key', 'HIGH'),
        ('/etc/ssh/*_key.pub', 'HIGH'),
        
        # PAM authentication
        ('/etc/pam.d/*', 'HIGH'),
        
        # Security policies
        ('/etc/security/*', 'HIGH'),
        ('/etc/selinux/*', 'HIGH'),
        ('/etc/apparmor.d/*', 'HIGH'),
        
        # Boot and kernel
        ('/boot/*', 'HIGH'),
        ('/etc/default/grub', 'HIGH'),
        ('/etc/grub.d/*', 'HIGH'),
        
        # Systemd services
        ('/etc/systemd/system/*', 'HIGH'),
        ('/usr/lib/systemd/system/*', 'HIGH'),
        
        # Firewall and network security
        ('/etc/iptables/*', 'HIGH'),
        ('/etc/nftables.conf', 'HIGH'),
        ('/etc/firewalld/*', 'HIGH'),
        
        # Certificate authorities
        ('/etc/ssl/certs/*', 'HIGH'),
        ('/etc/pki/*', 'HIGH'),
    ]
    
    # Important paths that warrant MEDIUM severity
    MEDIUM_PATTERNS = [
        # General system configuration
        ('/etc/*', 'MEDIUM'),
        
        # System binaries
        ('/usr/local/bin/*', 'MEDIUM'),
        ('/usr/bin/*', 'MEDIUM'),
        ('/bin/*', 'MEDIUM'),
        ('/usr/local/sbin/*', 'MEDIUM'),
        ('/usr/sbin/*', 'MEDIUM'),
        ('/sbin/*', 'MEDIUM'),
        
        # Systemd
        ('/lib/systemd/*', 'MEDIUM'),
        
        # Scheduled tasks
        ('/etc/cron.d/*', 'MEDIUM'),
        ('/etc/cron.daily/*', 'MEDIUM'),
        ('/etc/cron.hourly/*', 'MEDIUM'),
        ('/etc/cron.weekly/*', 'MEDIUM'),
        ('/etc/cron.monthly/*', 'MEDIUM'),
        ('/var/spool/cron/*', 'MEDIUM'),
        
        # System libraries
        ('/lib/*', 'MEDIUM'),
        ('/lib64/*', 'MEDIUM'),
        ('/usr/lib/*', 'MEDIUM'),
        ('/usr/lib64/*', 'MEDIUM'),
    ]
    
    def __init__(self, custom_patterns: Dict[str, str] = None):
        """
        Initialize SeverityScorer with optional custom patterns.
        
        Args:
            custom_patterns: Dictionary mapping file patterns to severity levels
                           Format: {'/path/pattern': 'HIGH|MEDIUM|LOW'}
        """
        self.custom_patterns = custom_patterns or {}
    
    def score(self, path: str) -> str:
        """
        Assign severity level to a file path.
        
        Evaluates the file path against known patterns to determine
        the severity of changes to that file.
        
        Args:
            path: File path to score (absolute or relative)
            
        Returns:
            Severity level: 'HIGH', 'MEDIUM', or 'LOW'
        """
        # Normalize path to use forward slashes
        normalized_path = path.replace('\\', '/')
        
        # Ensure path starts with / for consistent matching
        if not normalized_path.startswith('/'):
            normalized_path = '/' + normalized_path
        
        # Check custom patterns first (highest priority)
        for pattern, severity in self.custom_patterns.items():
            if self._matches_pattern(normalized_path, pattern):
                return severity
        
        # Check critical patterns (HIGH severity)
        for pattern, severity in self.CRITICAL_PATTERNS:
            if self._matches_pattern(normalized_path, pattern):
                return severity
        
        # Check medium patterns (MEDIUM severity)
        for pattern, severity in self.MEDIUM_PATTERNS:
            if self._matches_pattern(normalized_path, pattern):
                return severity
        
        # Default to LOW severity
        return 'LOW'
    
    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """
        Check if a path matches a pattern.
        
        Supports exact matches and glob patterns with wildcards.
        
        Args:
            path: File path to check
            pattern: Pattern to match against (supports * and ? wildcards)
            
        Returns:
            True if path matches pattern, False otherwise
        """
        # Exact match
        if path == pattern:
            return True
        
        # Glob pattern match
        if '*' in pattern or '?' in pattern:
            return fnmatch.fnmatch(path, pattern)
        
        # Prefix match for directory patterns
        if pattern.endswith('/'):
            return path.startswith(pattern)
        
        return False
    
    def score_multiple(self, paths: List[str]) -> Dict[str, str]:
        """
        Score multiple file paths at once.
        
        Args:
            paths: List of file paths to score
            
        Returns:
            Dictionary mapping each path to its severity level
        """
        return {path: self.score(path) for path in paths}
    
    def get_high_severity_paths(self, paths: List[str]) -> List[str]:
        """
        Filter paths to only those with HIGH severity.
        
        Args:
            paths: List of file paths to filter
            
        Returns:
            List of paths with HIGH severity
        """
        return [path for path in paths if self.score(path) == 'HIGH']
    
    def get_paths_by_severity(self, paths: List[str]) -> Dict[str, List[str]]:
        """
        Group paths by their severity level.
        
        Args:
            paths: List of file paths to group
            
        Returns:
            Dictionary with severity levels as keys and lists of paths as values
        """
        result = {
            'HIGH': [],
            'MEDIUM': [],
            'LOW': []
        }
        
        for path in paths:
            severity = self.score(path)
            result[severity].append(path)
        
        return result
    
    def add_custom_pattern(self, pattern: str, severity: str) -> None:
        """
        Add a custom pattern for severity scoring.
        
        Args:
            pattern: File path pattern (supports wildcards)
            severity: Severity level ('HIGH', 'MEDIUM', or 'LOW')
            
        Raises:
            ValueError: If severity is not valid
        """
        valid_severities = {'HIGH', 'MEDIUM', 'LOW'}
        if severity not in valid_severities:
            raise ValueError(f"Invalid severity: {severity}. Must be one of {valid_severities}")
        
        self.custom_patterns[pattern] = severity
    
    def remove_custom_pattern(self, pattern: str) -> None:
        """
        Remove a custom pattern.
        
        Args:
            pattern: File path pattern to remove
        """
        self.custom_patterns.pop(pattern, None)
    
    def get_pattern_explanation(self, path: str) -> str:
        """
        Get an explanation of why a path received its severity score.
        
        Args:
            path: File path to explain
            
        Returns:
            Human-readable explanation of the severity score
        """
        severity = self.score(path)
        normalized_path = path.replace('\\', '/')
        if not normalized_path.startswith('/'):
            normalized_path = '/' + normalized_path
        
        # Find matching pattern
        for pattern, sev in self.custom_patterns.items():
            if self._matches_pattern(normalized_path, pattern):
                return f"Severity: {severity} - Matches custom pattern '{pattern}'"
        
        for pattern, sev in self.CRITICAL_PATTERNS:
            if self._matches_pattern(normalized_path, pattern):
                return f"Severity: {severity} - Matches critical pattern '{pattern}' (authentication, security, or boot files)"
        
        for pattern, sev in self.MEDIUM_PATTERNS:
            if self._matches_pattern(normalized_path, pattern):
                return f"Severity: {severity} - Matches medium pattern '{pattern}' (system configuration or binaries)"
        
        return f"Severity: {severity} - Default severity for non-system files"
