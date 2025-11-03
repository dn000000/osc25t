"""
Tests for Git Integration.
"""

import os
import tempfile
import shutil
from pathlib import Path
import pytest
from gitproc.git_integration import GitIntegration


class TestGitIntegration:
    """Tests for Git repository operations."""
    
    @pytest.fixture
    def temp_repo_path(self):
        """Create a temporary directory for Git repository."""
        temp_dir = tempfile.mkdtemp()
        yield temp_dir
        # Cleanup
        shutil.rmtree(temp_dir, ignore_errors=True)
    
    def test_init_repo_creates_repository(self, temp_repo_path):
        """Test that init_repo creates a Git repository."""
        git_integration = GitIntegration(temp_repo_path, branch="main")
        
        result = git_integration.init_repo()
        
        assert result is True
        assert (Path(temp_repo_path) / ".git").exists()
        assert (Path(temp_repo_path) / "README.md").exists()
    
    def test_init_repo_creates_initial_commit(self, temp_repo_path):
        """Test that init_repo creates an initial commit."""
        git_integration = GitIntegration(temp_repo_path, branch="main")
        
        git_integration.init_repo()
        
        # Verify we have at least one commit
        assert git_integration.last_commit is not None
        assert len(git_integration.last_commit) == 40  # SHA-1 hash length
    
    def test_init_repo_on_existing_repository(self, temp_repo_path):
        """Test that init_repo works on an existing repository."""
        git_integration = GitIntegration(temp_repo_path, branch="main")
        
        # Initialize once
        result1 = git_integration.init_repo()
        first_commit = git_integration.last_commit
        
        # Initialize again
        git_integration2 = GitIntegration(temp_repo_path, branch="main")
        result2 = git_integration2.init_repo()
        
        assert result1 is True
        assert result2 is True
        assert git_integration2.last_commit == first_commit
    
    def test_get_unit_files_empty_repository(self, temp_repo_path):
        """Test listing unit files in an empty repository."""
        git_integration = GitIntegration(temp_repo_path, branch="main")
        git_integration.init_repo()
        
        unit_files = git_integration.get_unit_files()
        
        assert unit_files == []
    
    def test_get_unit_files_with_service_files(self, temp_repo_path):
        """Test listing unit files when .service files exist."""
        git_integration = GitIntegration(temp_repo_path, branch="main")
        git_integration.init_repo()
        
        # Create some .service files
        (Path(temp_repo_path) / "nginx.service").write_text("[Service]\nExecStart=/usr/bin/nginx\n")
        (Path(temp_repo_path) / "app.service").write_text("[Service]\nExecStart=/usr/bin/app\n")
        
        unit_files = git_integration.get_unit_files()
        
        assert len(unit_files) == 2
        assert "nginx.service" in unit_files
        assert "app.service" in unit_files
    
    def test_get_unit_files_ignores_non_service_files(self, temp_repo_path):
        """Test that get_unit_files only returns .service files."""
        git_integration = GitIntegration(temp_repo_path, branch="main")
        git_integration.init_repo()
        
        # Create various files
        (Path(temp_repo_path) / "nginx.service").write_text("[Service]\nExecStart=/usr/bin/nginx\n")
        (Path(temp_repo_path) / "config.txt").write_text("some config")
        (Path(temp_repo_path) / "script.sh").write_text("#!/bin/bash")
        
        unit_files = git_integration.get_unit_files()
        
        assert len(unit_files) == 1
        assert "nginx.service" in unit_files
    
    def test_get_unit_files_in_subdirectories(self, temp_repo_path):
        """Test listing unit files in subdirectories."""
        git_integration = GitIntegration(temp_repo_path, branch="main")
        git_integration.init_repo()
        
        # Create subdirectory with service file
        subdir = Path(temp_repo_path) / "services"
        subdir.mkdir()
        (subdir / "web.service").write_text("[Service]\nExecStart=/usr/bin/web\n")
        
        unit_files = git_integration.get_unit_files()
        
        assert len(unit_files) == 1
        assert "services/web.service" in unit_files or "services\\web.service" in unit_files
    
    def test_has_changes_no_changes(self, temp_repo_path):
        """Test has_changes returns False when no new commits."""
        git_integration = GitIntegration(temp_repo_path, branch="main")
        git_integration.init_repo()
        
        # First call stores the commit
        has_changes = git_integration.has_changes()
        assert has_changes is False
        
        # Second call with no new commits
        has_changes = git_integration.has_changes()
        assert has_changes is False
    
    def test_has_changes_with_new_commit(self, temp_repo_path):
        """Test has_changes returns True when new commit exists."""
        git_integration = GitIntegration(temp_repo_path, branch="main")
        git_integration.init_repo()
        
        # Store initial commit
        git_integration.has_changes()
        
        # Create and commit a new file
        (Path(temp_repo_path) / "test.service").write_text("[Service]\nExecStart=/bin/test\n")
        git_integration.repo.index.add(["test.service"])
        git_integration.repo.index.commit("Add test service")
        
        # Check for changes
        has_changes = git_integration.has_changes()
        assert has_changes is True
    
    def test_get_changed_files_no_previous_commit(self, temp_repo_path):
        """Test get_changed_files when no previous commit is stored."""
        git_integration = GitIntegration(temp_repo_path, branch="main")
        git_integration.init_repo()
        
        # Create service files
        (Path(temp_repo_path) / "app.service").write_text("[Service]\nExecStart=/usr/bin/app\n")
        git_integration.repo.index.add(["app.service"])
        git_integration.repo.index.commit("Add app service")
        
        # Reset last_commit to simulate no previous knowledge
        git_integration.last_commit = None
        
        modified, added, deleted = git_integration.get_changed_files()
        
        # All current files should be in "added"
        assert len(modified) == 0
        assert len(added) == 1
        assert "app.service" in added
        assert len(deleted) == 0
    
    def test_get_changed_files_modified_file(self, temp_repo_path):
        """Test get_changed_files detects modified files."""
        git_integration = GitIntegration(temp_repo_path, branch="main")
        git_integration.init_repo()
        
        # Create and commit initial file
        service_path = Path(temp_repo_path) / "app.service"
        service_path.write_text("[Service]\nExecStart=/usr/bin/app\n")
        git_integration.repo.index.add(["app.service"])
        git_integration.repo.index.commit("Add app service")
        
        # Store this commit
        git_integration.last_commit = git_integration.repo.head.commit.hexsha
        
        # Modify the file
        service_path.write_text("[Service]\nExecStart=/usr/bin/app --new-flag\n")
        git_integration.repo.index.add(["app.service"])
        git_integration.repo.index.commit("Update app service")
        
        modified, added, deleted = git_integration.get_changed_files()
        
        assert len(modified) == 1
        assert "app.service" in modified
        assert len(added) == 0
        assert len(deleted) == 0
    
    def test_get_changed_files_added_file(self, temp_repo_path):
        """Test get_changed_files detects added files."""
        git_integration = GitIntegration(temp_repo_path, branch="main")
        git_integration.init_repo()
        
        # Store initial commit
        git_integration.last_commit = git_integration.repo.head.commit.hexsha
        
        # Add new file
        (Path(temp_repo_path) / "new.service").write_text("[Service]\nExecStart=/usr/bin/new\n")
        git_integration.repo.index.add(["new.service"])
        git_integration.repo.index.commit("Add new service")
        
        modified, added, deleted = git_integration.get_changed_files()
        
        assert len(modified) == 0
        assert len(added) == 1
        assert "new.service" in added
        assert len(deleted) == 0
    
    def test_get_changed_files_deleted_file(self, temp_repo_path):
        """Test get_changed_files detects deleted files."""
        git_integration = GitIntegration(temp_repo_path, branch="main")
        git_integration.init_repo()
        
        # Create and commit file
        service_path = Path(temp_repo_path) / "old.service"
        service_path.write_text("[Service]\nExecStart=/usr/bin/old\n")
        git_integration.repo.index.add(["old.service"])
        git_integration.repo.index.commit("Add old service")
        
        # Store this commit
        git_integration.last_commit = git_integration.repo.head.commit.hexsha
        
        # Delete the file
        service_path.unlink()
        git_integration.repo.index.remove(["old.service"])
        git_integration.repo.index.commit("Remove old service")
        
        modified, added, deleted = git_integration.get_changed_files()
        
        assert len(modified) == 0
        assert len(added) == 0
        assert len(deleted) == 1
        assert "old.service" in deleted
    
    def test_get_changed_files_multiple_changes(self, temp_repo_path):
        """Test get_changed_files with multiple types of changes."""
        git_integration = GitIntegration(temp_repo_path, branch="main")
        git_integration.init_repo()
        
        # Create initial files
        (Path(temp_repo_path) / "app1.service").write_text("[Service]\nExecStart=/usr/bin/app1\n")
        (Path(temp_repo_path) / "app2.service").write_text("[Service]\nExecStart=/usr/bin/app2\n")
        git_integration.repo.index.add(["app1.service", "app2.service"])
        git_integration.repo.index.commit("Add initial services")
        
        # Store this commit
        git_integration.last_commit = git_integration.repo.head.commit.hexsha
        
        # Make multiple changes
        # Modify app1
        (Path(temp_repo_path) / "app1.service").write_text("[Service]\nExecStart=/usr/bin/app1 --updated\n")
        # Delete app2
        (Path(temp_repo_path) / "app2.service").unlink()
        # Add app3
        (Path(temp_repo_path) / "app3.service").write_text("[Service]\nExecStart=/usr/bin/app3\n")
        
        git_integration.repo.index.add(["app1.service", "app3.service"])
        git_integration.repo.index.remove(["app2.service"])
        git_integration.repo.index.commit("Multiple changes")
        
        modified, added, deleted = git_integration.get_changed_files()
        
        assert "app1.service" in modified
        assert "app3.service" in added
        assert "app2.service" in deleted
    
    def test_rollback_to_valid_commit(self, temp_repo_path):
        """Test rollback to a valid commit."""
        git_integration = GitIntegration(temp_repo_path, branch="main")
        git_integration.init_repo()
        
        # Create first version
        (Path(temp_repo_path) / "app.service").write_text("[Service]\nExecStart=/usr/bin/app v1\n")
        git_integration.repo.index.add(["app.service"])
        git_integration.repo.index.commit("Version 1")
        first_commit = git_integration.repo.head.commit.hexsha
        
        # Create second version
        (Path(temp_repo_path) / "app.service").write_text("[Service]\nExecStart=/usr/bin/app v2\n")
        git_integration.repo.index.add(["app.service"])
        git_integration.repo.index.commit("Version 2")
        
        # Rollback to first version
        result = git_integration.rollback(first_commit)
        
        assert result is True
        assert git_integration.last_commit == first_commit
        
        # Verify file content is rolled back
        content = (Path(temp_repo_path) / "app.service").read_text()
        assert "v1" in content
        assert "v2" not in content
    
    def test_rollback_to_invalid_commit(self, temp_repo_path):
        """Test rollback with invalid commit hash."""
        git_integration = GitIntegration(temp_repo_path, branch="main")
        git_integration.init_repo()
        
        result = git_integration.rollback("invalid_commit_hash_12345")
        
        assert result is False
    
    def test_rollback_updates_last_commit(self, temp_repo_path):
        """Test that rollback updates the last_commit tracker."""
        git_integration = GitIntegration(temp_repo_path, branch="main")
        git_integration.init_repo()
        
        # Create commits
        (Path(temp_repo_path) / "app.service").write_text("[Service]\nExecStart=/usr/bin/app v1\n")
        git_integration.repo.index.add(["app.service"])
        git_integration.repo.index.commit("Version 1")
        first_commit = git_integration.repo.head.commit.hexsha
        
        (Path(temp_repo_path) / "app.service").write_text("[Service]\nExecStart=/usr/bin/app v2\n")
        git_integration.repo.index.add(["app.service"])
        git_integration.repo.index.commit("Version 2")
        
        # Rollback
        git_integration.rollback(first_commit)
        
        # Verify last_commit is updated
        assert git_integration.last_commit == first_commit
        
        # Verify has_changes returns False after rollback
        assert git_integration.has_changes() is False
