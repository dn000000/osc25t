"""World-writable file detection rule"""

import os
import stat
from typing import Optional
from sysaudit.models import ComplianceIssue
from sysaudit.compliance.rules import ComplianceRule


class WorldWritableRule(ComplianceRule):
    """Detects world-writable files in critical directories"""
    
    CRITICAL_DIRECTORIES = [
        '/etc',
        '/usr/local/bin',
        '/usr/bin',
        '/bin',
        '/sbin',
        '/usr/sbin',
        '/usr/local/sbin',
        '/root',
        '/boot',
    ]
    
    @property
    def rule_name(self) -> str:
        return "world-writable"
    
    @property
    def description(self) -> str:
        return "Detects files that are writable by all users (world-writable)"
    
    def applies_to(self, path: str) -> bool:
        """
        Check if this rule applies to the given path
        
        Args:
            path: File path to check
            
        Returns:
            True if path is in a critical directory
        """
        # Check if path starts with any critical directory
        for critical_dir in self.CRITICAL_DIRECTORIES:
            if path.startswith(critical_dir):
                return True
        return False
    
    def check(self, path: str) -> Optional[ComplianceIssue]:
        """
        Check if file is world-writable
        
        Args:
            path: File path to check
            
        Returns:
            ComplianceIssue if file is world-writable, None otherwise
        """
        try:
            stat_info = os.stat(path)
            mode = stat_info.st_mode
            
            # Check if world-writable (others have write permission)
            # stat.S_IWOTH is the bit for "other write"
            if mode & stat.S_IWOTH:
                return ComplianceIssue(
                    severity='HIGH',
                    rule=self.rule_name,
                    path=path,
                    description=f'File is world-writable (mode: {oct(mode)})',
                    recommendation='Remove write permission for others: chmod o-w ' + path
                )
        except (OSError, PermissionError) as e:
            # If we can't stat the file, skip it
            pass
        
        return None
