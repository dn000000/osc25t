"""
Example usage scenarios for GitConfig
"""
import sys
import time
import threading
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from gitconfig_core import GitConfigStore


def example_basic_operations():
    """Example: Basic set/get/delete operations"""
    print("=== Basic Operations ===")
    store = GitConfigStore('./example_data/basic')
    
    # Set a key
    store.set('/app/db/host', 'localhost')
    print(f"Set /app/db/host = localhost")
    
    # Get the key
    value = store.get('/app/db/host')
    print(f"Get /app/db/host = {value}")
    
    # Delete the key
    store.delete('/app/db/host')
    print(f"Deleted /app/db/host")
    
    # Try to get deleted key
    value = store.get('/app/db/host')
    print(f"Get /app/db/host after delete = {value}")
    
    store.stop()
    print()


def example_hierarchical_keys():
    """Example: Hierarchical key structure"""
    print("=== Hierarchical Keys ===")
    store = GitConfigStore('./example_data/hierarchical')
    
    # Set multiple keys in hierarchy
    store.set('/app/db/host', 'localhost')
    store.set('/app/db/port', '5432')
    store.set('/app/api/endpoint', 'http://api.example.com')
    store.set('/system/hostname', 'server1')
    
    # List keys
    print("Keys in /app/db/:")
    for key in store.list_keys('/app/db/'):
        print(f"  {key}")
    
    print("\nAll keys in /app/ (recursive):")
    for key in store.list_keys('/app/', recursive=True):
        print(f"  {key}")
    
    store.stop()
    print()


def example_versioning():
    """Example: Version history and retrieval"""
    print("=== Versioning ===")
    store = GitConfigStore('./example_data/versioning')
    
    # Set key multiple times
    store.set('/config/version', 'v1.0')
    time.sleep(0.1)
    
    # Get commit hash
    commits = list(store.repo.iter_commits(paths='config/version'))
    first_commit = commits[-1].hexsha if commits else None
    
    store.set('/config/version', 'v2.0')
    time.sleep(0.1)
    store.set('/config/version', 'v3.0')
    
    # Get current version
    current = store.get('/config/version')
    print(f"Current version: {current}")
    
    # Get old version
    if first_commit:
        old = store.get('/config/version', commit=first_commit)
        print(f"First version (commit {first_commit[:8]}): {old}")
    
    # Show history
    print("\nHistory:")
    for entry in store.history('/config/version'):
        print(f"  {entry['commit']} - {entry['date'][:19]} - {entry['message']}")
    
    store.stop()
    print()


def example_watch():
    """Example: Watch for key changes"""
    print("=== Watch Mechanism ===")
    store = GitConfigStore('./example_data/watch')
    
    store.set('/status', 'idle')
    
    def watcher():
        print("Watcher: Waiting for /status to change...")
        if store.watch('/status', timeout=10):
            new_value = store.get('/status')
            print(f"Watcher: /status changed to '{new_value}'!")
        else:
            print("Watcher: Timeout")
    
    # Start watcher in background
    thread = threading.Thread(target=watcher)
    thread.start()
    
    # Change the key after a delay
    time.sleep(2)
    print("Main: Changing /status to 'active'")
    store.set('/status', 'active')
    
    thread.join()
    store.stop()
    print()


def example_ttl():
    """Example: TTL (Time-To-Live)"""
    print("=== TTL (Time-To-Live) ===")
    store = GitConfigStore('./example_data/ttl')
    store.start_ttl_cleanup()
    
    # Set key with 3 second TTL
    store.set('/session/token', 'abc123', ttl=3)
    print("Set /session/token with TTL=3 seconds")
    
    # Get immediately
    value = store.get('/session/token')
    print(f"Immediately: {value}")
    
    # Wait and try again
    print("Waiting 4 seconds...")
    time.sleep(4)
    
    value = store.get('/session/token')
    print(f"After TTL expired: {value}")
    
    store.stop()
    print()


def example_cas():
    """Example: Compare-and-Swap"""
    print("=== Compare-and-Swap (CAS) ===")
    store = GitConfigStore('./example_data/cas')
    
    # Initialize counter
    store.set('/counter', '0')
    print("Initialized /counter = 0")
    
    # Successful CAS
    success = store.cas('/counter', '0', '1')
    print(f"CAS /counter: 0 -> 1: {success}")
    print(f"Current value: {store.get('/counter')}")
    
    # Failed CAS (wrong expected value)
    success = store.cas('/counter', '0', '2')
    print(f"CAS /counter: 0 -> 2: {success} (expected to fail)")
    print(f"Current value: {store.get('/counter')}")
    
    # Successful CAS with correct expected value
    success = store.cas('/counter', '1', '2')
    print(f"CAS /counter: 1 -> 2: {success}")
    print(f"Current value: {store.get('/counter')}")
    
    store.stop()
    print()


if __name__ == '__main__':
    print("GitConfig Example Usage\n")
    
    example_basic_operations()
    example_hierarchical_keys()
    example_versioning()
    example_watch()
    example_ttl()
    example_cas()
    
    print("All examples completed!")
