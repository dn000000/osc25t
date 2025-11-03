"""Unit tests for event batching logic"""

import time
from datetime import datetime
from unittest.mock import Mock
import pytest

from sysaudit.models import FileEvent, ProcessInfo
from sysaudit.monitor.file_monitor import AuditEventHandler
from sysaudit.monitor.filter import FilterManager


class TestEventBatching:
    """Test suite for event batching mechanism (Requirement 2.6, 9.1)"""
    
    def test_batch_by_time_interval(self):
        """Test that events are batched after time interval expires"""
        callback = Mock()
        filter_mgr = FilterManager(use_defaults=False)
        
        # Set short batch interval for testing
        handler = AuditEventHandler(
            callback=callback,
            filter_manager=filter_mgr,
            batch_interval=1,  # 1 second
            batch_size=10
        )
        
        # Add events
        handler._handle_event('/test/file1.txt', 'created')
        handler._handle_event('/test/file2.txt', 'modified')
        
        # Should not have called callback yet
        callback.assert_not_called()
        
        # Wait for batch interval to expire
        time.sleep(1.1)
        
        # Add another event to trigger flush check
        handler._handle_event('/test/file3.txt', 'created')
        
        # Should have flushed previous events
        assert callback.call_count >= 1
    
    def test_batch_by_size_limit(self):
        """Test that events are batched when size limit is reached"""
        callback = Mock()
        filter_mgr = FilterManager(use_defaults=False)
        
        # Set small batch size for testing
        handler = AuditEventHandler(
            callback=callback,
            filter_manager=filter_mgr,
            batch_interval=60,  # Long interval
            batch_size=3  # Small batch size
        )
        
        # Add events up to batch size
        handler._handle_event('/test/file1.txt', 'created')
        handler._handle_event('/test/file2.txt', 'created')
        
        # Should not have called callback yet
        callback.assert_not_called()
        
        # Add one more to reach batch size
        handler._handle_event('/test/file3.txt', 'created')
        
        # Should have flushed
        callback.assert_called_once()
        
        # Verify all 3 events were in the batch
        events = callback.call_args[0][0]
        assert len(events) == 3
    
    def test_deduplication_same_file_multiple_changes(self):
        """Test that rapid changes to same file are deduplicated (Requirement 9.1)"""
        callback = Mock()
        filter_mgr = FilterManager(use_defaults=False)
        
        handler = AuditEventHandler(
            callback=callback,
            filter_manager=filter_mgr,
            batch_interval=1,
            batch_size=10
        )
        
        # Modify same file multiple times rapidly
        handler._handle_event('/test/file.txt', 'created')
        handler._handle_event('/test/file.txt', 'modified')
        handler._handle_event('/test/file.txt', 'modified')
        handler._handle_event('/test/file.txt', 'modified')
        
        # Manually flush
        handler._flush_events()
        
        # Should have called callback once
        callback.assert_called_once()
        
        # Should only have one event for the file (latest one)
        events = callback.call_args[0][0]
        assert len(events) == 1
        assert events[0].path == '/test/file.txt'
        assert events[0].event_type == 'modified'
    
    def test_deduplication_preserves_different_files(self):
        """Test that deduplication preserves events for different files"""
        callback = Mock()
        filter_mgr = FilterManager(use_defaults=False)
        
        handler = AuditEventHandler(
            callback=callback,
            filter_manager=filter_mgr,
            batch_interval=1,
            batch_size=10
        )
        
        # Add events for different files
        handler._handle_event('/test/file1.txt', 'created')
        handler._handle_event('/test/file2.txt', 'created')
        handler._handle_event('/test/file1.txt', 'modified')
        handler._handle_event('/test/file3.txt', 'created')
        
        # Manually flush
        handler._flush_events()
        
        # Should have 3 events (one per unique file)
        events = callback.call_args[0][0]
        assert len(events) == 3
        
        # Verify paths
        paths = {e.path for e in events}
        assert paths == {'/test/file1.txt', '/test/file2.txt', '/test/file3.txt'}
    
    def test_deduplication_keeps_latest_event(self):
        """Test that deduplication keeps the most recent event"""
        events = [
            FileEvent(
                path='/test/file.txt',
                event_type='created',
                timestamp=datetime(2024, 1, 1, 10, 0, 0)
            ),
            FileEvent(
                path='/test/file.txt',
                event_type='modified',
                timestamp=datetime(2024, 1, 1, 10, 0, 1)
            ),
            FileEvent(
                path='/test/file.txt',
                event_type='modified',
                timestamp=datetime(2024, 1, 1, 10, 0, 2)
            ),
        ]
        
        callback = Mock()
        filter_mgr = FilterManager(use_defaults=False)
        handler = AuditEventHandler(callback, filter_mgr)
        
        deduplicated = handler._deduplicate_events(events)
        
        assert len(deduplicated) == 1
        assert deduplicated[0].event_type == 'modified'
        assert deduplicated[0].timestamp == datetime(2024, 1, 1, 10, 0, 2)
    
    def test_empty_buffer_flush(self):
        """Test that flushing empty buffer doesn't call callback"""
        callback = Mock()
        filter_mgr = FilterManager(use_defaults=False)
        
        handler = AuditEventHandler(callback, filter_mgr)
        
        # Flush empty buffer
        handler._flush_events()
        
        # Should not have called callback
        callback.assert_not_called()
    
    def test_manual_flush(self):
        """Test manual flush of pending events"""
        callback = Mock()
        filter_mgr = FilterManager(use_defaults=False)
        
        handler = AuditEventHandler(
            callback=callback,
            filter_manager=filter_mgr,
            batch_interval=60,  # Long interval
            batch_size=100  # Large batch size
        )
        
        # Add events
        handler._handle_event('/test/file1.txt', 'created')
        handler._handle_event('/test/file2.txt', 'created')
        
        # Should not have auto-flushed
        callback.assert_not_called()
        
        # Manual flush
        handler.flush()
        
        # Should have called callback
        callback.assert_called_once()
        events = callback.call_args[0][0]
        assert len(events) == 2
    
    def test_buffer_cleared_after_flush(self):
        """Test that event buffer is cleared after flush"""
        callback = Mock()
        filter_mgr = FilterManager(use_defaults=False)
        
        handler = AuditEventHandler(callback, filter_mgr)
        
        # Add events
        handler._handle_event('/test/file.txt', 'created')
        assert len(handler.event_buffer) == 1
        
        # Flush
        handler._flush_events()
        
        # Buffer should be empty
        assert len(handler.event_buffer) == 0
    
    def test_callback_exception_handling(self):
        """Test that callback exceptions don't crash the handler"""
        def failing_callback(events):
            raise Exception("Callback error")
        
        filter_mgr = FilterManager(use_defaults=False)
        handler = AuditEventHandler(failing_callback, filter_mgr)
        
        # Add event and flush
        handler._handle_event('/test/file.txt', 'created')
        
        # Should not raise exception
        handler._flush_events()
        
        # Buffer should still be cleared
        assert len(handler.event_buffer) == 0
    
    def test_batch_interval_reset_after_flush(self):
        """Test that batch interval timer resets after flush"""
        callback = Mock()
        filter_mgr = FilterManager(use_defaults=False)
        
        handler = AuditEventHandler(
            callback=callback,
            filter_manager=filter_mgr,
            batch_interval=1,
            batch_size=10
        )
        
        # Add event and flush
        handler._handle_event('/test/file1.txt', 'created')
        initial_flush_time = handler.last_flush
        
        time.sleep(0.1)
        handler._flush_events()
        
        # last_flush should be updated
        assert handler.last_flush > initial_flush_time
    
    def test_deduplication_order_preservation(self):
        """Test that deduplication preserves first occurrence order"""
        events = [
            FileEvent(path='/test/a.txt', event_type='created', timestamp=datetime.now()),
            FileEvent(path='/test/b.txt', event_type='created', timestamp=datetime.now()),
            FileEvent(path='/test/a.txt', event_type='modified', timestamp=datetime.now()),
            FileEvent(path='/test/c.txt', event_type='created', timestamp=datetime.now()),
            FileEvent(path='/test/b.txt', event_type='modified', timestamp=datetime.now()),
        ]
        
        callback = Mock()
        filter_mgr = FilterManager(use_defaults=False)
        handler = AuditEventHandler(callback, filter_mgr)
        
        deduplicated = handler._deduplicate_events(events)
        
        # Should have 3 events in order: a, b, c
        assert len(deduplicated) == 3
        assert deduplicated[0].path == '/test/a.txt'
        assert deduplicated[1].path == '/test/b.txt'
        assert deduplicated[2].path == '/test/c.txt'
        
        # Should have latest event types
        assert deduplicated[0].event_type == 'modified'
        assert deduplicated[1].event_type == 'modified'
        assert deduplicated[2].event_type == 'created'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
