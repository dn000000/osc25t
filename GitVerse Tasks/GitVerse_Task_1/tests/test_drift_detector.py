"""Tests for drift detection functionality"""

import pytest
import tempfile
import shutil
from pathlib import Path
from datetime import datetime

from sysaudit.models import Config, FileChange
from sysaudit.git import GitManager, DriftDetector, DriftDetectorError, SeverityScorer


class TestDriftDetector:
    """Test suite for DriftDetector class"""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing"""
        repo_dir = tempfile.mkdtemp()
        watch_dir = tempfile.mkdtemp()
        
        yield repo_dir, watch_dir
        
        # Cleanup
        shutil.rmtree(repo_dir, ignore_errors=True)
        shutil.rmtree(watch_dir, ignore_errors=True)
    
    @pytest.fixture
    def git_manager(self, temp_dirs):
        """Create a GitManager instance for testing"""
        repo_dir, watch_dir = temp_dirs
        
        config = Config(
            repo_path=repo_dir,
            watch_paths=[watch_dir],
            baseline_branch='main'
        )
        
        manager = GitManager(config)
        manager.init_repo()
        
        return manager
    
    @pytest.fixture
    def drift_detector(self, git_manager):
        """Create a DriftDetector instance for testing"""
        return DriftDetector(git_manager)
    
    def test_init_with_uninitialized_repo(self, temp_dirs):
        """Test that DriftDetector raises error with uninitialized repo"""
        repo_dir, watch_dir = temp_dirs
        
        config = Config(
            repo_path=repo_dir,
            watch_paths=[watch_dir]
        )
        
        manager = GitManager(config)
        # Don't initialize the repo
        
        with pytest.raises(DriftDetectorError):
            DriftDetector(manager)
    
    def test_check_drift_no_changes(self, drift_detector):
        """Test drift check when there are no changes"""
        report = drift_detector.check_drift()
        
        assert report.baseline == 'main'
        assert len(report.changes) == 0
        assert isinstance(report.timestamp, datetime)
    
    def test_check_drift_with_added_file(self, drift_detector, git_manager, temp_dirs):
        """Test drift detection with an added file"""
        repo_dir, watch_dir = temp_dirs
        
        # Create a baseline branch at the initial commit
        git_manager.repo.create_head('baseline', git_manager.repo.head.commit)
        
        # Create and commit a new file
        test_file = Path(repo_dir) / 'etc' / 'test.conf'
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text('test content')
        
        # Add to git
        git_manager.repo.index.add(['etc/test.conf'])
        git_manager.repo.index.commit('Add test file')
        
        # Check drift from baseline
        report = drift_detector.check_drift('baseline')
        
        assert len(report.changes) == 1
        assert report.changes[0].path == 'etc/test.conf'
        assert report.changes[0].change_type == 'added'
        assert report.changes[0].severity in ['HIGH', 'MEDIUM', 'LOW']
    
    def test_check_drift_with_modified_file(self, drift_detector, git_manager, temp_dirs):
        """Test drift detection with a modified file"""
        repo_dir, watch_dir = temp_dirs
        
        # Create and commit initial file
        test_file = Path(repo_dir) / 'test.txt'
        test_file.write_text('initial content')
        git_manager.repo.index.add(['test.txt'])
        git_manager.repo.index.commit('Initial file')
        
        # Update baseline to current commit
        git_manager.repo.create_head('baseline', git_manager.repo.head.commit)
        
        # Modify the file
        test_file.write_text('modified content')
        git_manager.repo.index.add(['test.txt'])
        git_manager.repo.index.commit('Modify file')
        
        # Check drift from baseline
        report = drift_detector.check_drift('baseline')
        
        assert len(report.changes) == 1
        assert report.changes[0].path == 'test.txt'
        assert report.changes[0].change_type == 'modified'
    
    def test_check_drift_with_deleted_file(self, drift_detector, git_manager, temp_dirs):
        """Test drift detection with a deleted file"""
        repo_dir, watch_dir = temp_dirs
        
        # Create and commit initial file
        test_file = Path(repo_dir) / 'test.txt'
        test_file.write_text('content')
        git_manager.repo.index.add(['test.txt'])
        git_manager.repo.index.commit('Initial file')
        
        # Update baseline to current commit
        git_manager.repo.create_head('baseline', git_manager.repo.head.commit)
        
        # Delete the file
        test_file.unlink()
        git_manager.repo.index.remove(['test.txt'])
        git_manager.repo.index.commit('Delete file')
        
        # Check drift from baseline
        report = drift_detector.check_drift('baseline')
        
        assert len(report.changes) == 1
        assert report.changes[0].path == 'test.txt'
        assert report.changes[0].change_type == 'deleted'
    
    def test_check_drift_with_invalid_baseline(self, drift_detector):
        """Test that invalid baseline raises error"""
        with pytest.raises(DriftDetectorError):
            drift_detector.check_drift('nonexistent-branch')
    
    def test_check_drift_multiple_changes(self, drift_detector, git_manager, temp_dirs):
        """Test drift detection with multiple file changes"""
        repo_dir, watch_dir = temp_dirs
        
        # Create baseline with initial files
        file1 = Path(repo_dir) / 'file1.txt'
        file2 = Path(repo_dir) / 'file2.txt'
        file1.write_text('content1')
        file2.write_text('content2')
        git_manager.repo.index.add(['file1.txt', 'file2.txt'])
        git_manager.repo.index.commit('Initial files')
        git_manager.repo.create_head('baseline', git_manager.repo.head.commit)
        
        # Make multiple changes
        file1.write_text('modified content1')
        file3 = Path(repo_dir) / 'file3.txt'
        file3.write_text('new file')
        file2.unlink()
        
        git_manager.repo.index.add(['file1.txt', 'file3.txt'])
        git_manager.repo.index.remove(['file2.txt'])
        git_manager.repo.index.commit('Multiple changes')
        
        # Check drift
        report = drift_detector.check_drift('baseline')
        
        assert len(report.changes) == 3
        
        # Verify each change type is present
        change_types = {c.change_type for c in report.changes}
        assert 'modified' in change_types
        assert 'added' in change_types
        assert 'deleted' in change_types
    
    def test_get_file_history(self, drift_detector, git_manager, temp_dirs):
        """Test getting file history"""
        repo_dir, watch_dir = temp_dirs
        
        # Create file with multiple commits
        test_file = Path(repo_dir) / 'test.txt'
        test_file.write_text('version 1')
        git_manager.repo.index.add(['test.txt'])
        git_manager.repo.index.commit('Version 1')
        
        test_file.write_text('version 2')
        git_manager.repo.index.add(['test.txt'])
        git_manager.repo.index.commit('Version 2')
        
        test_file.write_text('version 3')
        git_manager.repo.index.add(['test.txt'])
        git_manager.repo.index.commit('Version 3')
        
        # Get history
        history = drift_detector.get_file_history('test.txt', max_count=10)
        
        assert len(history) == 3
        assert all('sha' in h for h in history)
        assert all('message' in h for h in history)
        assert all('timestamp' in h for h in history)
    
    def test_compare_with_baseline(self, drift_detector, git_manager, temp_dirs):
        """Test comparing specific file with baseline"""
        repo_dir, watch_dir = temp_dirs
        
        # Create baseline file
        test_file = Path(repo_dir) / 'test.txt'
        test_file.write_text('baseline content')
        git_manager.repo.index.add(['test.txt'])
        git_manager.repo.index.commit('Baseline')
        git_manager.repo.create_head('baseline', git_manager.repo.head.commit)
        
        # Modify file
        test_file.write_text('modified content')
        git_manager.repo.index.add(['test.txt'])
        git_manager.repo.index.commit('Modified')
        
        # Compare with baseline
        comparison = drift_detector.compare_with_baseline('test.txt', 'baseline')
        
        assert comparison['file_path'] == 'test.txt'
        assert comparison['change_type'] == 'modified'
        assert comparison['baseline_exists'] is True
        assert comparison['current_exists'] is True
        assert 'baseline content' in comparison['baseline_content']
        assert 'modified content' in comparison['current_content']


class TestSeverityScorer:
    """Test suite for SeverityScorer class"""
    
    def test_score_critical_files(self):
        """Test that critical files get HIGH severity"""
        scorer = SeverityScorer()
        
        critical_files = [
            '/etc/sudoers',
            '/etc/shadow',
            '/etc/passwd',
            '/etc/ssh/sshd_config',
            '/etc/pam.d/common-auth',
            '/boot/grub/grub.cfg',
        ]
        
        for file_path in critical_files:
            severity = scorer.score(file_path)
            assert severity == 'HIGH', f"{file_path} should be HIGH severity"
    
    def test_score_medium_files(self):
        """Test that system files get MEDIUM severity"""
        scorer = SeverityScorer()
        
        medium_files = [
            '/etc/hostname',
            '/etc/hosts',
            '/usr/bin/python',
            '/usr/local/bin/myapp',
            '/etc/cron.d/backup',
        ]
        
        for file_path in medium_files:
            severity = scorer.score(file_path)
            assert severity == 'MEDIUM', f"{file_path} should be MEDIUM severity"
    
    def test_score_low_files(self):
        """Test that non-system files get LOW severity"""
        scorer = SeverityScorer()
        
        low_files = [
            '/home/user/document.txt',
            '/var/log/app.log',
            '/tmp/tempfile',
            '/opt/myapp/config.ini',
        ]
        
        for file_path in low_files:
            severity = scorer.score(file_path)
            assert severity == 'LOW', f"{file_path} should be LOW severity"
    
    def test_custom_patterns(self):
        """Test custom severity patterns"""
        custom_patterns = {
            '/custom/critical/*': 'HIGH',
            '/custom/normal/*': 'MEDIUM',
        }
        
        scorer = SeverityScorer(custom_patterns=custom_patterns)
        
        assert scorer.score('/custom/critical/file.txt') == 'HIGH'
        assert scorer.score('/custom/normal/file.txt') == 'MEDIUM'
        assert scorer.score('/custom/other/file.txt') == 'LOW'
    
    def test_add_custom_pattern(self):
        """Test adding custom patterns dynamically"""
        scorer = SeverityScorer()
        
        scorer.add_custom_pattern('/myapp/*', 'HIGH')
        assert scorer.score('/myapp/config.conf') == 'HIGH'
    
    def test_remove_custom_pattern(self):
        """Test removing custom patterns"""
        scorer = SeverityScorer(custom_patterns={'/test/*': 'HIGH'})
        
        assert scorer.score('/test/file.txt') == 'HIGH'
        
        scorer.remove_custom_pattern('/test/*')
        assert scorer.score('/test/file.txt') == 'LOW'
    
    def test_score_multiple(self):
        """Test scoring multiple paths at once"""
        scorer = SeverityScorer()
        
        paths = [
            '/etc/shadow',
            '/etc/hostname',
            '/home/user/file.txt',
        ]
        
        scores = scorer.score_multiple(paths)
        
        assert scores['/etc/shadow'] == 'HIGH'
        assert scores['/etc/hostname'] == 'MEDIUM'
        assert scores['/home/user/file.txt'] == 'LOW'
    
    def test_get_high_severity_paths(self):
        """Test filtering high severity paths"""
        scorer = SeverityScorer()
        
        paths = [
            '/etc/shadow',
            '/etc/hostname',
            '/etc/sudoers',
            '/home/user/file.txt',
        ]
        
        high_paths = scorer.get_high_severity_paths(paths)
        
        assert len(high_paths) == 2
        assert '/etc/shadow' in high_paths
        assert '/etc/sudoers' in high_paths
    
    def test_get_paths_by_severity(self):
        """Test grouping paths by severity"""
        scorer = SeverityScorer()
        
        paths = [
            '/etc/shadow',
            '/etc/hostname',
            '/etc/sudoers',
            '/home/user/file.txt',
        ]
        
        grouped = scorer.get_paths_by_severity(paths)
        
        assert len(grouped['HIGH']) == 2
        assert len(grouped['MEDIUM']) == 1
        assert len(grouped['LOW']) == 1
    
    def test_pattern_explanation(self):
        """Test getting explanation for severity score"""
        scorer = SeverityScorer()
        
        explanation = scorer.get_pattern_explanation('/etc/shadow')
        assert 'HIGH' in explanation
        assert 'critical' in explanation.lower()
    
    def test_windows_path_normalization(self):
        """Test that Windows paths are normalized correctly"""
        scorer = SeverityScorer()
        
        # Windows-style path with backslashes should be normalized to forward slashes
        # Test with a path that doesn't have a drive letter
        severity = scorer.score('etc\\shadow')
        # Should match /etc/shadow pattern after normalization
        assert severity == 'HIGH'
    
    def test_invalid_severity_raises_error(self):
        """Test that invalid severity raises ValueError"""
        scorer = SeverityScorer()
        
        with pytest.raises(ValueError):
            scorer.add_custom_pattern('/test/*', 'INVALID')


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
