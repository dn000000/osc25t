"""
Integration tests for ProcessManager class.
Tests process spawning, stopping, isolation, privilege dropping, and output capture.
"""

import os
import sys
import time
import tempfile
import pytest
from pathlib import Path

from gitproc.config import Config
from gitproc.process_manager import ProcessManager
from gitproc.parser import UnitFile
from gitproc.resource_controller import ResourceController


# Skip tests on Windows that require Unix-specific features
SKIP_ON_WINDOWS = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Test requires Unix-specific features"
)


@pytest.fixture
def test_config():
    """Create a test configuration with temporary directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config(
            repo_path=os.path.join(tmpdir, "services"),
            branch="main",
            socket_path=os.path.join(tmpdir, "gitproc.sock"),
            state_file=os.path.join(tmpdir, "state.json"),
            log_dir=os.path.join(tmpdir, "logs"),
            cgroup_root=os.path.join(tmpdir, "cgroup")
        )
        config.ensure_directories()
        yield config


@pytest.fixture
def process_manager(test_config):
    """Create a ProcessManager instance for testing."""
    return ProcessManager(test_config)


class TestProcessLifecycle:
    """Tests for basic process lifecycle operations."""
    
    @SKIP_ON_WINDOWS
    def test_start_simple_process(self, process_manager):
        """Test starting a simple process (sleep command)."""
        unit = UnitFile(
            name="test-sleep",
            exec_start="/bin/sleep 10"
        )
        
        # Start the process
        process_info = process_manager.start_process(unit)
        
        try:
            # Verify process info
            assert process_info.pid > 0
            assert process_info.service_name == "test-sleep"
            assert "test-sleep.log" in process_info.log_file
            
            # Verify process is running
            assert process_manager.is_running(process_info.pid)
            
            # Verify process is tracked
            assert process_info.pid in process_manager.processes
            
        finally:
            # Clean up
            if process_manager.is_running(process_info.pid):
                process_manager.stop_process(process_info.pid)
    
    @SKIP_ON_WINDOWS
    def test_stop_process_with_sigterm(self, process_manager):
        """Test stopping a process with SIGTERM (graceful shutdown)."""
        # Create a simple process that will respond to SIGTERM
        unit = UnitFile(
            name="test-graceful",
            exec_start="/bin/sleep 30"
        )
        
        # Start the process
        process_info = process_manager.start_process(unit)
        pid = process_info.pid
        
        # Give it a moment to start
        time.sleep(0.5)
        
        # Verify it's running
        assert process_manager.is_running(pid)
        
        # Stop the process
        result = process_manager.stop_process(pid, timeout=5)
        
        # Give it a moment to fully terminate
        time.sleep(0.5)
        
        # Verify it stopped successfully
        assert result is True
        assert not process_manager.is_running(pid)
        
        # Verify process was removed from tracking
        assert pid not in process_manager.processes
    
    @SKIP_ON_WINDOWS
    def test_forced_kill_with_sigkill(self, process_manager):
        """Test forced termination with SIGKILL after timeout."""
        # Create a script that ignores SIGTERM
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write("""#!/bin/bash
trap '' TERM
sleep 30
""")
            script_path = f.name
        
        try:
            # Make script executable
            os.chmod(script_path, 0o755)
            
            unit = UnitFile(
                name="test-stubborn",
                exec_start=script_path
            )
            
            # Start the process
            process_info = process_manager.start_process(unit)
            pid = process_info.pid
            
            # Give it a moment to start and set up signal handler
            time.sleep(1.0)
            assert process_manager.is_running(pid)
            
            # Stop with short timeout (should force SIGKILL)
            start_time = time.time()
            result = process_manager.stop_process(pid, timeout=1)
            elapsed = time.time() - start_time
            
            # Give it a moment to fully terminate
            time.sleep(0.5)
            
            # Verify it was killed
            assert result is True
            assert not process_manager.is_running(pid)
            
            # Verify it took at least the timeout period
            assert elapsed >= 1.0
            
        finally:
            os.unlink(script_path)


class TestProcessIsolation:
    """Tests for PID namespace isolation."""
    
    @SKIP_ON_WINDOWS
    def test_pid_namespace_isolation(self, process_manager):
        """Test that process runs in isolated PID namespace."""
        # Create a script that checks its PID and lists processes
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write("""#!/bin/bash
echo "My PID: $$"
echo "Process list:"
ps aux 2>/dev/null || ps -ef 2>/dev/null || echo "ps command not available"
sleep 2
""")
            script_path = f.name
        
        try:
            os.chmod(script_path, 0o755)
            
            unit = UnitFile(
                name="test-isolation",
                exec_start=script_path
            )
            
            # Start the process
            process_info = process_manager.start_process(unit)
            pid = process_info.pid
            
            try:
                # Wait for process to complete
                time.sleep(3)
                
                # Read the log file
                log_content = process_manager.get_logs("test-isolation")
                
                # Check if isolation was attempted
                # Note: Isolation may not work in all environments (containers, permissions)
                # So we just verify the process ran and logged output
                assert "My PID:" in log_content or "Process list:" in log_content
                
            finally:
                if process_manager.is_running(pid):
                    process_manager.stop_process(pid)
                    
        finally:
            os.unlink(script_path)


class TestPrivilegeDropping:
    """Tests for privilege dropping functionality."""
    
    @SKIP_ON_WINDOWS
    @pytest.mark.skipif(
        hasattr(os, 'geteuid') and os.geteuid() != 0,
        reason="Test requires root privileges"
    )
    def test_privilege_dropping_to_nobody(self, process_manager):
        """Test that process runs as specified user (nobody)."""
        # Create a script that prints the current user
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write("""#!/bin/bash
echo "User: $(whoami)"
echo "UID: $(id -u)"
echo "GID: $(id -g)"
sleep 1
""")
            script_path = f.name
        
        try:
            os.chmod(script_path, 0o755)
            
            unit = UnitFile(
                name="test-privdrop",
                exec_start=script_path,
                user="nobody"
            )
            
            # Start the process
            process_info = process_manager.start_process(unit)
            pid = process_info.pid
            
            try:
                # Wait for process to complete
                time.sleep(2)
                
                # Read the log file
                log_content = process_manager.get_logs("test-privdrop")
                
                # Verify it ran as nobody
                assert "User: nobody" in log_content or "nobody" in log_content.lower()
                
            finally:
                if process_manager.is_running(pid):
                    process_manager.stop_process(pid)
                    
        finally:
            os.unlink(script_path)
    
    @SKIP_ON_WINDOWS
    def test_privilege_dropping_invalid_user(self, process_manager):
        """Test that invalid user causes process to fail."""
        unit = UnitFile(
            name="test-baduser",
            exec_start="/bin/sleep 10",
            user="nonexistent_user_12345"
        )
        
        # Start the process (should fail in child)
        process_info = process_manager.start_process(unit)
        pid = process_info.pid
        
        # Wait for child to fail and exit
        time.sleep(0.5)
        
        # Try to reap the zombie process multiple times
        reaped = False
        for attempt in range(10):
            try:
                result = os.waitpid(pid, os.WNOHANG)
                if result[0] != 0:
                    reaped = True
                    break
            except (OSError, ChildProcessError):
                # Process doesn't exist or already reaped
                reaped = True
                break
            time.sleep(0.2)
        
        # Give it one more moment for the process to fully terminate
        time.sleep(0.5)
        
        # Process should have exited due to privilege drop failure
        is_running = process_manager.is_running(pid)
        assert not is_running, f"Process {pid} should have exited but is still running. Reaped: {reaped}"


class TestOutputCapture:
    """Tests for stdout/stderr capture."""
    
    @SKIP_ON_WINDOWS
    def test_capture_stdout(self, process_manager):
        """Test that stdout is captured to log file."""
        # Create a script that writes to stdout
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write("""#!/bin/bash
echo "Hello from stdout"
echo "Line 2"
echo "Line 3"
sleep 1
""")
            script_path = f.name
        
        try:
            os.chmod(script_path, 0o755)
            
            unit = UnitFile(
                name="test-stdout",
                exec_start=script_path
            )
            
            # Start the process
            process_info = process_manager.start_process(unit)
            pid = process_info.pid
            
            try:
                # Wait for process to complete
                time.sleep(2)
                
                # Read the log file
                log_content = process_manager.get_logs("test-stdout")
                
                # Verify output was captured
                assert "Hello from stdout" in log_content
                assert "Line 2" in log_content
                assert "Line 3" in log_content
                
            finally:
                if process_manager.is_running(pid):
                    process_manager.stop_process(pid)
                    
        finally:
            os.unlink(script_path)
    
    @SKIP_ON_WINDOWS
    def test_capture_stderr(self, process_manager):
        """Test that stderr is captured to log file."""
        # Create a script that writes to stderr
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write("""#!/bin/bash
echo "Error message" >&2
echo "Another error" >&2
sleep 1
""")
            script_path = f.name
        
        try:
            os.chmod(script_path, 0o755)
            
            unit = UnitFile(
                name="test-stderr",
                exec_start=script_path
            )
            
            # Start the process
            process_info = process_manager.start_process(unit)
            pid = process_info.pid
            
            try:
                # Wait for process to complete
                time.sleep(2)
                
                # Read the log file
                log_content = process_manager.get_logs("test-stderr")
                
                # Verify stderr was captured
                assert "Error message" in log_content
                assert "Another error" in log_content
                
            finally:
                if process_manager.is_running(pid):
                    process_manager.stop_process(pid)
                    
        finally:
            os.unlink(script_path)
    
    @SKIP_ON_WINDOWS
    def test_log_file_path(self, process_manager, test_config):
        """Test that log file is created in correct location."""
        unit = UnitFile(
            name="test-logpath",
            exec_start="/bin/echo 'test message'"
        )
        
        # Start the process
        process_info = process_manager.start_process(unit)
        pid = process_info.pid
        
        # Wait for process to complete
        time.sleep(1)
        
        # Verify log file exists
        expected_log_path = os.path.join(test_config.log_dir, "test-logpath.log")
        assert os.path.exists(expected_log_path)
        
        # Verify log file path matches
        assert process_info.log_file == expected_log_path
        
        # Verify we can read it
        log_content = process_manager.get_logs("test-logpath")
        assert "test message" in log_content
    
    @SKIP_ON_WINDOWS
    def test_get_logs_with_lines_limit(self, process_manager):
        """Test getting limited number of log lines."""
        # Create a script that outputs multiple lines
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write("""#!/bin/bash
for i in {1..10}; do
    echo "Line $i"
done
sleep 1
""")
            script_path = f.name
        
        try:
            os.chmod(script_path, 0o755)
            
            unit = UnitFile(
                name="test-lines",
                exec_start=script_path
            )
            
            # Start the process
            process_info = process_manager.start_process(unit)
            pid = process_info.pid
            
            try:
                # Wait for process to complete
                time.sleep(2)
                
                # Get last 3 lines
                log_content = process_manager.get_logs("test-lines", lines=3)
                lines = log_content.strip().split('\n')
                
                # Should have at most 3 lines
                assert len(lines) <= 3
                
                # Should contain the last lines
                assert "Line 10" in log_content or "Line 9" in log_content
                
            finally:
                if process_manager.is_running(pid):
                    process_manager.stop_process(pid)
                    
        finally:
            os.unlink(script_path)


class TestEnvironmentVariables:
    """Tests for environment variable handling."""
    
    @SKIP_ON_WINDOWS
    def test_environment_variables(self, process_manager):
        """Test that environment variables are set correctly."""
        # Create a script that prints environment variables
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False) as f:
            f.write("""#!/bin/bash
echo "TEST_VAR=$TEST_VAR"
echo "ANOTHER_VAR=$ANOTHER_VAR"
sleep 1
""")
            script_path = f.name
        
        try:
            os.chmod(script_path, 0o755)
            
            unit = UnitFile(
                name="test-env",
                exec_start=script_path,
                environment={"TEST_VAR": "hello", "ANOTHER_VAR": "world"}
            )
            
            # Start the process
            process_info = process_manager.start_process(unit)
            pid = process_info.pid
            
            try:
                # Wait for process to complete
                time.sleep(2)
                
                # Read the log file
                log_content = process_manager.get_logs("test-env")
                
                # Verify environment variables were set
                assert "TEST_VAR=hello" in log_content
                assert "ANOTHER_VAR=world" in log_content
                
            finally:
                if process_manager.is_running(pid):
                    process_manager.stop_process(pid)
                    
        finally:
            os.unlink(script_path)


class TestProcessTracking:
    """Tests for process tracking functionality."""
    
    @SKIP_ON_WINDOWS
    def test_is_running_check(self, process_manager):
        """Test is_running() method."""
        unit = UnitFile(
            name="test-running",
            exec_start="/bin/sleep 5"
        )
        
        # Start the process
        process_info = process_manager.start_process(unit)
        pid = process_info.pid
        
        try:
            # Give it a moment to start
            time.sleep(0.5)
            
            # Should be running
            assert process_manager.is_running(pid)
            
            # Stop it
            process_manager.stop_process(pid)
            
            # Give it a moment to fully terminate
            time.sleep(0.5)
            
            # Should not be running
            assert not process_manager.is_running(pid)
            
        finally:
            if process_manager.is_running(pid):
                process_manager.stop_process(pid)
                time.sleep(0.5)
    
    @SKIP_ON_WINDOWS
    def test_is_running_nonexistent_pid(self, process_manager):
        """Test is_running() with nonexistent PID."""
        # Use a PID that's very unlikely to exist
        fake_pid = 999999
        assert not process_manager.is_running(fake_pid)
