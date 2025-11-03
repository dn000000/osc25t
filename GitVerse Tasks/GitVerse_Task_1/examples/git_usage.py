"""Example usage of GitManager for tracking file changes"""

import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from sysaudit.git import GitManager
from sysaudit.models import Config, FileEvent, ProcessInfo


def main():
    """Demonstrate GitManager functionality"""
    
    # Create temporary directories for demo
    repo_dir = tempfile.mkdtemp(prefix='demo_repo_')
    watch_dir = tempfile.mkdtemp(prefix='demo_watch_')
    
    print(f"Repository: {repo_dir}")
    print(f"Watch directory: {watch_dir}")
    print()
    
    try:
        # Create configuration
        config = Config(
            repo_path=repo_dir,
            watch_paths=[watch_dir],
            baseline_branch='main',
            gpg_sign=False
        )
        
        # Initialize GitManager
        git_manager = GitManager(config)
        
        # Initialize repository
        print("1. Initializing Git repository...")
        git_manager.init_repo()
        print(f"   ✓ Repository initialized at {repo_dir}")
        print(f"   ✓ Baseline branch: {config.baseline_branch}")
        print()
        
        # Create a test file
        print("2. Creating test file...")
        test_file = Path(watch_dir) / 'config.txt'
        test_file.write_text('initial configuration')
        print(f"   ✓ Created: {test_file}")
        print()
        
        # Commit the file creation
        print("3. Committing file creation...")
        event1 = FileEvent(
            path=str(test_file),
            event_type='created',
            timestamp=datetime.now(),
            process_info=ProcessInfo(
                pid=1234,
                name='demo',
                cmdline='python demo.py'
            )
        )
        commit1 = git_manager.commit_changes([event1])
        print(f"   ✓ Commit created: {commit1.hexsha[:8]}")
        print(f"   ✓ Message: {commit1.message.split(chr(10))[0]}")
        print()
        
        # Modify the file
        print("4. Modifying test file...")
        test_file.write_text('updated configuration')
        print(f"   ✓ Modified: {test_file}")
        print()
        
        # Commit the modification
        print("5. Committing file modification...")
        event2 = FileEvent(
            path=str(test_file),
            event_type='modified',
            timestamp=datetime.now()
        )
        commit2 = git_manager.commit_changes([event2])
        print(f"   ✓ Commit created: {commit2.hexsha[:8]}")
        print(f"   ✓ Message: {commit2.message.split(chr(10))[0]}")
        print()
        
        # Create multiple files for batch commit
        print("6. Creating multiple files...")
        files = []
        events = []
        for i in range(3):
            file_path = Path(watch_dir) / f'file{i}.txt'
            file_path.write_text(f'content {i}')
            files.append(file_path)
            events.append(FileEvent(
                path=str(file_path),
                event_type='created',
                timestamp=datetime.now()
            ))
        print(f"   ✓ Created {len(files)} files")
        print()
        
        # Batch commit
        print("7. Committing batch changes...")
        commit3 = git_manager.commit_changes(events)
        print(f"   ✓ Batch commit created: {commit3.hexsha[:8]}")
        print(f"   ✓ Message: {commit3.message.split(chr(10))[0]}")
        print()
        
        # Show commit history
        print("8. Commit history:")
        commits = list(git_manager.repo.iter_commits(max_count=5))
        for i, commit in enumerate(commits, 1):
            print(f"   {i}. {commit.hexsha[:8]} - {commit.message.split(chr(10))[0]}")
        print()
        
        # Get latest commit
        latest = git_manager.get_latest_commit()
        print(f"9. Latest commit: {latest.hexsha[:8]}")
        print()
        
        # Get baseline commit
        baseline = git_manager.get_baseline_commit()
        print(f"10. Baseline commit: {baseline.hexsha[:8]}")
        print()
        
        # GPG signing status
        gpg_status = git_manager.get_gpg_signing_status()
        print("11. GPG signing status:")
        print(f"    Enabled: {gpg_status['enabled']}")
        print(f"    Configured in Git: {gpg_status['configured_in_git']}")
        print(f"    Signing key: {gpg_status['signing_key']}")
        print()
        
        print("✓ Demo completed successfully!")
        
    finally:
        # Cleanup
        print("\nCleaning up temporary directories...")
        shutil.rmtree(repo_dir, ignore_errors=True)
        shutil.rmtree(watch_dir, ignore_errors=True)
        print("✓ Cleanup complete")


if __name__ == '__main__':
    main()
