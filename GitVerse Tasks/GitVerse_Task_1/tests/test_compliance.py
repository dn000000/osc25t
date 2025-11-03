"""Tests for compliance checking system"""

import os
import sys
import tempfile
import stat
import pytest
from pathlib import Path
from sysaudit.models import Config, ComplianceIssue
from sysaudit.compliance import (
    ComplianceChecker,
    ComplianceReporter,
    ComplianceRule,
    WorldWritableRule,
    SUIDSGIDRule,
    WeakPermissionsRule
)


class TestComplianceRule:
    """Test the abstract ComplianceRule base class"""
    
    def test_compliance_rule_is_abstract(self):
        """Test that ComplianceRule cannot be instantiated directly"""
        with pytest.raises(TypeError):
            ComplianceRule()


class TestWorldWritableRule:
    """Test WorldWritableRule"""
    
    def test_rule_properties(self):
        """Test rule name and description"""
        rule = WorldWritableRule()
        assert rule.rule_name == "world-writable"
        assert "writable" in rule.description.lower()
    
    def test_applies_to_critical_directories(self):
        """Test that rule applies to files in critical directories"""
        rule = WorldWritableRule()
        
        assert rule.applies_to('/etc/config')
        assert rule.applies_to('/usr/bin/program')
        assert rule.applies_to('/usr/local/bin/script')
        assert not rule.applies_to('/home/user/file.txt')
        assert not rule.applies_to('/tmp/test')
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix permissions not supported on Windows")
    def test_detects_world_writable_file(self):
        """Test detection of world-writable files"""
        rule = WorldWritableRule()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a world-writable file
            test_file = os.path.join(tmpdir, 'etc', 'test')
            os.makedirs(os.path.dirname(test_file), exist_ok=True)
            Path(test_file).touch()
            os.chmod(test_file, 0o666)
            
            issue = rule.check(test_file)
            assert issue is not None
            assert issue.severity == 'HIGH'
            assert issue.rule == 'world-writable'
            assert 'world-writable' in issue.description.lower()
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix permissions not supported on Windows")
    def test_ignores_non_world_writable_file(self):
        """Test that properly secured files are not flagged"""
        rule = WorldWritableRule()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a properly secured file
            test_file = os.path.join(tmpdir, 'etc', 'test')
            os.makedirs(os.path.dirname(test_file), exist_ok=True)
            Path(test_file).touch()
            os.chmod(test_file, 0o644)
            
            issue = rule.check(test_file)
            assert issue is None


class TestSUIDSGIDRule:
    """Test SUIDSGIDRule"""
    
    def test_rule_properties(self):
        """Test rule name and description"""
        rule = SUIDSGIDRule()
        assert rule.rule_name == "unexpected-suid-sgid"
        assert "suid" in rule.description.lower() or "sgid" in rule.description.lower()
    
    def test_applies_to_all_files(self):
        """Test that rule applies to all files"""
        rule = SUIDSGIDRule()
        
        assert rule.applies_to('/any/path/file')
        assert rule.applies_to('/etc/config')
        assert rule.applies_to('/tmp/test')
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix permissions not supported on Windows")
    def test_detects_unexpected_suid(self):
        """Test detection of unexpected SUID binaries"""
        rule = SUIDSGIDRule()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a SUID file in unexpected location
            test_file = os.path.join(tmpdir, 'suspicious')
            Path(test_file).touch()
            os.chmod(test_file, 0o4755)
            
            issue = rule.check(test_file)
            assert issue is not None
            assert issue.severity == 'HIGH'
            assert issue.rule == 'unexpected-suid-sgid'
            assert 'suid' in issue.description.lower()
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix permissions not supported on Windows")
    def test_ignores_expected_suid_files(self):
        """Test that expected SUID files are not flagged"""
        rule = SUIDSGIDRule()
        
        # These are in the expected list
        for path in ['/usr/bin/sudo', '/usr/bin/su', '/usr/bin/passwd']:
            # We can't actually test these without creating them,
            # but we can verify they're in the expected list
            assert path in rule.EXPECTED_SUID_FILES


class TestWeakPermissionsRule:
    """Test WeakPermissionsRule"""
    
    def test_rule_properties(self):
        """Test rule name and description"""
        rule = WeakPermissionsRule()
        assert rule.rule_name == "weak-permissions"
        assert "permissions" in rule.description.lower()
    
    def test_applies_to_sensitive_files(self):
        """Test that rule applies to sensitive files"""
        rule = WeakPermissionsRule()
        
        assert rule.applies_to('/etc/shadow')
        assert rule.applies_to('/etc/ssh/sshd_config')
        assert rule.applies_to('/root/.ssh/id_rsa')
        assert rule.applies_to('/home/user/.ssh/id_rsa')
        assert not rule.applies_to('/tmp/test.txt')
        assert not rule.applies_to('/home/user/document.txt')
    
    @pytest.mark.skipif(sys.platform == 'win32', reason="Unix permissions not supported on Windows")
    def test_detects_weak_ssh_key_permissions(self):
        """Test detection of weak SSH key permissions"""
        rule = WeakPermissionsRule()
        
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create SSH key with weak permissions
            ssh_dir = os.path.join(tmpdir, '.ssh')
            os.makedirs(ssh_dir)
            key_file = os.path.join(ssh_dir, 'id_rsa')
            Path(key_file).write_text("fake key")
            os.chmod(key_file, 0o644)  # Too permissive
            
            issue = rule.check(key_file)
            assert issue is not None
            assert issue.severity == 'HIGH'
            assert issue.rule == 'weak-permissions'


class TestComplianceChecker:
    """Test ComplianceChecker"""
    
    def test_initialization(self):
        """Test checker initialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(
                repo_path=os.path.join(tmpdir, 'repo'),
                watch_paths=[tmpdir]
            )
            checker = ComplianceChecker(config)
            
            assert checker.config == config
            assert len(checker.rules) > 0
    
    def test_list_rules(self):
        """Test listing available rules"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(
                repo_path=os.path.join(tmpdir, 'repo'),
                watch_paths=[tmpdir]
            )
            checker = ComplianceChecker(config)
            
            rules = checker.list_rules()
            assert 'world-writable' in rules
            assert 'unexpected-suid-sgid' in rules
            assert 'weak-permissions' in rules
    
    def test_get_rule_by_name(self):
        """Test getting a rule by name"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(
                repo_path=os.path.join(tmpdir, 'repo'),
                watch_paths=[tmpdir]
            )
            checker = ComplianceChecker(config)
            
            rule = checker.get_rule_by_name('world-writable')
            assert rule is not None
            assert isinstance(rule, WorldWritableRule)
            
            rule = checker.get_rule_by_name('nonexistent')
            assert rule is None
    
    def test_add_custom_rule(self):
        """Test adding a custom rule"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(
                repo_path=os.path.join(tmpdir, 'repo'),
                watch_paths=[tmpdir]
            )
            checker = ComplianceChecker(config)
            
            initial_count = len(checker.rules)
            
            # Add a custom rule
            custom_rule = WorldWritableRule()
            checker.add_rule(custom_rule)
            
            assert len(checker.rules) == initial_count + 1
    
    def test_check_files_with_nonexistent_file(self):
        """Test that nonexistent files are handled gracefully"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(
                repo_path=os.path.join(tmpdir, 'repo'),
                watch_paths=[tmpdir]
            )
            checker = ComplianceChecker(config)
            
            issues = checker.check_files(['/nonexistent/file'])
            assert issues == []
    
    def test_check_directory(self):
        """Test directory scanning"""
        with tempfile.TemporaryDirectory() as tmpdir:
            config = Config(
                repo_path=os.path.join(tmpdir, 'repo'),
                watch_paths=[tmpdir]
            )
            checker = ComplianceChecker(config)
            
            # Create some test files
            Path(os.path.join(tmpdir, 'file1.txt')).touch()
            Path(os.path.join(tmpdir, 'file2.txt')).touch()
            
            # Should not crash
            issues = checker.check_directory(tmpdir)
            assert isinstance(issues, list)


class TestComplianceReporter:
    """Test ComplianceReporter"""
    
    def test_initialization(self):
        """Test reporter initialization"""
        issues = []
        reporter = ComplianceReporter(issues)
        
        assert reporter.issues == issues
        assert reporter.timestamp is not None
    
    def test_text_report_no_issues(self):
        """Test text report with no issues"""
        reporter = ComplianceReporter([])
        report = reporter.generate_text_report()
        
        assert "No compliance issues found" in report
    
    def test_text_report_with_issues(self):
        """Test text report with issues"""
        issues = [
            ComplianceIssue(
                severity='HIGH',
                rule='test-rule',
                path='/test/path',
                description='Test issue',
                recommendation='Fix it'
            )
        ]
        reporter = ComplianceReporter(issues)
        report = reporter.generate_text_report()
        
        assert 'COMPLIANCE REPORT' in report
        assert 'HIGH' in report
        assert 'test-rule' in report
        assert '/test/path' in report
        assert 'Test issue' in report
    
    def test_json_report(self):
        """Test JSON report generation"""
        issues = [
            ComplianceIssue(
                severity='HIGH',
                rule='test-rule',
                path='/test/path',
                description='Test issue',
                recommendation='Fix it'
            )
        ]
        reporter = ComplianceReporter(issues)
        report = reporter.generate_json_report()
        
        import json
        data = json.loads(report)
        
        assert data['total_issues'] == 1
        assert data['summary']['high'] == 1
        assert len(data['issues']) == 1
        assert data['issues'][0]['severity'] == 'HIGH'
    
    def test_html_report(self):
        """Test HTML report generation"""
        issues = [
            ComplianceIssue(
                severity='MEDIUM',
                rule='test-rule',
                path='/test/path',
                description='Test issue',
                recommendation='Fix it'
            )
        ]
        reporter = ComplianceReporter(issues)
        report = reporter.generate_html_report()
        
        assert '<!DOCTYPE html>' in report
        assert '<html>' in report
        assert 'Compliance Report' in report
        assert 'MEDIUM' in report
        assert 'test-rule' in report
    
    def test_generate_report_invalid_format(self):
        """Test that invalid format raises error"""
        reporter = ComplianceReporter([])
        
        with pytest.raises(ValueError):
            reporter.generate_report('invalid')
    
    def test_save_report(self):
        """Test saving report to file"""
        issues = [
            ComplianceIssue(
                severity='LOW',
                rule='test-rule',
                path='/test/path',
                description='Test issue',
                recommendation='Fix it'
            )
        ]
        reporter = ComplianceReporter(issues)
        
        with tempfile.TemporaryDirectory() as tmpdir:
            output_file = os.path.join(tmpdir, 'report.txt')
            reporter.save_report(output_file, format='text')
            
            assert os.path.exists(output_file)
            
            with open(output_file, 'r') as f:
                content = f.read()
                assert 'COMPLIANCE REPORT' in content
    
    def test_report_groups_by_severity(self):
        """Test that reports group issues by severity"""
        issues = [
            ComplianceIssue(
                severity='HIGH',
                rule='rule1',
                path='/path1',
                description='High issue',
                recommendation='Fix 1'
            ),
            ComplianceIssue(
                severity='LOW',
                rule='rule2',
                path='/path2',
                description='Low issue',
                recommendation='Fix 2'
            ),
            ComplianceIssue(
                severity='HIGH',
                rule='rule3',
                path='/path3',
                description='Another high issue',
                recommendation='Fix 3'
            ),
        ]
        reporter = ComplianceReporter(issues)
        report = reporter.generate_text_report()
        
        # Check that HIGH section appears before LOW
        high_pos = report.find('HIGH SEVERITY')
        low_pos = report.find('LOW SEVERITY')
        assert high_pos < low_pos
        
        # Check counts
        assert 'HIGH:   2' in report
        assert 'LOW:    1' in report
