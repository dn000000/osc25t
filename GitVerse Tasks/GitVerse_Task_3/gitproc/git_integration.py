"""
Git Integration Module

Handles Git repository operations including initialization, change detection,
and rollback functionality for unit file management.
"""

import os
from pathlib import Path
from typing import List, Optional, Set, Tuple
import git
from git import Repo, GitCommandError


class GitIntegration:
    """Manages Git repository operations for service unit files."""
    
    def __init__(self, repo_path: str, branch: str = "main"):
        """
        Initialize Git integration.
        
        Args:
            repo_path: Path to the Git repository
            branch: Branch name to monitor (default: main)
        """
        self.repo_path = Path(repo_path)
        self.branch = branch
        self.last_commit: Optional[str] = None
        self._repo: Optional[Repo] = None
    
    @property
    def repo(self) -> Repo:
        """Lazy-load Git repository."""
        if self._repo is None:
            if self.repo_path.exists() and (self.repo_path / ".git").exists():
                self._repo = Repo(str(self.repo_path))
            else:
                raise ValueError(f"Git repository not found at {self.repo_path}")
        return self._repo
    
    def init_repo(self) -> bool:
        """
        Initialize Git repository structure.
        
        Creates the repository directory and initializes Git if not already present.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create directory if it doesn't exist
            self.repo_path.mkdir(parents=True, exist_ok=True)
            
            # Initialize Git repository if not already initialized
            if not (self.repo_path / ".git").exists():
                self._repo = Repo.init(str(self.repo_path))
                
                # Create initial commit with README
                readme_path = self.repo_path / "README.md"
                readme_path.write_text(
                    "# GitProc Service Repository\n\n"
                    "This repository contains service unit files for GitProc.\n"
                    "Add .service files to define services.\n"
                )
                
                self._repo.index.add(["README.md"])
                self._repo.index.commit("Initial commit")
                
                # Ensure we're on the correct branch
                if self.branch != "master" and self.branch != self._repo.active_branch.name:
                    self._repo.git.branch("-M", self.branch)
            else:
                self._repo = Repo(str(self.repo_path))
            
            # Store current commit as last known commit
            self.last_commit = self.repo.head.commit.hexsha
            
            return True
        except Exception as e:
            print(f"Error initializing repository: {e}")
            return False
    
    def get_unit_files(self) -> List[str]:
        """
        Get all .service files from the repository.
        
        Returns:
            List of paths to .service files relative to repo root
        """
        unit_files = []
        
        try:
            # Search for .service files in the repository
            for root, dirs, files in os.walk(self.repo_path):
                # Skip .git directory
                if ".git" in root:
                    continue
                
                for file in files:
                    if file.endswith(".service"):
                        # Get path relative to repo root
                        full_path = Path(root) / file
                        rel_path = full_path.relative_to(self.repo_path)
                        unit_files.append(str(rel_path))
            
            return sorted(unit_files)
        except Exception as e:
            print(f"Error listing unit files: {e}")
            return []
    
    def has_changes(self) -> bool:
        """
        Detect if there are new commits since last check.
        
        Returns:
            True if new commits exist, False otherwise
        """
        try:
            current_commit = self.repo.head.commit.hexsha
            
            # If we don't have a last commit, store current and return False
            if self.last_commit is None:
                self.last_commit = current_commit
                return False
            
            # Check if commit has changed
            has_new_commits = current_commit != self.last_commit
            
            return has_new_commits
        except Exception as e:
            print(f"Error checking for changes: {e}")
            return False
    
    def get_changed_files(self) -> Tuple[Set[str], Set[str], Set[str]]:
        """
        Identify modified, added, and deleted unit files since last sync.
        
        Returns:
            Tuple of (modified_files, added_files, deleted_files)
            Each set contains paths relative to repo root
        """
        modified = set()
        added = set()
        deleted = set()
        
        try:
            if self.last_commit is None:
                # No previous commit, all current files are "added"
                current_files = set(self.get_unit_files())
                return set(), current_files, set()
            
            current_commit = self.repo.head.commit.hexsha
            
            # If commits are the same, no changes
            if current_commit == self.last_commit:
                return set(), set(), set()
            
            # Get diff between last commit and current commit
            last_commit_obj = self.repo.commit(self.last_commit)
            current_commit_obj = self.repo.head.commit
            
            # Get diff
            diffs = last_commit_obj.diff(current_commit_obj)
            
            for diff in diffs:
                # Only process .service files
                if diff.a_path and diff.a_path.endswith(".service"):
                    if diff.change_type == "M":
                        modified.add(diff.a_path)
                    elif diff.change_type == "D":
                        deleted.add(diff.a_path)
                
                if diff.b_path and diff.b_path.endswith(".service"):
                    if diff.change_type == "A":
                        added.add(diff.b_path)
                    elif diff.change_type == "R":
                        # Renamed file - treat as delete old, add new
                        if diff.a_path:
                            deleted.add(diff.a_path)
                        added.add(diff.b_path)
            
            # Update last commit
            self.last_commit = current_commit
            
            return modified, added, deleted
        except Exception as e:
            print(f"Error getting changed files: {e}")
            return set(), set(), set()
    
    def rollback(self, commit_hash: str) -> bool:
        """
        Revert repository to a specific commit.
        
        Args:
            commit_hash: Git commit hash to rollback to
        
        Returns:
            True if successful, False otherwise
        """
        try:
            # Verify commit exists
            try:
                commit = self.repo.commit(commit_hash)
            except (GitCommandError, ValueError):
                print(f"Commit {commit_hash} not found")
                return False
            
            # Reset to the specified commit (hard reset)
            self.repo.git.reset("--hard", commit_hash)
            
            # Update last commit to the rollback target
            self.last_commit = commit_hash
            
            return True
        except Exception as e:
            print(f"Error during rollback: {e}")
            return False
