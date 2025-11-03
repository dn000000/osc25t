"""Example usage of RollbackManager for file restoration"""

import tempfile
from pathlib import Path
from git import Repo

from sysaudit.git.rollback import RollbackManager, RollbackError


def example_basic_rollback():
    """Example: Basic file rollback"""
    print("=== Basic File Rollback ===\n")
    
    # Create a temporary repository for demonstration
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / 'audit_repo'
        repo_path.mkdir()
        
        # Initialize repository
        repo = Repo.init(repo_path)
        with repo.config_writer() as config:
            config.set_value('user', 'name', 'Demo User')
            config.set_value('user', 'email', 'demo@example.com')
        
        # Create a file and commit it
        test_file = repo_path / 'config.txt'
        test_file.write_text('Version 1: Initial configuration')
        repo.index.add([str(test_file)])
        commit1 = repo.index.commit('Initial version')
        print(f"Created commit 1: {commit1.hexsha[:8]}")
        
        # Modify the file
        test_file.write_text('Version 2: Updated configuration')
        repo.index.add([str(test_file)])
        commit2 = repo.index.commit('Updated version')
        print(f"Created commit 2: {commit2.hexsha[:8]}")
        
        # Modify again
        test_file.write_text('Version 3: Latest configuration')
        repo.index.add([str(test_file)])
        repo.index.commit('Latest version')
        print(f"Current content: {test_file.read_text()}\n")
        
        repo.close()
        
        # Initialize RollbackManager
        rollback_mgr = RollbackManager(str(repo_path))
        
        # Rollback to version 1
        print(f"Rolling back to commit {commit1.hexsha[:8]}...")
        result = rollback_mgr.rollback_file(
            'config.txt',
            commit1.hexsha,
            dry_run=False
        )
        
        print(f"Success: {result['success']}")
        print(f"Message: {result['message']}")
        print(f"Backup: {result['backup_path']}")
        print(f"Restored content: {test_file.read_text()}\n")


def example_dry_run():
    """Example: Dry-run mode to preview rollback"""
    print("=== Dry-Run Mode ===\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / 'audit_repo'
        repo_path.mkdir()
        
        # Setup repository
        repo = Repo.init(repo_path)
        with repo.config_writer() as config:
            config.set_value('user', 'name', 'Demo User')
            config.set_value('user', 'email', 'demo@example.com')
        
        test_file = repo_path / 'important.conf'
        test_file.write_text('Original content')
        repo.index.add([str(test_file)])
        commit1 = repo.index.commit('Original')
        
        test_file.write_text('Modified content')
        repo.index.add([str(test_file)])
        repo.index.commit('Modified')
        
        repo.close()
        
        # Dry-run rollback
        rollback_mgr = RollbackManager(str(repo_path))
        result = rollback_mgr.rollback_file(
            'important.conf',
            commit1.hexsha,
            dry_run=True
        )
        
        print(f"Dry run: {result['dry_run']}")
        print(f"Message:\n{result['message']}\n")
        print(f"File unchanged: {test_file.read_text()}\n")


def example_file_history():
    """Example: View file history before rollback"""
    print("=== File History ===\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / 'audit_repo'
        repo_path.mkdir()
        
        # Setup repository with multiple commits
        repo = Repo.init(repo_path)
        with repo.config_writer() as config:
            config.set_value('user', 'name', 'Demo User')
            config.set_value('user', 'email', 'demo@example.com')
        
        test_file = repo_path / 'app.conf'
        
        for i in range(1, 6):
            test_file.write_text(f'Configuration version {i}')
            repo.index.add([str(test_file)])
            repo.index.commit(f'Update to version {i}')
        
        repo.close()
        
        # Get file history
        rollback_mgr = RollbackManager(str(repo_path))
        history = rollback_mgr.get_file_history('app.conf', max_count=10)
        
        print(f"Found {len(history)} commits for app.conf:\n")
        for entry in history:
            print(f"Commit: {entry['commit_short']}")
            print(f"Author: {entry['author']}")
            print(f"Date: {entry['date']}")
            print(f"Message: {entry['message']}")
            print()


def example_validation():
    """Example: Validate commit and file existence"""
    print("=== Validation ===\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / 'audit_repo'
        repo_path.mkdir()
        
        # Setup repository
        repo = Repo.init(repo_path)
        with repo.config_writer() as config:
            config.set_value('user', 'name', 'Demo User')
            config.set_value('user', 'email', 'demo@example.com')
        
        test_file = repo_path / 'data.txt'
        test_file.write_text('Data')
        repo.index.add([str(test_file)])
        commit = repo.index.commit('Add data')
        
        repo.close()
        
        # Validate
        rollback_mgr = RollbackManager(str(repo_path))
        
        # Check if commit exists
        print(f"Commit {commit.hexsha[:8]} exists: {rollback_mgr.validate_commit(commit.hexsha)}")
        print(f"Commit 'invalid123' exists: {rollback_mgr.validate_commit('invalid123')}")
        
        # Check if file exists in commit
        print(f"File 'data.txt' in commit: {rollback_mgr.validate_file_in_commit('data.txt', commit.hexsha)}")
        print(f"File 'missing.txt' in commit: {rollback_mgr.validate_file_in_commit('missing.txt', commit.hexsha)}\n")


def example_error_handling():
    """Example: Error handling"""
    print("=== Error Handling ===\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / 'audit_repo'
        repo_path.mkdir()
        
        # Setup repository
        repo = Repo.init(repo_path)
        with repo.config_writer() as config:
            config.set_value('user', 'name', 'Demo User')
            config.set_value('user', 'email', 'demo@example.com')
        
        test_file = repo_path / 'file.txt'
        test_file.write_text('Content')
        repo.index.add([str(test_file)])
        repo.index.commit('Add file')
        
        repo.close()
        
        rollback_mgr = RollbackManager(str(repo_path))
        
        # Try to rollback with invalid commit
        try:
            rollback_mgr.rollback_file('file.txt', 'invalid_commit')
        except RollbackError as e:
            print(f"Expected error: {e}\n")
        
        # Try to rollback non-existent file
        try:
            rollback_mgr.rollback_file('nonexistent.txt', 'HEAD')
        except RollbackError as e:
            print(f"Expected error: {e}\n")


def example_list_files():
    """Example: List files in a commit"""
    print("=== List Files in Commit ===\n")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_path = Path(tmpdir) / 'audit_repo'
        repo_path.mkdir()
        
        # Setup repository with multiple files
        repo = Repo.init(repo_path)
        with repo.config_writer() as config:
            config.set_value('user', 'name', 'Demo User')
            config.set_value('user', 'email', 'demo@example.com')
        
        # Create multiple files
        (repo_path / 'config.yaml').write_text('config: value')
        (repo_path / 'data.json').write_text('{"key": "value"}')
        (repo_path / 'README.md').write_text('# Project')
        
        repo.index.add(['config.yaml', 'data.json', 'README.md'])
        commit = repo.index.commit('Add project files')
        
        repo.close()
        
        # List files
        rollback_mgr = RollbackManager(str(repo_path))
        files = rollback_mgr.list_files_in_commit(commit.hexsha)
        
        print(f"Files in commit {commit.hexsha[:8]}:")
        for file in files:
            print(f"  - {file}")
        print()


if __name__ == '__main__':
    print("RollbackManager Usage Examples\n")
    print("=" * 50)
    print()
    
    example_basic_rollback()
    example_dry_run()
    example_file_history()
    example_validation()
    example_error_handling()
    example_list_files()
    
    print("=" * 50)
    print("\nAll examples completed!")
