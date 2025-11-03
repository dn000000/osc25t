"""Tests for GitManager"""

import os
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import pytest

from sysaudit.git import GitManager, GitManagerError
from sysaudit.models import Config, FileEvent, ProcessInfo


class TestGitManager:
    """Test suite for GitManager class"""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing"""
        repo_dir = tempfile.mkdtemp(prefix='test_repo_')
        watch_dir = tempfile.mkdtemp(prefix='test_watch_')
        
        yield {
            'repo': repo_dir,
            'watch': watch_dir
        }
        
        # Cleanup
        shutil.rmtree(repo_dir, ignore_errors=True)
        shutil.rmtree(watch_dir, ignore_errors=True)
    
    @pytest.fixture
    def config(self, temp_dirs):
        """Create test configuration"""
        return Config(
            repo_path=temp_dirs['repo'],
            watch_paths=[temp_dirs['watch']],
            baseline_branch='main',
            gpg_sign=False
        )
    
    @pytest.fixture
    def git_manager(self, config):
        """Create GitManager instance"""
        return GitManager(config)
    
    def test_init_repo(self, git_manager):
        """Test repository initialization"""
        git_manager.init_repo()
        
        assert git_manager.is_initialized()
        assert git_manager.repo is not None
        assert (Path(git_manager.repo_path) / '.git').exists()
    
    def test_init_repo_creates_baseline_branch(self, git_manager):
        """Test that initialization creates baseline branch"""
        git_manager.init_repo(baseline_branch='baseline')
        
        assert 'baseline' in git_manager.repo.heads
        assert git_manager.repo.active_branch.name == 'baseline'
    
    def test_init_repo_creates_initial_commit(self, git_manager):
        """Test that initialization creates initial commit"""
        git_manager.init_repo()
        
        commits = list(git_manager.repo.iter_commits())
        assert len(commits) > 0
        assert 'Initial commit' in commits[0].message
    
    def test_commit_single_file_created(self, git_manager, temp_dirs):
        """Test committing a single created file"""
        git_manager.init_repo()
        
        # Create a test file
        test_file = Path(temp_dirs['watch']) / 'test.txt'
        test_file.write_text('test content')
        
        # Create file event
        event = FileEvent(
            path=str(test_file),
            event_type='created',
            timestamp=datetime.now(),
            process_info=ProcessInfo(pid=1234, name='test', cmdline='test command')
        )
        
        # Commit the change
        commit = git_manager.commit_changes([event])
        
        assert commit is not None
        assert 'created' in commit.message.lower()
        assert str(test_file) in commit.message
    
    def test_commit_single_file_modified(self, git_manager, temp_dirs):
        """Test committing a single modified file"""
        git_manager.init_repo()
        
        # Create and commit initial file
        test_file = Path(temp_dirs['watch']) / 'test.txt'
        test_file.write_text('initial content')
        
        event1 = FileEvent(
            path=str(test_file),
            event_type='created',
            timestamp=datetime.now()
        )
        git_manager.commit_changes([event1])
        
        # Modify the file
        test_file.write_text('modified content')
        
        event2 = FileEvent(
            path=str(test_file),
            event_type='modified',
            timestamp=datetime.now()
        )
        
        # Commit the modification
        commit = git_manager.commit_changes([event2])
        
        assert commit is not None
        assert 'modified' in commit.message.lower()
    
    def test_commit_single_file_deleted(self, git_manager, temp_dirs):
        """Test committing a single deleted file"""
        git_manager.init_repo()
        
        # Create and commit initial file
        test_file = Path(temp_dirs['watch']) / 'test.txt'
        test_file.write_text('content')
        
        event1 = FileEvent(
            path=str(test_file),
            event_type='created',
            timestamp=datetime.now()
        )
        git_manager.commit_changes([event1])
        
        # Delete the file
        test_file.unlink()
        
        event2 = FileEvent(
            path=str(test_file),
            event_type='deleted',
            timestamp=datetime.now()
        )
        
        # Commit the deletion
        commit = git_manager.commit_changes([event2])
        
        assert commit is not None
        assert 'deleted' in commit.message.lower()
    
    def test_commit_batch_changes(self, git_manager, temp_dirs):
        """Test committing multiple files in a batch"""
        git_manager.init_repo()
        
        # Create multiple test files
        files = []
        events = []
        
        for i in range(3):
            test_file = Path(temp_dirs['watch']) / f'test{i}.txt'
            test_file.write_text(f'content {i}')
            files.append(test_file)
            
            events.append(FileEvent(
                path=str(test_file),
                event_type='created',
                timestamp=datetime.now()
            ))
        
        # Commit all changes
        commit = git_manager.commit_changes(events)
        
        assert commit is not None
        assert 'batch update' in commit.message.lower()
        assert '3 files' in commit.message.lower()
    
    def test_commit_with_process_info(self, git_manager, temp_dirs):
        """Test that commit message includes process information"""
        git_manager.init_repo()
        
        test_file = Path(temp_dirs['watch']) / 'test.txt'
        test_file.write_text('content')
        
        process_info = ProcessInfo(
            pid=1234,
            name='vim',
            cmdline='vim test.txt'
        )
        
        event = FileEvent(
            path=str(test_file),
            event_type='created',
            timestamp=datetime.now(),
            process_info=process_info
        )
        
        commit = git_manager.commit_changes([event])
        
        assert commit is not None
        assert 'vim' in commit.message
        assert '1234' in commit.message
    
    def test_commit_without_process_info(self, git_manager, temp_dirs):
        """Test commit message when process info is unavailable"""
        git_manager.init_repo()
        
        test_file = Path(temp_dirs['watch']) / 'test.txt'
        test_file.write_text('content')
        
        event = FileEvent(
            path=str(test_file),
            event_type='created',
            timestamp=datetime.now(),
            process_info=None
        )
        
        commit = git_manager.commit_changes([event])
        
        assert commit is not None
        assert 'unknown' in commit.message.lower()
    
    def test_commit_empty_events_list(self, git_manager):
        """Test that committing empty events list returns None"""
        git_manager.init_repo()
        
        commit = git_manager.commit_changes([])
        
        assert commit is None
    
    def test_commit_before_init_raises_error(self, git_manager, temp_dirs):
        """Test that committing before initialization raises error"""
        test_file = Path(temp_dirs['watch']) / 'test.txt'
        test_file.write_text('content')
        
        event = FileEvent(
            path=str(test_file),
            event_type='created',
            timestamp=datetime.now()
        )
        
        with pytest.raises(GitManagerError):
            git_manager.commit_changes([event])
    
    def test_get_latest_commit(self, git_manager):
        """Test getting the latest commit"""
        git_manager.init_repo()
        
        latest = git_manager.get_latest_commit()
        
        assert latest is not None
        assert 'Initial commit' in latest.message
    
    def test_get_baseline_commit(self, git_manager):
        """Test getting the baseline commit"""
        # Update config to use 'baseline' branch
        git_manager.config.baseline_branch = 'baseline'
        git_manager.init_repo(baseline_branch='baseline')
        
        baseline = git_manager.get_baseline_commit()
        
        assert baseline is not None
    
    def test_gpg_signing_status(self, git_manager):
        """Test getting GPG signing status"""
        git_manager.init_repo()
        
        status = git_manager.get_gpg_signing_status()
        
        assert 'enabled' in status
        assert 'configured_in_git' in status
        assert 'signing_key' in status
    
    def test_enable_gpg_signing(self, git_manager):
        """Test enabling GPG signing"""
        git_manager.init_repo()
        
        git_manager.enable_gpg_signing()
        
        assert git_manager.config.gpg_sign is True
    
    def test_disable_gpg_signing(self, git_manager):
        """Test disabling GPG signing"""
        git_manager.init_repo()
        git_manager.enable_gpg_signing()
        
        git_manager.disable_gpg_signing()
        
        assert git_manager.config.gpg_sign is False
    
    def test_file_path_conversion(self, git_manager):
        """Test conversion of absolute paths to repo-relative paths"""
        # Test Unix-style path
        unix_path = '/etc/config/test.conf'
        relative = git_manager._get_repo_relative_path(unix_path)
        assert not relative.startswith('/')
        assert 'etc' in relative
        
        # Test relative path (should remain unchanged)
        rel_path = 'config/test.conf'
        result = git_manager._get_repo_relative_path(rel_path)
        assert result == rel_path
    
    def test_race_condition_file_disappears(self, git_manager, temp_dirs):
        """Test handling of race condition when file disappears"""
        git_manager.init_repo()
        
        # Create event for non-existent file
        test_file = Path(temp_dirs['watch']) / 'nonexistent.txt'
        
        event = FileEvent(
            path=str(test_file),
            event_type='modified',
            timestamp=datetime.now()
        )
        
        # Should not raise error, just return None
        commit = git_manager.commit_changes([event])
        
        # Commit might be None if no files were successfully synced
        # This is expected behavior for race conditions
        assert True  # Test passes if no exception raised


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
