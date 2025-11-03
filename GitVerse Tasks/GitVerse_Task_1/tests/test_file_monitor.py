"""Tests for file monitoring functionality"""

import os
import time
import tempfile
import pytest
from pathlib import Path

from sysaudit.models import Config, FileEvent
from sysaudit.monitor import FileMonitor


class TestFileMonitor:
    """Test FileMonitor class"""
    
    def test_file_monitor_initialization(self):
        """Test that FileMonitor initializes correctly"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(
                repo_path=os.path.join(tmpdir, 'repo'),
                watch_paths=[tmpdir],
                batch_interval=5,
                batch_size=10,
                baseline_branch="main",
                gpg_sign=False
            )
            
            monitor = FileMonitor(config)
            assert monitor.config == config
            assert monitor.filter is not None
            assert not monitor.is_running()
    
    def test_file_monitor_start_stop(self):
        """Test starting and stopping the monitor"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(
                repo_path=os.path.join(tmpdir, 'repo'),
                watch_paths=[tmpdir],
                batch_interval=5,
                batch_size=10
            )
            
            events_received = []
            
            def callback(events):
                events_received.extend(events)
            
            monitor = FileMonitor(config)
            monitor.start(callback)
            
            assert monitor.is_running()
            
            monitor.stop()
            
            assert not monitor.is_running()
    
    def test_file_monitor_detects_file_creation(self):
        """Test that monitor detects file creation"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(
                repo_path=os.path.join(tmpdir, 'repo'),
                watch_paths=[tmpdir],
                batch_interval=1,  # Short interval for testing
                batch_size=10
            )
            
            events_received = []
            
            def callback(events):
                events_received.extend(events)
            
            monitor = FileMonitor(config)
            monitor.start(callback)
            
            # Create a test file
            test_file = os.path.join(tmpdir, 'test.txt')
            Path(test_file).write_text('test content')
            
            # Wait for event to be processed
            time.sleep(2)
            
            monitor.stop()
            
            # Check that we received at least one event
            assert len(events_received) > 0
            
            # Check that the event is for our test file
            file_paths = [e.path for e in events_received]
            assert any(test_file in path for path in file_paths)
    
    def test_file_monitor_detects_file_modification(self):
        """Test that monitor detects file modification"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create file before starting monitor
            test_file = os.path.join(tmpdir, 'test.txt')
            Path(test_file).write_text('initial content')
            
            config = Config(
                repo_path=os.path.join(tmpdir, 'repo'),
                watch_paths=[tmpdir],
                batch_interval=1,
                batch_size=10
            )
            
            events_received = []
            
            def callback(events):
                events_received.extend(events)
            
            monitor = FileMonitor(config)
            monitor.start(callback)
            
            # Modify the file
            time.sleep(0.5)  # Give monitor time to start
            Path(test_file).write_text('modified content')
            
            # Wait for event to be processed
            time.sleep(2)
            
            monitor.stop()
            
            # Check that we received events
            assert len(events_received) > 0
            
            # Check for modification event
            modification_events = [e for e in events_received if e.event_type == 'modified']
            assert len(modification_events) > 0
    
    def test_file_monitor_filters_ignored_files(self):
        """Test that monitor filters out ignored files"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create blacklist file
            blacklist_file = os.path.join(tmpdir, 'blacklist.txt')
            Path(blacklist_file).write_text('*.tmp\n*.log\n')
            
            config = Config(
                repo_path=os.path.join(tmpdir, 'repo'),
                watch_paths=[tmpdir],
                batch_interval=1,
                batch_size=10,
                blacklist_file=blacklist_file
            )
            
            events_received = []
            
            def callback(events):
                events_received.extend(events)
            
            monitor = FileMonitor(config)
            monitor.start(callback)
            
            # Create files that should be ignored
            tmp_file = os.path.join(tmpdir, 'test.tmp')
            log_file = os.path.join(tmpdir, 'test.log')
            normal_file = os.path.join(tmpdir, 'test.txt')
            
            Path(tmp_file).write_text('temp')
            Path(log_file).write_text('log')
            Path(normal_file).write_text('normal')
            
            # Wait for potential events
            time.sleep(2)
            
            monitor.stop()
            
            # Check that ignored files were not reported
            file_paths = [e.path for e in events_received]
            assert not any(tmp_file in path for path in file_paths), "tmp file should be ignored"
            assert not any(log_file in path for path in file_paths), "log file should be ignored"
            # But normal file should be reported
            assert any(normal_file in path for path in file_paths), "normal file should be reported"
    
    def test_file_monitor_batches_events(self):
        """Test that monitor batches multiple events"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(
                repo_path=os.path.join(tmpdir, 'repo'),
                watch_paths=[tmpdir],
                batch_interval=2,  # 2 second batch window
                batch_size=10
            )
            
            batch_count = 0
            
            def callback(events):
                nonlocal batch_count
                batch_count += 1
            
            monitor = FileMonitor(config)
            monitor.start(callback)
            
            # Create multiple files quickly
            for i in range(5):
                test_file = os.path.join(tmpdir, f'test{i}.txt')
                Path(test_file).write_text(f'content {i}')
                time.sleep(0.1)
            
            # Wait for batch to flush
            time.sleep(3)
            
            monitor.stop()
            
            # Should have received events in batches (likely 1 batch for all 5 files)
            assert batch_count >= 1
            assert batch_count <= 5  # Should be batched, not individual
    
    def test_file_monitor_invalid_watch_path(self):
        """Test that monitor raises error for invalid watch path"""
        config = Config(
            repo_path='/tmp/repo',
            watch_paths=['/nonexistent/path/that/does/not/exist'],
            batch_interval=5,
            batch_size=10
        )
        
        def callback(events):
            pass
        
        monitor = FileMonitor(config)
        
        with pytest.raises(ValueError, match="Watch path does not exist"):
            monitor.start(callback)
    
    def test_file_monitor_multiple_watch_paths(self):
        """Test monitoring multiple paths simultaneously"""
        with tempfile.TemporaryDirectory() as tmpdir1:
            with tempfile.TemporaryDirectory() as tmpdir2:
                config = Config(
                    repo_path=os.path.join(tmpdir1, 'repo'),
                    watch_paths=[tmpdir1, tmpdir2],
                    batch_interval=1,
                    batch_size=10
                )
                
                events_received = []
                
                def callback(events):
                    events_received.extend(events)
                
                monitor = FileMonitor(config)
                monitor.start(callback)
                
                # Create files in both directories
                file1 = os.path.join(tmpdir1, 'test1.txt')
                file2 = os.path.join(tmpdir2, 'test2.txt')
                
                Path(file1).write_text('content1')
                Path(file2).write_text('content2')
                
                # Wait for events
                time.sleep(2)
                
                monitor.stop()
                
                # Should have received events from both paths
                assert len(events_received) >= 2
                file_paths = [e.path for e in events_received]
                assert any(file1 in path for path in file_paths)
                assert any(file2 in path for path in file_paths)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
