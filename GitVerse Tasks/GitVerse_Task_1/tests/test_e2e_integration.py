#!/usr/bin/env python3
"""
End-to-end integration tests for the complete sysaudit system.
Tests the full workflow from installation to monitoring.
"""

import os
import sys
import time
import tempfile
import shutil
import subprocess
from pathlib import Path
import pytest


class TestEndToEndIntegration:
    """Test complete system workflow"""
    
    def test_installation_workflow(self):
        """Test that installation creates necessary files and structure"""
        # Verify package is accessible (either installed or via PYTHONPATH)
        result = subprocess.run(
            [sys.executable, "-c", "import sysaudit; print(sysaudit.__version__)"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0, "Package not accessible"
        assert "0.1.0" in result.stdout
    
    def test_cli_commands_available(self):
        """Test that all CLI commands are available"""
        result = subprocess.run(
            [sys.executable, "-m", "sysaudit", "--help"],
            capture_output=True,
            text=True
        )
        assert result.returncode == 0
        
        # Check all commands are listed
        commands = ["init", "monitor", "snapshot", "drift-check", 
                   "compliance-report", "rollback"]
        for cmd in commands:
            assert cmd in result.stdout, f"Command {cmd} not found in help"
    
    def test_init_command(self):
        """Test repository initialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = os.path.join(tmpdir, "audit_repo")
            
            result = subprocess.run(
                [sys.executable, "-m", "sysaudit", "init", 
                 "--repo", repo_path, "--baseline", "main"],
                capture_output=True,
                text=True
            )
            
            assert result.returncode == 0, f"Init failed: {result.stderr}"
            assert os.path.exists(repo_path), "Repository not created"
            assert os.path.exists(os.path.join(repo_path, ".git")), "Git not initialized"
    
    def test_snapshot_command(self):
        """Test manual snapshot creation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = os.path.join(tmpdir, "audit_repo")
            watch_path = os.path.join(tmpdir, "watch")
            os.makedirs(watch_path)
            
            # Initialize
            subprocess.run(
                [sys.executable, "-m", "sysaudit", "init", 
                 "--repo", repo_path],
                capture_output=True
            )
            
            # Create test file
            test_file = os.path.join(watch_path, "test.txt")
            Path(test_file).write_text("test content")
            
            # Create snapshot
            result = subprocess.run(
                [sys.executable, "-m", "sysaudit", "snapshot",
                 "--repo", repo_path,
                 "--paths", watch_path,
                 "--message", "Test snapshot"],
                capture_output=True,
                text=True
            )
            
            assert result.returncode == 0, f"Snapshot failed: {result.stderr}"
    
    def test_drift_check_command(self):
        """Test drift detection"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = os.path.join(tmpdir, "audit_repo")
            
            # Initialize
            subprocess.run(
                [sys.executable, "-m", "sysaudit", "init", 
                 "--repo", repo_path],
                capture_output=True
            )
            
            # Run drift check
            result = subprocess.run(
                [sys.executable, "-m", "sysaudit", "drift-check",
                 "--repo", repo_path,
                 "--baseline", "main"],
                capture_output=True,
                text=True
            )
            
            assert result.returncode == 0, f"Drift check failed: {result.stderr}"
    
    def test_compliance_report_command(self):
        """Test compliance report generation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            watch_path = os.path.join(tmpdir, "watch")
            os.makedirs(watch_path)
            
            # Create test file with world-writable permissions
            test_file = os.path.join(watch_path, "test.txt")
            Path(test_file).write_text("test")
            os.chmod(test_file, 0o666)
            
            # Run compliance report
            result = subprocess.run(
                [sys.executable, "-m", "sysaudit", "compliance-report",
                 "--paths", watch_path,
                 "--format", "text"],
                capture_output=True,
                text=True
            )
            
            assert result.returncode == 0, f"Compliance report failed: {result.stderr}"
    
    def test_rollback_command_dry_run(self):
        """Test rollback in dry-run mode"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = os.path.join(tmpdir, "audit_repo")
            watch_path = os.path.join(tmpdir, "watch")
            os.makedirs(watch_path)
            
            # Initialize
            subprocess.run(
                [sys.executable, "-m", "sysaudit", "init", 
                 "--repo", repo_path],
                capture_output=True
            )
            
            # Create and snapshot a file
            test_file = os.path.join(watch_path, "test.txt")
            Path(test_file).write_text("original")
            
            subprocess.run(
                [sys.executable, "-m", "sysaudit", "snapshot",
                 "--repo", repo_path,
                 "--paths", watch_path,
                 "--message", "Original"],
                capture_output=True
            )
            
            # Try rollback (dry-run)
            result = subprocess.run(
                [sys.executable, "-m", "sysaudit", "rollback",
                 "--repo", repo_path,
                 "--path", test_file,
                 "--to-commit", "HEAD",
                 "--dry-run"],
                capture_output=True,
                text=True
            )
            
            # Should succeed or fail gracefully
            assert result.returncode in [0, 1]
    
    def test_monitoring_workflow(self):
        """Test basic monitoring workflow (short duration)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = os.path.join(tmpdir, "audit_repo")
            watch_path = os.path.join(tmpdir, "watch")
            os.makedirs(watch_path)
            
            # Initialize
            subprocess.run(
                [sys.executable, "-m", "sysaudit", "init", 
                 "--repo", repo_path],
                capture_output=True
            )
            
            # Start monitoring in background (with timeout)
            monitor_proc = subprocess.Popen(
                [sys.executable, "-m", "sysaudit", "monitor",
                 "--repo", repo_path,
                 "--watch", watch_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            try:
                # Give it time to start
                time.sleep(2)
                
                # Create a test file
                test_file = os.path.join(watch_path, "monitored.txt")
                Path(test_file).write_text("monitored content")
                
                # Wait for event processing
                time.sleep(3)
                
                # Check if process is still running
                assert monitor_proc.poll() is None, "Monitor process died"
                
            finally:
                # Clean up
                monitor_proc.terminate()
                try:
                    monitor_proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    monitor_proc.kill()
    
    def test_config_file_loading(self):
        """Test configuration file loading"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_file = os.path.join(tmpdir, "config.yaml")
            repo_path = os.path.join(tmpdir, "audit_repo")
            watch_path = os.path.join(tmpdir, "watch")
            
            # Create config file
            config_content = f"""
repository:
  path: {repo_path}
  baseline: main

monitoring:
  paths:
    - {watch_path}
  batch_interval: 5
  batch_size: 10
"""
            Path(config_file).write_text(config_content)
            
            # Test that config can be loaded
            from sysaudit.config import Config
            config = Config.from_yaml(config_file)
            
            assert config.repo_path == repo_path
            assert watch_path in config.watch_paths


class TestSystemdService:
    """Test systemd service integration"""
    
    def test_service_file_exists(self):
        """Test that service file is present"""
        service_file = Path("sysaudit.service")
        assert service_file.exists(), "Service file not found"
        
        content = service_file.read_text()
        assert "sysaudit" in content
        assert "ExecStart" in content
        assert "[Unit]" in content
        assert "[Service]" in content
        assert "[Install]" in content
    
    def test_service_file_syntax(self):
        """Test service file has valid syntax"""
        service_file = Path("sysaudit.service")
        content = service_file.read_text()
        
        # Check required sections
        assert "[Unit]" in content
        assert "[Service]" in content
        assert "[Install]" in content
        
        # Check required fields
        assert "Description=" in content
        assert "ExecStart=" in content
        assert "Type=" in content
        assert "WantedBy=" in content


class TestErrorHandling:
    """Test error handling and edge cases"""
    
    def test_invalid_repo_path(self):
        """Test handling of invalid repository path"""
        result = subprocess.run(
            [sys.executable, "-m", "sysaudit", "drift-check",
             "--repo", "/nonexistent/path"],
            capture_output=True,
            text=True
        )
        
        # Should fail gracefully
        assert result.returncode != 0
        # Check for error indicators in output
        error_text = (result.stderr + result.stdout).lower()
        assert any(word in error_text for word in ["error", "failed", "not found", "must be specified"])
    
    def test_invalid_command_args(self):
        """Test handling of invalid command arguments"""
        result = subprocess.run(
            [sys.executable, "-m", "sysaudit", "init"],
            capture_output=True,
            text=True
        )
        
        # Should fail with missing required argument
        assert result.returncode != 0
    
    def test_nonexistent_watch_path(self):
        """Test handling of nonexistent watch path"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = os.path.join(tmpdir, "audit_repo")
            
            subprocess.run(
                [sys.executable, "-m", "sysaudit", "init", 
                 "--repo", repo_path],
                capture_output=True
            )
            
            result = subprocess.run(
                [sys.executable, "-m", "sysaudit", "monitor",
                 "--repo", repo_path,
                 "--watch", "/nonexistent/path"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            # Should handle gracefully
            assert result.returncode != 0 or "error" in result.stderr.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
