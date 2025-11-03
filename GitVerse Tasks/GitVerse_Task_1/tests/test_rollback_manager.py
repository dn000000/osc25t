"""Tests for RollbackManager"""

import os
import tempfile
import shutil
from pathlib import Path
import pytest
from git import Repo

from sysaudit.git.rollback import RollbackManager, RollbackError


class TestRollbackManager:
    """Test suite for RollbackManager"""
    
    @pytest.fixture
    def temp_repo(self):
        """Create a temporary Git repository for testing"""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = Path(tmpdir) / 'test_repo'
            repo_path.mkdir()
            
            # Initialize Git repository
            repo = Repo.init(repo_path)
            
            # Configure Git user
            with repo.config_writer() as config:
                config.set_value('user', 'name', 'Test User')
                config.set_value('user', 'email', 'test@example.com')
            
            # Create initial commit
            readme = repo_path / 'README.md'
            readme.write_text('Initial content')
            repo.index.add([str(readme)])
            repo.index.commit('Initial commit')
            
            # Close the repo to release file handles
            repo.close()
            
            yield repo_path
    
    @pytest.fixture
    def rollback_manager(self, temp_repo):
        """Create RollbackManager instance"""
        return RollbackManager(str(temp_repo))
    
    def test_init_with_valid_repo(self, temp_repo):
        """Test initialization with valid repository"""
        manager = RollbackManager(str(temp_repo))
        assert manager.repo is not None
        assert manager.repo_path == temp_repo
    
    def test_init_with_invalid_path(self):
        """Test initialization with non-existent path"""
        with pytest.raises(RollbackError, match="Repository path does not exist"):
            RollbackManager('/nonexistent/path')
    
    def test_init_with_non_git_directory(self):
        """Test initialization with directory that's not a Git repo"""
        with tempfile.TemporaryDirectory() as tmpdir:
            with pytest.raises(RollbackError, match="Not a Git repository"):
                RollbackManager(tmpdir)
    
    def test_validate_commit_exists(self, rollback_manager, temp_repo):
        """Test validating existing commit"""
        repo = Repo(temp_repo)
        commit = repo.head.commit
        
        assert rollback_manager.validate_commit(commit.hexsha) is True
        assert rollback_manager.validate_commit('HEAD') is True
    
    def test_validate_commit_not_exists(self, rollback_manager):
        """Test validating non-existent commit"""
        assert rollback_manager.validate_commit('nonexistent123') is False
    
    def test_validate_file_in_commit(self, rollback_manager, temp_repo):
        """Test validating file exists in commit"""
        assert rollback_manager.validate_file_in_commit('README.md', 'HEAD') is True
        assert rollback_manager.validate_file_in_commit('nonexistent.txt', 'HEAD') is False
    
    def test_rollback_file_dry_run(self, rollback_manager, temp_repo):
        """Test rollback in dry-run mode"""
        # Create a file and commit it
        repo = Repo(temp_repo)
        test_file = temp_repo / 'test.txt'
        test_file.write_text('Version 1')
        repo.index.add([str(test_file)])
        commit1 = repo.index.commit('Add test file')
        
        # Modify the file
        test_file.write_text('Version 2')
        repo.index.add([str(test_file)])
        repo.index.commit('Modify test file')
        repo.close()
        
        # Rollback in dry-run mode
        result = rollback_manager.rollback_file(
            'test.txt',
            commit1.hexsha,
            dry_run=True
        )
        
        assert result['success'] is True
        assert result['dry_run'] is True
        assert 'DRY RUN' in result['message']
        
        # File should not have changed
        assert test_file.read_text() == 'Version 2'
    
    def test_rollback_file_success(self, rollback_manager, temp_repo):
        """Test successful file rollback"""
        # Create a file and commit it
        repo = Repo(temp_repo)
        test_file = temp_repo / 'test.txt'
        test_file.write_text('Version 1')
        repo.index.add([str(test_file)])
        commit1 = repo.index.commit('Add test file')
        
        # Modify the file
        test_file.write_text('Version 2')
        repo.index.add([str(test_file)])
        repo.index.commit('Modify test file')
        repo.close()
        
        # Verify current content
        assert test_file.read_text() == 'Version 2'
        
        # Rollback to version 1
        result = rollback_manager.rollback_file(
            'test.txt',
            commit1.hexsha,
            dry_run=False
        )
        
        assert result['success'] is True
        assert result['dry_run'] is False
        assert result['backup_path'] is not None
        
        # File should be rolled back
        assert test_file.read_text() == 'Version 1'
        
        # Backup should exist
        backup_path = Path(result['backup_path'])
        assert backup_path.exists()
        assert backup_path.read_text() == 'Version 2'
    
    def test_rollback_file_without_backup(self, rollback_manager, temp_repo):
        """Test rollback without creating backup"""
        # Create a file and commit it
        repo = Repo(temp_repo)
        test_file = temp_repo / 'test.txt'
        test_file.write_text('Version 1')
        repo.index.add([str(test_file)])
        commit1 = repo.index.commit('Add test file')
        
        # Modify the file
        test_file.write_text('Version 2')
        repo.index.add([str(test_file)])
        repo.index.commit('Modify test file')
        repo.close()
        
        # Rollback without backup
        result = rollback_manager.rollback_file(
            'test.txt',
            commit1.hexsha,
            dry_run=False,
            create_backup=False
        )
        
        assert result['success'] is True
        assert result['backup_path'] is None
        assert test_file.read_text() == 'Version 1'
    
    def test_rollback_nonexistent_commit(self, rollback_manager):
        """Test rollback with non-existent commit"""
        with pytest.raises(RollbackError, match="Commit .* not found"):
            rollback_manager.rollback_file(
                'test.txt',
                'nonexistent123',
                dry_run=False
            )
    
    def test_rollback_file_not_in_commit(self, rollback_manager, temp_repo):
        """Test rollback when file doesn't exist in commit"""
        repo = Repo(temp_repo)
        commit = repo.head.commit
        
        with pytest.raises(RollbackError, match="File .* not found in commit"):
            rollback_manager.rollback_file(
                'nonexistent.txt',
                commit.hexsha,
                dry_run=False
            )
    
    def test_get_file_history(self, rollback_manager, temp_repo):
        """Test getting file history"""
        # Create a file with multiple commits
        repo = Repo(temp_repo)
        test_file = temp_repo / 'history.txt'
        
        test_file.write_text('Version 1')
        repo.index.add([str(test_file)])
        repo.index.commit('Version 1')
        
        test_file.write_text('Version 2')
        repo.index.add([str(test_file)])
        repo.index.commit('Version 2')
        
        test_file.write_text('Version 3')
        repo.index.add([str(test_file)])
        repo.index.commit('Version 3')
        repo.close()
        
        # Get history
        history = rollback_manager.get_file_history('history.txt', max_count=10)
        
        assert len(history) == 3
        assert all('commit' in h for h in history)
        assert all('author' in h for h in history)
        assert all('date' in h for h in history)
        assert all('message' in h for h in history)
        
        # Check order (most recent first)
        assert 'Version 3' in history[0]['message']
        assert 'Version 2' in history[1]['message']
        assert 'Version 1' in history[2]['message']
    
    def test_get_file_history_nonexistent(self, rollback_manager):
        """Test getting history for non-existent file"""
        history = rollback_manager.get_file_history('nonexistent.txt')
        assert history == []
    
    def test_list_files_in_commit(self, rollback_manager, temp_repo):
        """Test listing files in a commit"""
        # Create multiple files
        repo = Repo(temp_repo)
        
        file1 = temp_repo / 'file1.txt'
        file2 = temp_repo / 'file2.txt'
        
        file1.write_text('Content 1')
        file2.write_text('Content 2')
        
        repo.index.add([str(file1), str(file2)])
        commit = repo.index.commit('Add files')
        repo.close()
        
        # List files
        files = rollback_manager.list_files_in_commit(commit.hexsha)
        
        assert 'file1.txt' in files
        assert 'file2.txt' in files
        assert 'README.md' in files  # From initial commit
    
    def test_list_files_invalid_commit(self, rollback_manager):
        """Test listing files with invalid commit"""
        with pytest.raises(RollbackError, match="Failed to list files"):
            rollback_manager.list_files_in_commit('invalid123')
    
    def test_get_repo_relative_path(self, rollback_manager):
        """Test path conversion to repository-relative format"""
        # Unix-style absolute path
        assert rollback_manager._get_repo_relative_path('/etc/config.txt') == 'etc/config.txt'
        
        # Relative path
        assert rollback_manager._get_repo_relative_path('etc/config.txt') == 'etc/config.txt'
        
        # Path with backslashes (Windows-style)
        assert rollback_manager._get_repo_relative_path('etc\\config.txt') == 'etc/config.txt'
    
    def test_rollback_with_subdirectory(self, rollback_manager, temp_repo):
        """Test rollback of file in subdirectory"""
        # Create file in subdirectory
        repo = Repo(temp_repo)
        subdir = temp_repo / 'subdir'
        subdir.mkdir()
        
        test_file = subdir / 'test.txt'
        test_file.write_text('Version 1')
        repo.index.add([str(test_file)])
        commit1 = repo.index.commit('Add file in subdir')
        
        # Modify the file
        test_file.write_text('Version 2')
        repo.index.add([str(test_file)])
        repo.index.commit('Modify file in subdir')
        repo.close()
        
        # Rollback
        result = rollback_manager.rollback_file(
            'subdir/test.txt',
            commit1.hexsha,
            dry_run=False
        )
        
        assert result['success'] is True
        assert test_file.read_text() == 'Version 1'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
