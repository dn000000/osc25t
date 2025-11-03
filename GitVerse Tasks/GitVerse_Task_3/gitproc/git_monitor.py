"""
Git Monitor Module

Monitors Git repository for changes using file system events.
"""

import os
import time
from pathlib import Path
from typing import Callable, Optional
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent


class GitChangeHandler(FileSystemEventHandler):
    """Handles file system events for Git reference changes."""
    
    def __init__(self, callback: Callable[[], None]):
        """
        Initialize handler with callback.
        
        Args:
            callback: Function to call when changes are detected
        """
        super().__init__()
        self.callback = callback
        self.last_trigger = 0
        self.debounce_seconds = 1.0  # Debounce to avoid multiple triggers
    
    def on_modified(self, event: FileSystemEvent):
        """Handle file modification events."""
        if event.is_directory:
            return
        
        # Debounce: only trigger if enough time has passed
        current_time = time.time()
        if current_time - self.last_trigger < self.debounce_seconds:
            return
        
        self.last_trigger = current_time
        
        # Trigger callback
        try:
            self.callback()
        except Exception as e:
            print(f"Error in Git change callback: {e}")


class GitMonitor:
    """Monitors Git repository for changes using watchdog."""
    
    def __init__(self, repo_path: str, branch: str, on_change: Callable[[], None]):
        """
        Initialize Git monitor.
        
        Args:
            repo_path: Path to Git repository
            branch: Branch name to monitor
            on_change: Callback function to invoke when changes detected
        """
        self.repo_path = Path(repo_path)
        self.branch = branch
        self.on_change = on_change
        self.observer: Optional[Observer] = None
        self._running = False
    
    def start(self) -> bool:
        """
        Start monitoring the Git repository.
        
        Returns:
            True if monitoring started successfully, False otherwise
        """
        try:
            # Construct path to the branch ref file
            ref_path = self.repo_path / ".git" / "refs" / "heads" / self.branch
            
            # Check if ref file exists
            if not ref_path.exists():
                # Try checking if it's a packed ref
                packed_refs = self.repo_path / ".git" / "packed-refs"
                if not packed_refs.exists():
                    print(f"Branch ref not found: {ref_path}")
                    return False
                # For packed refs, monitor the packed-refs file
                watch_path = packed_refs.parent
            else:
                # Monitor the refs/heads directory
                watch_path = ref_path.parent
            
            # Create event handler
            event_handler = GitChangeHandler(self.on_change)
            
            # Create observer
            self.observer = Observer()
            self.observer.schedule(event_handler, str(watch_path), recursive=False)
            
            # Start observer
            self.observer.start()
            self._running = True
            
            return True
        except Exception as e:
            print(f"Error starting Git monitor: {e}")
            return False
    
    def stop(self):
        """Stop monitoring the Git repository."""
        if self.observer and self._running:
            self.observer.stop()
            self.observer.join(timeout=5)
            self._running = False
    
    def is_running(self) -> bool:
        """Check if monitor is running."""
        return self._running
