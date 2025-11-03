"""Example usage of FileMonitor for file system monitoring"""

import os
import time
import tempfile
from pathlib import Path

from sysaudit.models import Config
from sysaudit.monitor import FileMonitor


def example_callback(events):
    """Callback function to handle file events"""
    print(f"\n=== Received {len(events)} file event(s) ===")
    for event in events:
        print(f"  Event: {event.event_type}")
        print(f"  Path: {event.path}")
        print(f"  Time: {event.timestamp}")
        if event.process_info:
            print(f"  Process: {event.process_info.name} (PID: {event.process_info.pid})")
        else:
            print(f"  Process: unknown")
        print()


def main():
    """Demonstrate file monitoring functionality"""
    print("FileMonitor Example")
    print("=" * 60)
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"\nMonitoring directory: {tmpdir}")
        
        # Create configuration
        config = Config(
            repo_path=os.path.join(tmpdir, 'audit_repo'),
            watch_paths=[tmpdir],
            batch_interval=2,  # Batch events every 2 seconds
            batch_size=5       # Or when 5 events accumulate
        )
        
        # Create and start monitor
        monitor = FileMonitor(config)
        monitor.start(example_callback)
        
        print("\nMonitor started. Creating test files...")
        print("(Events will be batched and reported every 2 seconds or 5 events)")
        print()
        
        try:
            # Create some test files
            print("Creating files...")
            for i in range(3):
                test_file = os.path.join(tmpdir, f'test{i}.txt')
                Path(test_file).write_text(f'Content {i}')
                print(f"  Created: test{i}.txt")
                time.sleep(0.5)
            
            # Wait for events to be batched and processed
            time.sleep(3)
            
            # Modify a file
            print("\nModifying file...")
            test_file = os.path.join(tmpdir, 'test0.txt')
            Path(test_file).write_text('Modified content')
            print(f"  Modified: test0.txt")
            
            # Wait for event
            time.sleep(3)
            
            # Create a file that should be ignored
            print("\nCreating ignored file (*.tmp)...")
            ignored_file = os.path.join(tmpdir, 'ignored.tmp')
            Path(ignored_file).write_text('This should be ignored')
            print(f"  Created: ignored.tmp (should not trigger event)")
            
            # Wait to confirm no event
            time.sleep(3)
            
            # Delete a file
            print("\nDeleting file...")
            test_file = os.path.join(tmpdir, 'test1.txt')
            os.remove(test_file)
            print(f"  Deleted: test1.txt")
            
            # Wait for event
            time.sleep(3)
            
            print("\nExample complete. Stopping monitor...")
            
        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
        finally:
            monitor.stop()
            print("Monitor stopped.")


if __name__ == '__main__':
    main()
