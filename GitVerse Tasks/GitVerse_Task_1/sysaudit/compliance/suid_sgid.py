"""SUID/SGID binary detection rule"""

import os
import stat
from typing import Optional, Set
from sysaudit.models import ComplianceIssue
from sysaudit.compliance.rules import ComplianceRule


class SUIDSGIDRule(ComplianceRule):
    """Detects unexpected SUID/SGID binaries"""
    
    # Known legitimate SUID/SGID binaries
    EXPECTED_SUID_FILES: Set[str] = {
        '/usr/bin/sudo',
        '/usr/bin/su',
        '/usr/bin/passwd',
        '/usr/bin/chsh',
        '/usr/bin/chfn',
        '/usr/bin/gpasswd',
        '/usr/bin/newgrp',
        '/usr/bin/mount',
        '/usr/bin/umount',
        '/usr/bin/pkexec',
        '/usr/lib/dbus-1.0/dbus-daemon-launch-helper',
        '/usr/lib/openssh/ssh-keysign',
        '/bin/su',
        '/bin/mount',
        '/bin/umount',
        '/bin/ping',
        '/sbin/mount.nfs',
        '/sbin/unix_chkpwd',
    }
    
    @property
    def rule_name(self) -> str:
        return "unexpected-suid-sgid"
    
    @property
    def description(self) -> str:
        return "Detects SUID/SGID binaries in unexpected locations"
    
    def applies_to(self, path: str) -> bool:
        """
        This rule applies to all executable files
        
        Args:
            path: File path to check
            
        Returns:
            True (applies to all files)
        """
        return True
    
    def check(self, path: str) -> Optional[ComplianceIssue]:
        """
        Check if file has unexpected SUID/SGID bits set
        
        Args:
            path: File path to check
            
        Returns:
            ComplianceIssue if unexpected SUID/SGID found, None otherwise
        """
        try:
            stat_info = os.stat(path)
            mode = stat_info.st_mode
            
            # Check for SUID or SGID bits
            has_suid = bool(mode & stat.S_ISUID)
            has_sgid = bool(mode & stat.S_ISGID)
            
            if not (has_suid or has_sgid):
                return None
            
            # Check if this is an expected SUID/SGID file
            if path in self.EXPECTED_SUID_FILES:
                return None
            
            # Determine which bits are set
            bits = []
            if has_suid:
                bits.append('SUID')
            if has_sgid:
                bits.append('SGID')
            bits_str = '/'.join(bits)
            
            return ComplianceIssue(
                severity='HIGH',
                rule=self.rule_name,
                path=path,
                description=f'Unexpected {bits_str} binary found (mode: {oct(mode)})',
                recommendation=f'Review if {bits_str} is necessary. Remove with: chmod u-s,g-s ' + path
            )
            
        except (OSError, PermissionError) as e:
            # If we can't stat the file, skip it
            pass
        
        return None
