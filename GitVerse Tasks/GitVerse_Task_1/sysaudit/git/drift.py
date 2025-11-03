"""Drift detection for comparing current state with baseline"""

from typing import List, Optional
from datetime import datetime
from git import Repo, GitCommandError

from ..models import FileChange, DriftReport, Config
from .manager import GitManager, GitManagerError
from .severity import SeverityScorer


class DriftDetectorError(Exception):
    """Base exception for DriftDetector errors"""
    pass


class DriftDetector:
    """
    Detects drift (changes) between current state and baseline.
    
    Compares the current repository state with a baseline commit or branch
    to identify all changes, including additions, modifications, and deletions.
    """
    
    def __init__(self, git_manager: GitManager, severity_scorer: Optional[SeverityScorer] = None):
        """
        Initialize DriftDetector with a GitManager instance.
        
        Args:
            git_manager: GitManager instance managing the audit repository
            severity_scorer: Optional SeverityScorer for classifying changes (creates default if None)
        """
        self.git_manager = git_manager
        self.repo = git_manager.get_repo()
        self.severity_scorer = severity_scorer or SeverityScorer()
        
        if not self.repo:
            raise DriftDetectorError("GitManager repository not initialized")
    
    def check_drift(self, baseline: Optional[str] = None) -> DriftReport:
        """
        Check drift from baseline commit or branch.
        
        Compares the current HEAD with the specified baseline to identify
        all file changes. Each change is classified by type (added/modified/deleted).
        
        Args:
            baseline: Baseline commit SHA or branch name (defaults to config baseline_branch)
            
        Returns:
            DriftReport containing all detected changes
            
        Raises:
            DriftDetectorError: If baseline doesn't exist or comparison fails
        """
        if baseline is None:
            baseline = self.git_manager.config.baseline_branch
        
        try:
            # Get baseline commit
            baseline_commit = self._resolve_baseline(baseline)
            
            # Get current commit
            current_commit = self.repo.head.commit
            
            # If baseline and current are the same, no drift
            if baseline_commit.hexsha == current_commit.hexsha:
                return DriftReport(
                    baseline=baseline,
                    changes=[],
                    timestamp=datetime.now()
                )
            
            # Compare trees to find differences
            changes = self._compare_commits(baseline_commit, current_commit)
            
            return DriftReport(
                baseline=baseline,
                changes=changes,
                timestamp=datetime.now()
            )
            
        except GitCommandError as e:
            raise DriftDetectorError(f"Git command failed during drift check: {e}")
        except Exception as e:
            raise DriftDetectorError(f"Failed to check drift: {e}")
    
    def _resolve_baseline(self, baseline: str):
        """
        Resolve baseline string to a commit object.
        
        Args:
            baseline: Branch name, tag, or commit SHA
            
        Returns:
            Commit object for the baseline
            
        Raises:
            DriftDetectorError: If baseline cannot be resolved
        """
        try:
            # Try to resolve as branch, tag, or commit
            return self.repo.commit(baseline)
        except Exception as e:
            raise DriftDetectorError(f"Cannot resolve baseline '{baseline}': {e}")
    
    def _compare_commits(self, baseline_commit, current_commit) -> List[FileChange]:
        """
        Compare two commits and generate list of changes.
        
        Args:
            baseline_commit: The baseline commit to compare against
            current_commit: The current commit to compare
            
        Returns:
            List of FileChange objects representing all differences
        """
        changes = []
        
        # Get diff between commits
        # baseline_commit.diff(current_commit) shows changes from baseline to current
        diff_index = baseline_commit.diff(current_commit)
        
        for diff_item in diff_index:
            change = self._create_file_change(diff_item)
            if change:
                changes.append(change)
        
        return changes
    
    def _create_file_change(self, diff_item) -> Optional[FileChange]:
        """
        Create a FileChange object from a git diff item.
        
        Args:
            diff_item: GitPython diff item
            
        Returns:
            FileChange object, or None if change should be ignored
        """
        # Determine change type
        change_type = self._get_change_type(diff_item)
        
        # Get file path (use b_path for additions, a_path for deletions, either for modifications)
        if diff_item.new_file:
            path = diff_item.b_path
        elif diff_item.deleted_file:
            path = diff_item.a_path
        else:
            path = diff_item.a_path or diff_item.b_path
        
        if not path:
            return None
        
        # Score severity using SeverityScorer
        severity = self.severity_scorer.score(path)
        
        # Create FileChange with scored severity
        return FileChange(
            path=path,
            change_type=change_type,
            severity=severity
        )
    
    def _get_change_type(self, diff_item) -> str:
        """
        Determine the type of change from a diff item.
        
        Args:
            diff_item: GitPython diff item
            
        Returns:
            Change type: 'added', 'modified', or 'deleted'
        """
        if diff_item.new_file:
            return 'added'
        elif diff_item.deleted_file:
            return 'deleted'
        elif diff_item.renamed_file:
            # Treat renames as modifications
            return 'modified'
        else:
            return 'modified'
    
    def get_file_history(self, file_path: str, max_count: int = 10) -> List[dict]:
        """
        Get commit history for a specific file.
        
        Args:
            file_path: Path to the file (repository-relative)
            max_count: Maximum number of commits to retrieve
            
        Returns:
            List of dictionaries containing commit information
        """
        try:
            commits = list(self.repo.iter_commits(paths=file_path, max_count=max_count))
            
            history = []
            for commit in commits:
                history.append({
                    'sha': commit.hexsha,
                    'message': commit.message,
                    'author': str(commit.author),
                    'timestamp': datetime.fromtimestamp(commit.committed_date),
                    'summary': commit.summary
                })
            
            return history
            
        except Exception as e:
            raise DriftDetectorError(f"Failed to get file history: {e}")
    
    def compare_with_baseline(self, file_path: str, baseline: Optional[str] = None) -> Optional[dict]:
        """
        Compare a specific file with its baseline version.
        
        Args:
            file_path: Path to the file (repository-relative)
            baseline: Baseline commit or branch (defaults to config baseline_branch)
            
        Returns:
            Dictionary with comparison details, or None if file doesn't exist in baseline
        """
        if baseline is None:
            baseline = self.git_manager.config.baseline_branch
        
        try:
            baseline_commit = self._resolve_baseline(baseline)
            current_commit = self.repo.head.commit
            
            # Check if file exists in baseline
            baseline_content = None
            try:
                baseline_blob = baseline_commit.tree / file_path
                baseline_content = baseline_blob.data_stream.read().decode('utf-8', errors='replace')
            except KeyError:
                # File doesn't exist in baseline
                pass
            
            # Check if file exists in current
            current_content = None
            try:
                current_blob = current_commit.tree / file_path
                current_content = current_blob.data_stream.read().decode('utf-8', errors='replace')
            except KeyError:
                # File doesn't exist in current
                pass
            
            # Determine change type
            if baseline_content is None and current_content is not None:
                change_type = 'added'
            elif baseline_content is not None and current_content is None:
                change_type = 'deleted'
            elif baseline_content != current_content:
                change_type = 'modified'
            else:
                change_type = 'unchanged'
            
            return {
                'file_path': file_path,
                'change_type': change_type,
                'baseline_exists': baseline_content is not None,
                'current_exists': current_content is not None,
                'baseline_content': baseline_content,
                'current_content': current_content
            }
            
        except Exception as e:
            raise DriftDetectorError(f"Failed to compare file with baseline: {e}")
