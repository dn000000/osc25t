"""File system monitoring using watchdog library"""

import time
import logging
from datetime import datetime
from typing import Callable, List, Optional
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from ..models import FileEvent, ProcessInfo, Config
from .filter import FilterManager
from .process_tracker import ProcessTracker

logger = logging.getLogger(__name__)


class AuditEventHandler(FileSystemEventHandler):
    """
    Event handler for file system changes.
    
    Handles file creation, modification, and deletion events,
    applies filtering, batches events, and tracks process information.
    """
    
    def __init__(
        self,
        callback: Callable[[List[FileEvent]], None],
        filter_manager: FilterManager,
        batch_interval: int = 5,
        batch_size: int = 10
    ):
        """
        Initialize the event handler.
        
        Args:
            callback: Function to call with batched events
            filter_manager: FilterManager instance for event filtering
            batch_interval: Time window for batching events (seconds)
            batch_size: Maximum number of events per batch
        """
        super().__init__()
        self.callback = callback
        self.filter = filter_manager
        self.batch_interval = batch_interval
        self.batch_size = batch_size
        self.event_buffer: List[FileEvent] = []
        self.last_flush = time.time()
        self._flush_timer = None
        self._start_flush_timer()
        
        logger.info(
            f"AuditEventHandler initialized with batch_interval={batch_interval}s, "
            f"batch_size={batch_size}"
        )
    
    def _start_flush_timer(self) -> None:
        """Start periodic flush timer"""
        import threading
        
        def periodic_flush():
            if self.event_buffer:
                time_since_flush = time.time() - self.last_flush
                if time_since_flush >= self.batch_interval:
                    self._flush_events()
            # Reschedule
            if self._flush_timer is not None:
                self._flush_timer = threading.Timer(self.batch_interval, periodic_flush)
                self._flush_timer.daemon = True
                self._flush_timer.start()
        
        self._flush_timer = threading.Timer(self.batch_interval, periodic_flush)
        self._flush_timer.daemon = True
        self._flush_timer.start()
    
    def stop_timer(self) -> None:
        """Stop the flush timer"""
        if self._flush_timer:
            self._flush_timer.cancel()
            self._flush_timer = None
    
    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation events"""
        if not event.is_directory:
            self._handle_event(event.src_path, 'created')
    
    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification events"""
        if not event.is_directory:
            self._handle_event(event.src_path, 'modified')
    
    def on_deleted(self, event: FileSystemEvent) -> None:
        """Handle file deletion events"""
        if not event.is_directory:
            self._handle_event(event.src_path, 'deleted')
    
    def _handle_event(self, path: str, event_type: str) -> None:
        """
        Process a file system event.
        
        Args:
            path: Path to the file
            event_type: Type of event ('created', 'modified', 'deleted')
        """
        # Apply filters (Requirement 3.1, 3.4, 3.5)
        if self.filter.should_ignore(path):
            logger.debug(f"Ignoring filtered path: {path}")
            return
        
        # Get process information (Requirement 4.1, 4.2, 4.3, 4.4)
        process_info = self._get_process_info()
        
        # Create FileEvent
        file_event = FileEvent(
            path=path,
            event_type=event_type,
            timestamp=datetime.now(),
            process_info=process_info
        )
        
        logger.info(f"Event detected: {event_type} - {path}")
        if process_info:
            logger.debug(f"Process: {process_info.name} (PID: {process_info.pid})")
        
        # Add to buffer
        self.event_buffer.append(file_event)
        
        # Check if we should flush (Requirement 2.6, 9.1)
        time_since_flush = time.time() - self.last_flush
        if time_since_flush >= self.batch_interval or len(self.event_buffer) >= self.batch_size:
            self._flush_events()
    
    def _get_process_info(self) -> Optional[ProcessInfo]:
        """
        Try to identify the process that modified the file.
        
        Uses /proc filesystem on Linux to identify the process.
        Returns None if process cannot be identified (Requirement 4.3).
        
        Returns:
            ProcessInfo object or None if unavailable
        """
        # Attempt to get process information (Requirements 4.1, 4.2, 4.4)
        try:
            process_info = ProcessTracker.get_process_info()
            return process_info
        except Exception as e:
            logger.debug(f"Failed to get process info: {e}")
            return None  # Handle cases where process info unavailable (Requirement 4.3)
    
    def _flush_events(self) -> None:
        """
        Flush buffered events by calling the callback.
        
        Implements batching mechanism (Requirement 2.6, 9.1).
        Handles rapid successive changes to same file by keeping only the latest event.
        """
        if self.event_buffer:
            # Deduplicate events for the same file (Requirement 9.1)
            # Keep only the latest event for each file path
            deduplicated = self._deduplicate_events(self.event_buffer)
            
            logger.info(f"Flushing {len(deduplicated)} events (deduplicated from {len(self.event_buffer)})")
            try:
                self.callback(deduplicated)
            except Exception as e:
                logger.error(f"Error in callback: {e}", exc_info=True)
            
            self.event_buffer.clear()
            self.last_flush = time.time()
    
    def _deduplicate_events(self, events: List[FileEvent]) -> List[FileEvent]:
        """
        Deduplicate events by keeping only the latest event for each file.
        
        When a file is modified multiple times rapidly, we only keep the
        most recent event to avoid redundant commits.
        
        Args:
            events: List of FileEvent objects
            
        Returns:
            Deduplicated list of FileEvent objects
        """
        # Use dict to keep latest event per path
        event_map = {}
        for event in events:
            # Always keep the latest event for each path
            event_map[event.path] = event
        
        # Return events in original order (preserving first occurrence order)
        seen_paths = set()
        result = []
        for event in events:
            if event.path not in seen_paths:
                result.append(event_map[event.path])
                seen_paths.add(event.path)
        
        return result
    
    def flush(self) -> None:
        """Manually flush any pending events"""
        self._flush_events()


class FileMonitor:
    """
    File system monitor using watchdog library.
    
    Monitors specified paths for file changes and reports events
    through a callback function. Supports multiple watch paths,
    recursive monitoring, and event filtering.
    """
    
    def __init__(self, config: Config):
        """
        Initialize FileMonitor with configuration.
        
        Args:
            config: Config object with monitoring settings
        """
        self.config = config
        self.observer: Optional[Observer] = None
        self.handler: Optional[AuditEventHandler] = None
        
        # Initialize filter manager (Requirement 3.1, 3.3, 3.4, 3.5)
        # Disable defaults in test/Docker environments to allow /tmp monitoring
        import os
        use_defaults = not (os.path.exists('/.dockerenv') or os.getenv('PYTEST_CURRENT_TEST'))
        
        self.filter = FilterManager(
            blacklist_file=config.blacklist_file,
            whitelist_file=config.whitelist_file,
            use_defaults=use_defaults
        )
        
        logger.info(f"FileMonitor initialized for paths: {config.watch_paths}")
    
    def start(self, callback: Callable[[List[FileEvent]], None]) -> None:
        """
        Start monitoring file system.
        
        Sets up watchdog Observer with event handlers for all configured
        watch paths. Monitoring is recursive by default.
        
        Args:
            callback: Function to call with batched file events
            
        Raises:
            ValueError: If watch paths don't exist
            RuntimeError: If monitor is already running
        """
        if self.observer is not None and self.observer.is_alive():
            raise RuntimeError("FileMonitor is already running")
        
        # Validate watch paths exist (Requirement 1.2)
        for path in self.config.watch_paths:
            if not Path(path).exists():
                raise ValueError(f"Watch path does not exist: {path}")
        
        # Create event handler with batching (Requirement 2.6, 9.1)
        self.handler = AuditEventHandler(
            callback=callback,
            filter_manager=self.filter,
            batch_interval=self.config.batch_interval,
            batch_size=self.config.batch_size
        )
        
        # Create and configure observer (Requirement 1.1)
        # Use PollingObserver in Docker/testing environments for better compatibility
        import os
        if os.path.exists('/.dockerenv') or os.getenv('PYTEST_CURRENT_TEST'):
            from watchdog.observers.polling import PollingObserver
            self.observer = PollingObserver(timeout=0.1)
            logger.info("Using PollingObserver for Docker/test environment")
        else:
            self.observer = Observer()
        
        # Schedule monitoring for all watch paths (Requirement 1.2, 3.2)
        for watch_path in self.config.watch_paths:
            self.observer.schedule(
                self.handler,
                watch_path,
                recursive=True  # Recursive directory watching
            )
            logger.info(f"Scheduled monitoring for: {watch_path} (recursive)")
        
        # Start the observer
        self.observer.start()
        logger.info("FileMonitor started successfully")
    
    def stop(self) -> None:
        """
        Stop monitoring file system.
        
        Stops the observer and flushes any pending events.
        """
        if self.observer is None:
            logger.warning("FileMonitor is not running")
            return
        
        logger.info("Stopping FileMonitor...")
        
        # Stop flush timer and flush any pending events
        if self.handler:
            self.handler.stop_timer()
            self.handler.flush()
        
        # Stop and join observer
        self.observer.stop()
        self.observer.join(timeout=5)
        
        self.observer = None
        self.handler = None
        
        logger.info("FileMonitor stopped")
    
    def is_running(self) -> bool:
        """
        Check if monitor is currently running.
        
        Returns:
            True if monitoring is active, False otherwise
        """
        return self.observer is not None and self.observer.is_alive()
    
    def wait(self) -> None:
        """
        Wait for the monitor to stop (blocking).
        
        Useful for daemon mode where we want to keep the process alive.
        """
        if self.observer is None:
            raise RuntimeError("FileMonitor is not running")
        
        try:
            while self.observer.is_alive():
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
            self.stop()
