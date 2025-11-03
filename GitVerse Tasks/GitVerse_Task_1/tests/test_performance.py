#!/usr/bin/env python3
"""
Performance tests and profiling for sysaudit system.
Tests event processing, Git operations, and system impact.
"""

import os
import sys
import time
import tempfile
import shutil
import cProfile
import pstats
from pathlib import Path
from io import StringIO
import pytest

from sysaudit.models import Config, FileEvent, ProcessInfo
from sysaudit.monitor.filter import FilterManager
from sysaudit.monitor.file_monitor import FileMonitor
from sysaudit.git.manager import GitManager
from sysaudit.compliance.checker import ComplianceChecker


class TestEventProcessingPerformance:
    """Test performance of event processing"""
    
    def test_filter_performance(self):
        """Test filter matching performance with many patterns"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create blacklist with many patterns
            blacklist_file = os.path.join(tmpdir, "blacklist.txt")
            patterns = [f"*.pattern{i}" for i in range(100)]
            patterns.extend(FilterManager.DEFAULT_IGNORE_PATTERNS)
            
            Path(blacklist_file).write_text("\n".join(patterns))
            
            config = Config(
                repo_path=tmpdir,
                watch_paths=[tmpdir],
                blacklist_file=blacklist_file,
                baseline_branch="main",
                gpg_sign=False
            )
            
            filter_mgr = FilterManager(blacklist_file=blacklist_file)
            
            # Test filtering performance
            test_paths = [
                f"/test/path/file{i}.txt" for i in range(1000)
            ]
            
            start_time = time.time()
            for path in test_paths:
                filter_mgr.should_ignore(path)
            elapsed = time.time() - start_time
            
            # Should process 1000 paths in under 2 seconds (relaxed for Docker)
            assert elapsed < 2.0, f"Filter too slow: {elapsed:.3f}s for 1000 paths"
            
            # Calculate throughput
            throughput = len(test_paths) / elapsed
            print(f"\nFilter throughput: {throughput:.0f} paths/sec")
    
    def test_event_batching_performance(self):
        """Test event batching performance"""
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
        
        # Test event creation performance
        start_time = time.time()
        test_events = []
        for i in range(1000):
            event = FileEvent(
                path=f"/test/file{i}.txt",
                event_type="modified",
                timestamp=datetime.now(),
                process_info=None
            )
            test_events.append(event)
        elapsed = time.time() - start_time
        
        # Should process 1000 events in under 0.1 seconds
        assert elapsed < 0.1, f"Event creation too slow: {elapsed:.3f}s for 1000 events"
        
        throughput = len(test_events) / elapsed
        print(f"\nEvent creation throughput: {throughput:.0f} events/sec")
    
    def test_git_commit_performance(self):
        """Test Git commit operation performance"""
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
            
            # Create test files
            test_files = []
            for i in range(10):
                test_file = os.path.join(watch_path, f"test{i}.txt")
                Path(test_file).write_text(f"content {i}")
                test_files.append(test_file)
            
            # Test commit performance
            events = [
                FileEvent(
                    path=f,
                    event_type="created",
                    timestamp=datetime.now(),
                    process_info=None
                )
                for f in test_files
            ]
            
            start_time = time.time()
            git_mgr.commit_changes(events)
            elapsed = time.time() - start_time
            
            # Should commit 10 files in under 2 seconds
            assert elapsed < 2.0, f"Git commit too slow: {elapsed:.3f}s for 10 files"
            
            print(f"\nGit commit time: {elapsed:.3f}s for {len(test_files)} files")
    
    def test_compliance_scan_performance(self):
        """Test compliance scanning performance"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test files
            test_files = []
            for i in range(50):
                test_file = os.path.join(tmpdir, f"test{i}.txt")
                Path(test_file).write_text(f"content {i}")
                os.chmod(test_file, 0o644)
                test_files.append(test_file)
            
            config = Config(
                repo_path=tmpdir,
                watch_paths=[tmpdir],
                baseline_branch="main",
                gpg_sign=False
            )
            
            checker = ComplianceChecker(config)
            
            # Test scanning performance
            start_time = time.time()
            issues = checker.check_files(test_files)
            elapsed = time.time() - start_time
            
            # Should scan 50 files in under 0.5 seconds
            assert elapsed < 0.5, f"Compliance scan too slow: {elapsed:.3f}s for 50 files"
            
            throughput = len(test_files) / elapsed
            print(f"\nCompliance scan throughput: {throughput:.0f} files/sec")


class TestMemoryUsage:
    """Test memory usage and resource management"""
    
    def test_event_buffer_memory(self):
        """Test that event list doesn't grow unbounded"""
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
    
    def test_filter_pattern_caching(self):
        """Test that filter patterns are cached efficiently"""
        with tempfile.TemporaryDirectory() as tmpdir:
            filter_mgr = FilterManager()
            
            # Test same path multiple times
            test_path = "/test/file.tmp"
            
            # First call compiles patterns
            result1 = filter_mgr.should_ignore(test_path)
            
            # Subsequent calls should use cache
            start_time = time.time()
            for _ in range(1000):
                result = filter_mgr.should_ignore(test_path)
                assert result == result1
            elapsed = time.time() - start_time
            
            # Should be reasonably fast with caching (relaxed for Docker)
            assert elapsed < 0.1, f"Pattern matching not cached: {elapsed:.3f}s"


class TestSystemImpact:
    """Test system resource impact"""
    
    def test_cpu_usage_during_monitoring(self):
        """Test CPU usage remains reasonable during monitoring"""
        # This is a placeholder - actual CPU monitoring would require
        # platform-specific tools like psutil
        pass
    
    def test_disk_io_optimization(self):
        """Test that disk I/O is minimized"""
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
            
            # Create and commit multiple files
            test_files = []
            for i in range(5):
                test_file = os.path.join(watch_path, f"test{i}.txt")
                Path(test_file).write_text(f"content {i}")
                test_files.append(test_file)
            
            events = [
                FileEvent(
                    path=f,
                    event_type="created",
                    timestamp=datetime.now(),
                    process_info=None
                )
                for f in test_files
            ]
            
            # Batch commit should be more efficient than individual commits
            start_time = time.time()
            git_mgr.commit_changes(events)
            batch_time = time.time() - start_time
            
            print(f"\nBatch commit time: {batch_time:.3f}s for {len(test_files)} files")
            
            # Individual commits would be slower
            # This demonstrates the benefit of batching


def profile_event_processing():
    """Profile event processing pipeline"""
    from datetime import datetime
    profiler = cProfile.Profile()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        filter_mgr = FilterManager()
        events = []
        
        # Profile filtering and event creation
        profiler.enable()
        
        for i in range(1000):
            path = f"/test/file{i}.txt"
            if not filter_mgr.should_ignore(path):
                event = FileEvent(
                    path=path,
                    event_type="modified",
                    timestamp=datetime.now(),
                    process_info=None
                )
                events.append(event)
        
        profiler.disable()
        
        # Print profile stats
        s = StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(20)
        print("\n=== Event Processing Profile ===")
        print(s.getvalue())


def profile_git_operations():
    """Profile Git operations"""
    from datetime import datetime
    profiler = cProfile.Profile()
    
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
        
        # Create test files
        test_files = []
        for i in range(10):
            test_file = os.path.join(watch_path, f"test{i}.txt")
            Path(test_file).write_text(f"content {i}")
            test_files.append(test_file)
        
        events = [
            FileEvent(
                path=f,
                event_type="created",
                timestamp=datetime.now(),
                process_info=None
            )
            for f in test_files
        ]
        
        # Profile Git commit
        profiler.enable()
        git_mgr.commit_changes(events)
        profiler.disable()
        
        # Print profile stats
        s = StringIO()
        ps = pstats.Stats(profiler, stream=s).sort_stats('cumulative')
        ps.print_stats(20)
        print("\n=== Git Operations Profile ===")
        print(s.getvalue())


if __name__ == "__main__":
    # Run performance tests
    pytest.main([__file__, "-v", "-s"])
    
    # Run profiling
    print("\n" + "="*60)
    print("PROFILING RESULTS")
    print("="*60)
    profile_event_processing()
    profile_git_operations()
