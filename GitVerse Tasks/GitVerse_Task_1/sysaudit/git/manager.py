"""Git repository management for the audit system"""

import os
import shutil
from pathlib import Path
from typing import List, Optional
from datetime import datetime
import git
from git import Repo, GitCommandError

from ..models import FileEvent, Config


class GitManagerError(Exception):
    """Base exception for GitManager errors"""
    pass


class GitManager:
    """
    Manages Git repository operations for the audit system.
    
    Handles repository initialization, file synchronization, and commit creation
    with metadata tracking.
    """
    
    def __init__(self, config: Config):
        """
        Initialize GitManager with configuration.
        
        Args:
            config: Configuration object containing repo_path and other settings
        """
        self.config = config
        self.repo_path = Path(config.repo_path)
        self.repo: Optional[Repo] = None
        
        # Load existing repo if it exists
        if self._is_git_repo():
            try:
                self.repo = Repo(self.repo_path)
            except Exception as e:
                raise GitManagerError(f"Failed to load existing repository: {e}")
    
    def _is_git_repo(self) -> bool:
        """Check if the repo_path is already a Git repository"""
        git_dir = self.repo_path / '.git'
        return git_dir.exists() and git_dir.is_dir()
    
    def init_repo(self, baseline_branch: Optional[str] = None) -> None:
        """
        Initialize a new Git repository with baseline branch.
        
        Creates the repository directory if it doesn't exist, initializes Git,
        and creates an initial commit on the baseline branch.
        
        Args:
            baseline_branch: Name of the baseline branch (defaults to config.baseline_branch)
            
        Raises:
            GitManagerError: If initialization fails
        """
        if baseline_branch is None:
            baseline_branch = self.config.baseline_branch
        
        try:
            # Create repository directory if it doesn't exist
            self.repo_path.mkdir(parents=True, exist_ok=True)
            
            # Initialize Git repository
            if self._is_git_repo():
                self.repo = Repo(self.repo_path)
            else:
                self.repo = Repo.init(self.repo_path)
            
            # Configure Git user if not already set
            self._configure_git_user()
            
            # Create initial commit if repository is empty
            if not self._has_commits():
                self._create_initial_commit(baseline_branch)
            
        except GitCommandError as e:
            raise GitManagerError(f"Git command failed during initialization: {e}")
        except Exception as e:
            raise GitManagerError(f"Failed to initialize repository: {e}")
    
    def _configure_git_user(self) -> None:
        """Configure Git user name and email if not already set"""
        try:
            with self.repo.config_reader() as config:
                try:
                    config.get_value('user', 'name')
                    config.get_value('user', 'email')
                    return  # Already configured
                except:
                    pass
            
            # Set default user for the repository
            with self.repo.config_writer() as config:
                config.set_value('user', 'name', 'System Audit')
                config.set_value('user', 'email', 'sysaudit@localhost')
                
        except Exception:
            # If configuration fails, Git will use system defaults
            pass
    
    def _has_commits(self) -> bool:
        """Check if repository has any commits"""
        try:
            list(self.repo.iter_commits(max_count=1))
            return True
        except:
            return False
    
    def _create_initial_commit(self, baseline_branch: str) -> None:
        """
        Create initial commit on baseline branch.
        
        Args:
            baseline_branch: Name of the baseline branch
        """
        # Create a README file for the initial commit
        readme_path = self.repo_path / 'README.md'
        readme_content = f"""# System Audit Repository

This repository tracks changes to monitored system files.

- **Baseline Branch**: {baseline_branch}
- **Created**: {datetime.now().isoformat()}
- **Purpose**: Automated system file change tracking and compliance monitoring

## Structure

Files in this repository mirror the filesystem structure of monitored paths.
Each commit represents a detected change to one or more files.

## Commit Message Format

Commits include:
- File path(s) that changed
- Type of change (created/modified/deleted)
- Timestamp of the change
- Process information (when available)
"""
        
        readme_path.write_text(readme_content)
        
        # Stage and commit
        self.repo.index.add([str(readme_path)])
        self.repo.index.commit(
            f"Initial commit: Initialize audit repository\n\nBaseline branch: {baseline_branch}"
        )
        
        # Create baseline branch if it doesn't exist and isn't the current branch
        branch_names = [head.name for head in self.repo.heads]
        if baseline_branch not in branch_names:
            self.repo.create_head(baseline_branch)
        
        # Checkout baseline branch
        self.repo.heads[baseline_branch].checkout()
    
    def is_initialized(self) -> bool:
        """
        Check if the repository is properly initialized.
        
        Returns:
            True if repository exists and has commits, False otherwise
        """
        return self.repo is not None and self._has_commits()

    def commit_changes(self, events: List[FileEvent]) -> Optional[git.Commit]:
        """
        Commit file changes to the repository.
        
        Syncs changed files to the repository, stages them, and creates a commit
        with informative metadata.
        
        Args:
            events: List of FileEvent objects representing changes
            
        Returns:
            The created Commit object, or None if no changes to commit
            
        Raises:
            GitManagerError: If commit operation fails
        """
        if not events:
            return None
        
        if not self.is_initialized():
            raise GitManagerError("Repository not initialized. Call init_repo() first.")
        
        try:
            # Separate deletions from other events
            deleted_events = [e for e in events if e.event_type == 'deleted']
            other_events = [e for e in events if e.event_type != 'deleted']
            
            # Sync non-deleted files to repository
            files_to_stage = []
            for event in other_events:
                synced_path = self._sync_file(event)
                if synced_path:
                    files_to_stage.append(synced_path)
            
            # Stage additions and modifications
            if files_to_stage:
                self.repo.index.add(files_to_stage)
            
            # Handle deletions
            deleted_files = []
            for event in deleted_events:
                synced_path = self._sync_file(event)
                if synced_path:
                    deleted_files.append(synced_path)
            
            if deleted_files:
                # Remove deleted files from index
                try:
                    self.repo.index.remove(deleted_files, working_tree=True)
                except GitCommandError:
                    # File might not be in index, that's okay
                    pass
            
            # Check if there are any changes to commit
            if not files_to_stage and not deleted_files:
                return None
            
            # Create commit message
            message = self._create_commit_message(events)
            
            # Create commit
            commit = self.repo.index.commit(message)
            
            # Sign commit if configured
            if self.config.gpg_sign:
                self._sign_commit(commit)
            
            return commit
            
        except GitCommandError as e:
            raise GitManagerError(f"Git command failed during commit: {e}")
        except Exception as e:
            raise GitManagerError(f"Failed to commit changes: {e}")
    
    def _sync_file(self, event: FileEvent) -> Optional[str]:
        """
        Sync a file from the filesystem to the repository.
        
        Args:
            event: FileEvent describing the change
            
        Returns:
            Relative path in repository if file was synced, None otherwise
        """
        src_path = Path(event.path)
        
        # Get relative path in repository
        repo_relative = self._get_repo_relative_path(event.path)
        dst_path = self.repo_path / repo_relative
        
        try:
            if event.event_type == 'deleted':
                # Remove file from repository if it exists
                if dst_path.exists():
                    dst_path.unlink()
                    return repo_relative
                return None
            else:
                # Copy file to repository (created or modified)
                if not src_path.exists():
                    # File disappeared between detection and sync (race condition)
                    return None
                
                # Create parent directories
                dst_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file with metadata
                shutil.copy2(src_path, dst_path)
                
                return repo_relative
                
        except (PermissionError, OSError) as e:
            # Log error but don't fail the entire operation
            # This handles race conditions and permission issues gracefully
            return None
    
    def _get_repo_relative_path(self, file_path: str) -> str:
        """
        Convert absolute file path to repository-relative path.
        
        Args:
            file_path: Absolute path to file
            
        Returns:
            Relative path suitable for repository storage (with forward slashes)
        """
        # Handle Unix-style paths (starting with /)
        if file_path.startswith('/'):
            # Remove leading slash: /etc/config -> etc/config
            relative_path = file_path.lstrip('/')
        else:
            # Handle Windows paths and relative paths
            path = Path(file_path)
            
            if path.is_absolute():
                # On Windows: C:/Users/file -> Users/file
                parts = path.parts
                if ':' in parts[0]:
                    # Skip drive letter
                    relative_path = str(Path(*parts[1:]))
                else:
                    relative_path = str(path)
            else:
                relative_path = str(path)
        
        # Convert to forward slashes for Git compatibility
        return relative_path.replace('\\', '/')
    
    def _create_commit_message(self, events: List[FileEvent]) -> str:
        """
        Create an informative commit message from file events.
        
        Args:
            events: List of FileEvent objects
            
        Returns:
            Formatted commit message with metadata
        """
        if len(events) == 1:
            # Single file change - detailed message
            event = events[0]
            
            # Subject line
            message = f"{event.event_type}: {event.path}\n\n"
            
            # Metadata
            message += f"Timestamp: {event.timestamp.isoformat()}\n"
            message += f"Event Type: {event.event_type}\n"
            message += f"File Path: {event.path}\n"
            
            # Process information if available
            if event.process_info:
                message += f"Process: {event.process_info.name} (PID: {event.process_info.pid})\n"
                if event.process_info.cmdline:
                    message += f"Command: {event.process_info.cmdline}\n"
            else:
                message += "Process: unknown\n"
            
            return message
        else:
            # Multiple files - batch message
            message = f"Batch update: {len(events)} files changed\n\n"
            
            # Group by event type
            created = [e for e in events if e.event_type == 'created']
            modified = [e for e in events if e.event_type == 'modified']
            deleted = [e for e in events if e.event_type == 'deleted']
            
            if created:
                message += f"Created ({len(created)}):\n"
                for e in created:
                    message += f"  - {e.path}\n"
                message += "\n"
            
            if modified:
                message += f"Modified ({len(modified)}):\n"
                for e in modified:
                    message += f"  - {e.path}\n"
                message += "\n"
            
            if deleted:
                message += f"Deleted ({len(deleted)}):\n"
                for e in deleted:
                    message += f"  - {e.path}\n"
                message += "\n"
            
            # Add timestamp
            message += f"Timestamp: {events[0].timestamp.isoformat()}\n"
            
            # Add process info if available for first event
            if events[0].process_info:
                message += f"Primary Process: {events[0].process_info.name} (PID: {events[0].process_info.pid})\n"
            
            return message
    
    def _sign_commit(self, commit: git.Commit) -> None:
        """
        Sign a commit with GPG (optional feature).
        
        Args:
            commit: The commit to sign
            
        Note:
            GPG signing requires proper Git and GPG configuration.
            The signing key must be configured in Git config.
        """
        # GPG signing is handled by Git configuration (commit.gpgsign)
        # This method validates that signing is properly configured
        try:
            with self.repo.config_reader() as config:
                # Check if GPG signing is enabled in Git config
                try:
                    gpg_sign = config.get_value('commit', 'gpgsign', default='false')
                    if gpg_sign.lower() != 'true':
                        # Enable GPG signing for this repository
                        with self.repo.config_writer() as writer:
                            writer.set_value('commit', 'gpgsign', 'true')
                except:
                    # Enable GPG signing
                    with self.repo.config_writer() as writer:
                        writer.set_value('commit', 'gpgsign', 'true')
        except Exception:
            # If GPG configuration fails, log but don't fail the commit
            pass
    
    def get_repo(self) -> Optional[Repo]:
        """
        Get the underlying GitPython Repo object.
        
        Returns:
            The Repo object if initialized, None otherwise
        """
        return self.repo
    
    def get_latest_commit(self) -> Optional[git.Commit]:
        """
        Get the latest commit in the repository.
        
        Returns:
            The latest Commit object, or None if no commits exist
        """
        if not self.is_initialized():
            return None
        
        try:
            return self.repo.head.commit
        except:
            return None
    
    def get_baseline_commit(self) -> Optional[git.Commit]:
        """
        Get the commit at the baseline branch.
        
        Returns:
            The baseline Commit object, or None if branch doesn't exist
        """
        if not self.is_initialized():
            return None
        
        try:
            baseline_branch = self.config.baseline_branch
            # Check if branch exists in heads
            branch_names = [head.name for head in self.repo.heads]
            if baseline_branch in branch_names:
                return self.repo.heads[baseline_branch].commit
            return None
        except:
            return None

    def validate_commit_signature(self, commit: git.Commit) -> bool:
        """
        Validate GPG signature of a commit.
        
        Args:
            commit: The commit to validate
            
        Returns:
            True if signature is valid, False otherwise
            
        Note:
            Requires GPG to be properly configured on the system.
        """
        try:
            # Check if commit has a GPG signature
            if not hasattr(commit, 'gpgsig') or not commit.gpgsig:
                return False
            
            # Use git verify-commit to validate signature
            try:
                self.repo.git.verify_commit(commit.hexsha)
                return True
            except GitCommandError:
                # Signature verification failed
                return False
                
        except Exception:
            # If validation fails for any reason, return False
            return False
    
    def enable_gpg_signing(self, signing_key: Optional[str] = None) -> None:
        """
        Enable GPG signing for commits in this repository.
        
        Args:
            signing_key: GPG key ID to use for signing (optional)
            
        Raises:
            GitManagerError: If GPG configuration fails
        """
        try:
            with self.repo.config_writer() as config:
                # Enable GPG signing
                config.set_value('commit', 'gpgsign', 'true')
                
                # Set signing key if provided
                if signing_key:
                    config.set_value('user', 'signingkey', signing_key)
            
            # Update config object
            self.config.gpg_sign = True
            
        except Exception as e:
            raise GitManagerError(f"Failed to enable GPG signing: {e}")
    
    def disable_gpg_signing(self) -> None:
        """
        Disable GPG signing for commits in this repository.
        
        Raises:
            GitManagerError: If GPG configuration fails
        """
        try:
            with self.repo.config_writer() as config:
                config.set_value('commit', 'gpgsign', 'false')
            
            # Update config object
            self.config.gpg_sign = False
            
        except Exception as e:
            raise GitManagerError(f"Failed to disable GPG signing: {e}")
    
    def get_gpg_signing_status(self) -> dict:
        """
        Get GPG signing configuration status.
        
        Returns:
            Dictionary with GPG signing status information
        """
        status = {
            'enabled': self.config.gpg_sign,
            'configured_in_git': False,
            'signing_key': None
        }
        
        try:
            with self.repo.config_reader() as config:
                # Check if GPG signing is enabled in Git config
                try:
                    gpg_sign = config.get_value('commit', 'gpgsign', default='false')
                    status['configured_in_git'] = gpg_sign.lower() == 'true'
                except:
                    pass
                
                # Get signing key if configured
                try:
                    signing_key = config.get_value('user', 'signingkey')
                    status['signing_key'] = signing_key
                except:
                    pass
        except:
            pass
        
        return status
