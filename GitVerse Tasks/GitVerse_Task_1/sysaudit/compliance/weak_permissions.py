"""Weak permissions detection rule for sensitive files"""

import os
import stat
from typing import Optional, Dict
from sysaudit.models import ComplianceIssue
from sysaudit.compliance.rules import ComplianceRule


class WeakPermissionsRule(ComplianceRule):
    """Detects weak permissions on sensitive files"""
    
    # Sensitive files and their expected maximum permissions
    # Format: path -> (max_mode, description)
    SENSITIVE_FILES: Dict[str, tuple] = {
        '/etc/shadow': (0o600, 'shadow password file'),
        '/etc/gshadow': (0o600, 'group shadow file'),
        '/etc/ssh/sshd_config': (0o644, 'SSH daemon configuration'),
        '/etc/ssh/ssh_host_rsa_key': (0o600, 'SSH host RSA private key'),
        '/etc/ssh/ssh_host_dsa_key': (0o600, 'SSH host DSA private key'),
        '/etc/ssh/ssh_host_ecdsa_key': (0o600, 'SSH host ECDSA private key'),
        '/etc/ssh/ssh_host_ed25519_key': (0o600, 'SSH host ED25519 private key'),
        '/root/.ssh/id_rsa': (0o600, 'root SSH private key'),
        '/root/.ssh/id_dsa': (0o600, 'root SSH private key'),
        '/root/.ssh/id_ecdsa': (0o600, 'root SSH private key'),
        '/root/.ssh/id_ed25519': (0o600, 'root SSH private key'),
        '/etc/sudoers': (0o440, 'sudoers configuration'),
        '/etc/ssl/private': (0o700, 'SSL private keys directory'),
    }
    
    # Patterns for SSH private keys in home directories
    SSH_KEY_PATTERNS = [
        'id_rsa',
        'id_dsa',
        'id_ecdsa',
        'id_ed25519',
    ]
    
    @property
    def rule_name(self) -> str:
        return "weak-permissions"
    
    @property
    def description(self) -> str:
        return "Detects weak permissions on sensitive files (SSH keys, passwords, etc.)"
    
    def applies_to(self, path: str) -> bool:
        """
        Check if this rule applies to the given path
        
        Args:
            path: File path to check
            
        Returns:
            True if path is a sensitive file
        """
        # Check exact matches
        if path in self.SENSITIVE_FILES:
            return True
        
        # Check for SSH private keys
        if '/.ssh/' in path:
            for pattern in self.SSH_KEY_PATTERNS:
                if path.endswith(pattern):
                    return True
        
        # Check for files in sensitive directories
        if path.startswith('/etc/ssl/private/'):
            return True
        
        return False
    
    def check(self, path: str) -> Optional[ComplianceIssue]:
        """
        Check if file has weak permissions
        
        Args:
            path: File path to check
            
        Returns:
            ComplianceIssue if weak permissions found, None otherwise
        """
        try:
            stat_info = os.stat(path)
            mode = stat_info.st_mode
            
            # Get permission bits only (last 9 bits)
            perms = stat.S_IMODE(mode)
            
            # Determine expected permissions
            expected_perms = None
            file_desc = "sensitive file"
            
            if path in self.SENSITIVE_FILES:
                expected_perms, file_desc = self.SENSITIVE_FILES[path]
            elif '/.ssh/' in path:
                # SSH private keys should be 0600
                for pattern in self.SSH_KEY_PATTERNS:
                    if path.endswith(pattern):
                        expected_perms = 0o600
                        file_desc = "SSH private key"
                        break
            elif path.startswith('/etc/ssl/private/'):
                expected_perms = 0o600
                file_desc = "SSL private key"
            
            if expected_perms is None:
                return None
            
            # Check if permissions are too permissive
            # A file is too permissive if it has any bits set that shouldn't be
            if perms & ~expected_perms:
                return ComplianceIssue(
                    severity='HIGH',
                    rule=self.rule_name,
                    path=path,
                    description=f'Weak permissions on {file_desc} (current: {oct(perms)}, expected: {oct(expected_perms)} or stricter)',
                    recommendation=f'Set proper permissions: chmod {oct(expected_perms)} ' + path
                )
            
        except (OSError, PermissionError) as e:
            # If we can't stat the file, skip it
            pass
        
        return None
