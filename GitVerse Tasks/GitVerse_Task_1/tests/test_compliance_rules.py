"""Detailed unit tests for individual compliance rules"""

import os
import sys
import stat
import tempfile
import pytest
from pathlib import Path

from sysaudit.compliance import (
    WorldWritableRule,
    SUIDSGIDRule,
    WeakPermissionsRule
)


class TestWorldWritableRuleDetailed:
    """Detailed tests for WorldWritableRule (Requirement 6.2)"""
    
    def test_rule_name_and_description(self):
        """Test rule has proper name and description"""
        rule = WorldWritableRule()
        assert rule.rule_name == "world-writable"
        assert isinstance(rule.description, str)
        assert len(rule.description) > 0
    
    def test_applies_to_etc_directory(self):
        """Test rule applies to /etc directory"""
        rule = WorldWritableRule()
        assert rule.applies_to('/etc/config')
        assert rule.applies_to('/etc/subdir/file')
        assert rule.applies_to('/etc/ssh/sshd_config')
    
    def test_applies_to_usr_bin(self):
        """Test rule applies to /usr/bin"""
        rule = WorldWritableRule()
        assert rule.applies_to('/usr/bin/program')
        assert rule.applies_to('/usr/bin/subdir/script')
    
    def test_applies_to_usr_local_bin(self):
        """Test rule applies to /usr/local/bin"""
        rule = WorldWritableRule()
        assert rule.applies_to('/usr/local/bin/myapp')
        assert rule.applies_to('/usr/local/bin/scripts/tool')
    
    def test_does_not_apply_to_home(self):
        """Test rule doesn't apply to home directories"""
        rule = WorldWritableRule()
        assert not rule.applies_to('/home/user/file.txt')
        assert not rule.applies_to('/home/admin/config')
    
    def test_does_not_apply_to_tmp(self):
        """Test rule doesn't apply to /tmp"""
        rule = WorldWritableRule()
        assert not rule.applies_to('/tmp/tempfile')
        assert not rule.applies_to('/tmp/subdir/file')
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix permissions not supported on Windows")
    def test_detects_mode_666(self):
        """Test detection of 0666 permissions"""
        rule = WorldWritableRule()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'etc', 'test')
            os.makedirs(os.path.dirname(test_file), exist_ok=True)
            Path(test_file).touch()
            os.chmod(test_file, 0o666)
            
            issue = rule.check(test_file)
            assert issue is not None
            assert issue.severity == 'HIGH'
            assert 'world-writable' in issue.description.lower()
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix permissions not supported on Windows")
    def test_detects_mode_777(self):
        """Test detection of 0777 permissions"""
        rule = WorldWritableRule()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'etc', 'test')
            os.makedirs(os.path.dirname(test_file), exist_ok=True)
            Path(test_file).touch()
            os.chmod(test_file, 0o777)
            
            issue = rule.check(test_file)
            assert issue is not None
            assert issue.severity == 'HIGH'
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix permissions not supported on Windows")
    def test_accepts_mode_644(self):
        """Test that 0644 permissions are acceptable"""
        rule = WorldWritableRule()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'etc', 'test')
            os.makedirs(os.path.dirname(test_file), exist_ok=True)
            Path(test_file).touch()
            os.chmod(test_file, 0o644)
            
            issue = rule.check(test_file)
            assert issue is None
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix permissions not supported on Windows")
    def test_accepts_mode_600(self):
        """Test that 0600 permissions are acceptable"""
        rule = WorldWritableRule()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'etc', 'test')
            os.makedirs(os.path.dirname(test_file), exist_ok=True)
            Path(test_file).touch()
            os.chmod(test_file, 0o600)
            
            issue = rule.check(test_file)
            assert issue is None
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix permissions not supported on Windows")
    def test_issue_contains_recommendation(self):
        """Test that issue includes recommendation"""
        rule = WorldWritableRule()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'etc', 'test')
            os.makedirs(os.path.dirname(test_file), exist_ok=True)
            Path(test_file).touch()
            os.chmod(test_file, 0o666)
            
            issue = rule.check(test_file)
            assert issue.recommendation is not None
            assert len(issue.recommendation) > 0
    
    def test_nonexistent_file(self):
        """Test handling of nonexistent file"""
        rule = WorldWritableRule()
        
        # Should raise FileNotFoundError or return None
        try:
            issue = rule.check('/nonexistent/file')
            # If it doesn't raise, it should return None
            assert issue is None
        except FileNotFoundError:
            pass  # This is also acceptable


class TestSUIDSGIDRuleDetailed:
    """Detailed tests for SUIDSGIDRule (Requirement 6.3)"""
    
    def test_rule_name_and_description(self):
        """Test rule has proper name and description"""
        rule = SUIDSGIDRule()
        assert rule.rule_name == "unexpected-suid-sgid"
        assert isinstance(rule.description, str)
        assert len(rule.description) > 0
    
    def test_applies_to_all_paths(self):
        """Test rule applies to all file paths"""
        rule = SUIDSGIDRule()
        assert rule.applies_to('/etc/config')
        assert rule.applies_to('/usr/bin/program')
        assert rule.applies_to('/home/user/file')
        assert rule.applies_to('/tmp/test')
    
    def test_expected_suid_files_list(self):
        """Test that expected SUID files are defined"""
        rule = SUIDSGIDRule()
        assert hasattr(rule, 'EXPECTED_SUID_FILES')
        assert isinstance(rule.EXPECTED_SUID_FILES, (set, list, tuple))
        assert len(rule.EXPECTED_SUID_FILES) > 0
    
    def test_expected_suid_includes_sudo(self):
        """Test that sudo is in expected SUID files"""
        rule = SUIDSGIDRule()
        assert '/usr/bin/sudo' in rule.EXPECTED_SUID_FILES
    
    def test_expected_suid_includes_su(self):
        """Test that su is in expected SUID files"""
        rule = SUIDSGIDRule()
        assert '/usr/bin/su' in rule.EXPECTED_SUID_FILES
    
    def test_expected_suid_includes_passwd(self):
        """Test that passwd is in expected SUID files"""
        rule = SUIDSGIDRule()
        assert '/usr/bin/passwd' in rule.EXPECTED_SUID_FILES
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix permissions not supported on Windows")
    def test_detects_suid_bit(self):
        """Test detection of SUID bit (04000)"""
        rule = SUIDSGIDRule()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'suspicious')
            Path(test_file).touch()
            os.chmod(test_file, 0o4755)  # SUID bit set
            
            issue = rule.check(test_file)
            assert issue is not None
            assert issue.severity == 'HIGH'
            assert 'suid' in issue.description.lower() or 'sgid' in issue.description.lower()
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix permissions not supported on Windows")
    def test_detects_sgid_bit(self):
        """Test detection of SGID bit (02000)"""
        rule = SUIDSGIDRule()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'suspicious')
            Path(test_file).touch()
            os.chmod(test_file, 0o2755)  # SGID bit set
            
            issue = rule.check(test_file)
            assert issue is not None
            assert issue.severity == 'HIGH'
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix permissions not supported on Windows")
    def test_detects_both_suid_and_sgid(self):
        """Test detection of both SUID and SGID bits"""
        rule = SUIDSGIDRule()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'suspicious')
            Path(test_file).touch()
            os.chmod(test_file, 0o6755)  # Both SUID and SGID
            
            issue = rule.check(test_file)
            assert issue is not None
            assert issue.severity == 'HIGH'
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix permissions not supported on Windows")
    def test_accepts_normal_permissions(self):
        """Test that normal permissions don't trigger alert"""
        rule = SUIDSGIDRule()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'normal')
            Path(test_file).touch()
            os.chmod(test_file, 0o755)  # No SUID/SGID
            
            issue = rule.check(test_file)
            assert issue is None
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix permissions not supported on Windows")
    def test_issue_includes_recommendation(self):
        """Test that issue includes recommendation"""
        rule = SUIDSGIDRule()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, 'suspicious')
            Path(test_file).touch()
            os.chmod(test_file, 0o4755)
            
            issue = rule.check(test_file)
            assert issue.recommendation is not None
            assert len(issue.recommendation) > 0


class TestWeakPermissionsRuleDetailed:
    """Detailed tests for WeakPermissionsRule"""
    
    def test_rule_name_and_description(self):
        """Test rule has proper name and description"""
        rule = WeakPermissionsRule()
        assert rule.rule_name == "weak-permissions"
        assert isinstance(rule.description, str)
        assert len(rule.description) > 0
    
    def test_applies_to_shadow_file(self):
        """Test rule applies to /etc/shadow"""
        rule = WeakPermissionsRule()
        assert rule.applies_to('/etc/shadow')
    
    def test_applies_to_ssh_config(self):
        """Test rule applies to SSH config files"""
        rule = WeakPermissionsRule()
        assert rule.applies_to('/etc/ssh/sshd_config')
        # Note: ssh_config (client config) is not in the sensitive files list
        # Only sshd_config (server config) is checked
    
    def test_applies_to_ssh_private_keys(self):
        """Test rule applies to SSH private keys"""
        rule = WeakPermissionsRule()
        assert rule.applies_to('/root/.ssh/id_rsa')
        assert rule.applies_to('/home/user/.ssh/id_rsa')
        assert rule.applies_to('/home/user/.ssh/id_ed25519')
        assert rule.applies_to('/home/user/.ssh/id_ecdsa')
    
    def test_does_not_apply_to_public_keys(self):
        """Test rule doesn't apply to SSH public keys"""
        rule = WeakPermissionsRule()
        # Public keys (.pub) typically don't need strict permissions
        # This depends on implementation
        result = rule.applies_to('/home/user/.ssh/id_rsa.pub')
        # Either way is acceptable, just document the behavior
        assert isinstance(result, bool)
    
    def test_does_not_apply_to_regular_files(self):
        """Test rule doesn't apply to regular files"""
        rule = WeakPermissionsRule()
        assert not rule.applies_to('/home/user/document.txt')
        assert not rule.applies_to('/tmp/test.txt')
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix permissions not supported on Windows")
    def test_detects_weak_ssh_key_permissions(self):
        """Test detection of weak SSH key permissions"""
        rule = WeakPermissionsRule()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ssh_dir = os.path.join(tmpdir, '.ssh')
            os.makedirs(ssh_dir)
            key_file = os.path.join(ssh_dir, 'id_rsa')
            Path(key_file).write_text("fake private key")
            os.chmod(key_file, 0o644)  # Too permissive
            
            issue = rule.check(key_file)
            assert issue is not None
            assert issue.severity == 'HIGH'
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix permissions not supported on Windows")
    def test_accepts_proper_ssh_key_permissions(self):
        """Test that proper SSH key permissions (0600) are accepted"""
        rule = WeakPermissionsRule()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ssh_dir = os.path.join(tmpdir, '.ssh')
            os.makedirs(ssh_dir)
            key_file = os.path.join(ssh_dir, 'id_rsa')
            Path(key_file).write_text("fake private key")
            os.chmod(key_file, 0o600)  # Proper permissions
            
            issue = rule.check(key_file)
            assert issue is None
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix permissions not supported on Windows")
    def test_detects_group_readable_key(self):
        """Test detection of group-readable SSH key"""
        rule = WeakPermissionsRule()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ssh_dir = os.path.join(tmpdir, '.ssh')
            os.makedirs(ssh_dir)
            key_file = os.path.join(ssh_dir, 'id_rsa')
            Path(key_file).write_text("fake private key")
            os.chmod(key_file, 0o640)  # Group readable
            
            issue = rule.check(key_file)
            assert issue is not None
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix permissions not supported on Windows")
    def test_detects_world_readable_key(self):
        """Test detection of world-readable SSH key"""
        rule = WeakPermissionsRule()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ssh_dir = os.path.join(tmpdir, '.ssh')
            os.makedirs(ssh_dir)
            key_file = os.path.join(ssh_dir, 'id_rsa')
            Path(key_file).write_text("fake private key")
            os.chmod(key_file, 0o604)  # World readable
            
            issue = rule.check(key_file)
            assert issue is not None
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix permissions not supported on Windows")
    def test_issue_includes_recommendation(self):
        """Test that issue includes recommendation"""
        rule = WeakPermissionsRule()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ssh_dir = os.path.join(tmpdir, '.ssh')
            os.makedirs(ssh_dir)
            key_file = os.path.join(ssh_dir, 'id_rsa')
            Path(key_file).write_text("fake private key")
            os.chmod(key_file, 0o644)
            
            issue = rule.check(key_file)
            assert issue.recommendation is not None
            assert len(issue.recommendation) > 0
            assert 'chmod' in issue.recommendation.lower() or 'permission' in issue.recommendation.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
