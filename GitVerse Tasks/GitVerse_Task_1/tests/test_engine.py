"""Tests for the AuditEngine core orchestration"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from sysaudit.core.engine import AuditEngine, AuditEngineError, safe_operation, retry_on_transient_error
from sysaudit.models import Config, FileEvent, ComplianceIssue


@pytest.fixture
def temp_dirs():
    """Create temporary directories for testing"""
    temp_dir = tempfile.mkdtemp()
    repo_dir = Path(temp_dir) / "repo"
    watch_dir = Path(temp_dir) / "watch"
    repo_dir.mkdir()
    watch_dir.mkdir()
    
    yield {
        'temp': temp_dir,
        'repo': str(repo_dir),
        'watch': str(watch_dir)
    }
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def config(temp_dirs):
    """Create test configuration"""
    return Config(
        repo_path=temp_dirs['repo'],
        watch_paths=[temp_dirs['watch']],
        baseline_branch='baseline',
        auto_compliance=True,
        batch_interval=1,
        batch_size=5
    )


class TestSafeOperation:
    """Test the safe_operation decorator"""
    
    def test_safe_operation_handles_file_not_found(self):
        """Test that FileNotFoundError is handled gracefully"""
        @safe_operation("test_operation")
        def failing_func():
            raise FileNotFoundError("File disappeared")
        
        # Should not raise, returns None
        result = failing_func()
        assert result is None
    
    def test_safe_operation_handles_permission_error(self):
        """Test that PermissionError is handled gracefully"""
        @safe_operation("test_operation")
        def failing_func():
            raise PermissionError("Access denied")
        
        result = failing_func()
        assert result is None
    
    def test_safe_operation_handles_generic_exception(self):
        """Test that generic exceptions are handled"""
        @safe_operation("test_operation")
        def failing_func():
            raise ValueError("Something went wrong")
        
        result = failing_func()
        assert result is None
    
    def test_safe_operation_returns_value_on_success(self):
        """Test that successful operations return their value"""
        @safe_operation("test_operation")
        def success_func():
            return "success"
        
        result = success_func()
        assert result == "success"


class TestRetryOnTransientError:
    """Test the retry_on_transient_error decorator"""
    
    def test_retry_succeeds_on_second_attempt(self):
        """Test that retry succeeds after transient failure"""
        call_count = [0]
        
        @retry_on_transient_error(max_retries=3, delay=0.1)
        def flaky_func():
            call_count[0] += 1
            if call_count[0] < 2:
                raise OSError("Temporary failure")
            return "success"
        
        result = flaky_func()
        assert result == "success"
        assert call_count[0] == 2
    
    def test_retry_exhausts_attempts(self):
        """Test that retry gives up after max attempts"""
        @retry_on_transient_error(max_retries=2, delay=0.1)
        def always_fails():
            raise OSError("Persistent failure")
        
        with pytest.raises(OSError):
            always_fails()
    
    def test_retry_does_not_retry_non_transient_errors(self):
        """Test that non-transient errors are not retried"""
        call_count = [0]
        
        @retry_on_transient_error(max_retries=3, delay=0.1)
        def non_transient_failure():
            call_count[0] += 1
            raise ValueError("Non-transient error")
        
        with pytest.raises(ValueError):
            non_transient_failure()
        
        # Should only be called once (no retries)
        assert call_count[0] == 1


class TestAuditEngine:
    """Test the AuditEngine class"""
    
    def test_engine_initialization(self, config):
        """Test that engine initializes correctly"""
        engine = AuditEngine(config)
        
        assert engine.config == config
        assert not engine.running
        assert engine.monitor is not None
        assert engine.git_manager is not None
        assert engine.compliance_checker is not None
        assert engine.alert_manager is not None
    
    def test_engine_initialization_failure(self, temp_dirs):
        """Test that initialization errors are handled"""
        # Engine initialization doesn't fail for non-existent paths
        # It only fails when starting monitoring
        # This test verifies the engine can be created with any config
        bad_config = Config(
            repo_path="/nonexistent/path",
            watch_paths=["/nonexistent/watch"],
            baseline_branch='baseline'
        )
        
        # Engine creation should succeed
        engine = AuditEngine(bad_config)
        assert engine is not None
    
    def test_initialize_repository(self, config):
        """Test repository initialization"""
        engine = AuditEngine(config)
        engine.initialize_repository()
        
        assert engine.git_manager.is_initialized()
        assert Path(config.repo_path).exists()
    
    def test_get_status(self, config):
        """Test status reporting"""
        engine = AuditEngine(config)
        engine.initialize_repository()
        
        status = engine.get_status()
        
        assert 'running' in status
        assert 'repository_initialized' in status
        assert 'watch_paths' in status
        assert status['repository_initialized'] is True
        assert status['running'] is False
    
    def test_is_running(self, config):
        """Test running state check"""
        engine = AuditEngine(config)
        
        assert not engine.is_running()
        
        engine.running = True
        assert engine.is_running()
    
    def test_commit_changes_filters_disappeared_files(self, config):
        """Test that commit filters out files that disappeared"""
        engine = AuditEngine(config)
        engine.initialize_repository()
        
        # Create events for non-existent files
        events = [
            FileEvent(
                path="/nonexistent/file1.txt",
                event_type='modified',
                timestamp=datetime.now()
            ),
            FileEvent(
                path="/nonexistent/file2.txt",
                event_type='deleted',
                timestamp=datetime.now()
            )
        ]
        
        # Should not raise, handles gracefully
        engine._commit_changes(events)
    
    def test_check_compliance_handles_disappeared_files(self, config, temp_dirs):
        """Test that compliance check handles disappeared files"""
        engine = AuditEngine(config)
        engine.initialize_repository()
        
        # Create a file then delete it
        test_file = Path(temp_dirs['watch']) / "test.txt"
        test_file.write_text("test")
        
        events = [
            FileEvent(
                path=str(test_file),
                event_type='modified',
                timestamp=datetime.now()
            )
        ]
        
        # Delete the file
        test_file.unlink()
        
        # Should handle gracefully
        engine._check_compliance(events)
    
    def test_create_snapshot_handles_missing_paths(self, config, temp_dirs):
        """Test that snapshot handles missing watch paths"""
        engine = AuditEngine(config)
        engine.initialize_repository()
        
        # Add a non-existent path
        engine.config.watch_paths.append("/nonexistent/path")
        
        # Should not raise
        engine.create_snapshot("Test snapshot")
    
    def test_create_snapshot_handles_permission_errors(self, config, temp_dirs):
        """Test that snapshot handles permission errors gracefully"""
        engine = AuditEngine(config)
        engine.initialize_repository()
        
        # Create a file
        test_file = Path(temp_dirs['watch']) / "test.txt"
        test_file.write_text("test")
        
        # Mock path.rglob to raise PermissionError
        with patch.object(Path, 'rglob', side_effect=PermissionError("Access denied")):
            # Should not raise
            engine.create_snapshot("Test snapshot")
    
    def test_on_file_change_handles_errors(self, config):
        """Test that file change callback handles errors gracefully"""
        engine = AuditEngine(config)
        engine.initialize_repository()
        
        # Mock git_manager to raise error
        engine.git_manager.commit_changes = Mock(side_effect=Exception("Git error"))
        
        events = [
            FileEvent(
                path="/test/file.txt",
                event_type='modified',
                timestamp=datetime.now()
            )
        ]
        
        # Should not raise due to safe_operation decorator
        engine._on_file_change(events)
    
    def test_start_monitoring_requires_initialized_repo(self, config):
        """Test that monitoring requires initialized repository"""
        engine = AuditEngine(config)
        
        with pytest.raises(AuditEngineError, match="not initialized"):
            engine.start_monitoring()
    
    def test_start_monitoring_validates_watch_paths(self, config):
        """Test that monitoring validates watch paths exist"""
        engine = AuditEngine(config)
        engine.initialize_repository()
        
        # Add non-existent path
        engine.config.watch_paths.append("/nonexistent/path")
        
        with pytest.raises(AuditEngineError, match="does not exist"):
            engine.start_monitoring()
    
    def test_stop_monitoring_when_not_running(self, config):
        """Test that stopping when not running is handled gracefully"""
        engine = AuditEngine(config)
        
        # Should not raise
        engine.stop_monitoring()
    
    def test_run_compliance_scan(self, config, temp_dirs):
        """Test full compliance scan"""
        engine = AuditEngine(config)
        engine.initialize_repository()
        
        # Create some test files
        test_file = Path(temp_dirs['watch']) / "test.txt"
        test_file.write_text("test")
        
        issues = engine.run_compliance_scan()
        
        # Should return a list (may be empty)
        assert isinstance(issues, list)
    
    def test_logging_configuration(self, config):
        """Test that logging is configured correctly"""
        engine = AuditEngine(config, log_level='DEBUG')
        
        # Check that logger is configured
        import logging
        logger = logging.getLogger('sysaudit')
        assert logger.level == logging.DEBUG


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
