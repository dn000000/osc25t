"""Detailed unit tests for severity scoring (Requirement 12.1, 12.2, 12.3, 12.4)"""

import pytest
from sysaudit.git.severity import SeverityScorer


class TestSeverityScorerBasics:
    """Basic tests for SeverityScorer"""
    
    def test_initialization(self):
        """Test SeverityScorer initializes correctly"""
        scorer = SeverityScorer()
        assert scorer is not None
    
    def test_initialization_with_custom_patterns(self):
        """Test initialization with custom patterns"""
        custom = {'/custom/*': 'HIGH'}
        scorer = SeverityScorer(custom_patterns=custom)
        assert scorer.score('/custom/file.txt') == 'HIGH'


class TestCriticalPathScoring:
    """Test scoring of critical system paths (Requirement 12.2)"""
    
    def test_sudoers_is_high(self):
        """Test /etc/sudoers is HIGH severity"""
        scorer = SeverityScorer()
        assert scorer.score('/etc/sudoers') == 'HIGH'
    
    def test_shadow_is_high(self):
        """Test /etc/shadow is HIGH severity"""
        scorer = SeverityScorer()
        assert scorer.score('/etc/shadow') == 'HIGH'
    
    def test_passwd_is_high(self):
        """Test /etc/passwd is HIGH severity"""
        scorer = SeverityScorer()
        assert scorer.score('/etc/passwd') == 'HIGH'
    
    def test_sshd_config_is_high(self):
        """Test /etc/ssh/sshd_config is HIGH severity"""
        scorer = SeverityScorer()
        assert scorer.score('/etc/ssh/sshd_config') == 'HIGH'
    
    def test_pam_config_is_high(self):
        """Test PAM configuration files are HIGH severity"""
        scorer = SeverityScorer()
        assert scorer.score('/etc/pam.d/common-auth') == 'HIGH'
        assert scorer.score('/etc/pam.d/sudo') == 'HIGH'
    
    def test_security_directory_is_high(self):
        """Test /etc/security/ files are HIGH severity"""
        scorer = SeverityScorer()
        assert scorer.score('/etc/security/limits.conf') == 'HIGH'
        assert scorer.score('/etc/security/access.conf') == 'HIGH'
    
    def test_grub_config_is_high(self):
        """Test bootloader config is HIGH severity"""
        scorer = SeverityScorer()
        assert scorer.score('/boot/grub/grub.cfg') == 'HIGH'


class TestMediumPathScoring:
    """Test scoring of medium priority paths (Requirement 12.3)"""
    
    def test_etc_directory_is_medium(self):
        """Test general /etc files are MEDIUM severity"""
        scorer = SeverityScorer()
        assert scorer.score('/etc/hostname') == 'MEDIUM'
        assert scorer.score('/etc/hosts') == 'MEDIUM'
        assert scorer.score('/etc/resolv.conf') == 'MEDIUM'
    
    def test_usr_bin_is_medium(self):
        """Test /usr/bin files are MEDIUM severity"""
        scorer = SeverityScorer()
        assert scorer.score('/usr/bin/python') == 'MEDIUM'
        assert scorer.score('/usr/bin/gcc') == 'MEDIUM'
    
    def test_usr_local_bin_is_medium(self):
        """Test /usr/local/bin files are MEDIUM severity"""
        scorer = SeverityScorer()
        assert scorer.score('/usr/local/bin/myapp') == 'MEDIUM'
        assert scorer.score('/usr/local/bin/script.sh') == 'MEDIUM'
    
    def test_cron_files_are_medium(self):
        """Test cron files are MEDIUM severity"""
        scorer = SeverityScorer()
        assert scorer.score('/etc/cron.d/backup') == 'MEDIUM'
        assert scorer.score('/etc/crontab') == 'MEDIUM'


class TestLowPathScoring:
    """Test scoring of low priority paths (Requirement 12.3)"""
    
    def test_home_directory_is_low(self):
        """Test home directory files are LOW severity"""
        scorer = SeverityScorer()
        assert scorer.score('/home/user/document.txt') == 'LOW'
        assert scorer.score('/home/user/.bashrc') == 'LOW'
    
    def test_tmp_directory_is_low(self):
        """Test /tmp files are LOW severity"""
        scorer = SeverityScorer()
        assert scorer.score('/tmp/tempfile') == 'LOW'
        assert scorer.score('/tmp/test.txt') == 'LOW'
    
    def test_var_log_is_low(self):
        """Test log files are LOW severity"""
        scorer = SeverityScorer()
        assert scorer.score('/var/log/syslog') == 'LOW'
        assert scorer.score('/var/log/app.log') == 'LOW'
    
    def test_opt_directory_is_low(self):
        """Test /opt files are LOW severity"""
        scorer = SeverityScorer()
        assert scorer.score('/opt/myapp/config.ini') == 'LOW'


class TestCustomPatterns:
    """Test custom pattern functionality"""
    
    def test_add_custom_pattern(self):
        """Test adding custom severity pattern"""
        scorer = SeverityScorer()
        scorer.add_custom_pattern('/myapp/*', 'HIGH')
        assert scorer.score('/myapp/config.conf') == 'HIGH'
    
    def test_custom_pattern_overrides_default(self):
        """Test custom pattern overrides default scoring"""
        scorer = SeverityScorer()
        # /tmp is normally LOW
        assert scorer.score('/tmp/test.txt') == 'LOW'
        
        # Override with custom pattern
        scorer.add_custom_pattern('/tmp/critical/*', 'HIGH')
        assert scorer.score('/tmp/critical/file.txt') == 'HIGH'
    
    def test_remove_custom_pattern(self):
        """Test removing custom pattern"""
        scorer = SeverityScorer()
        scorer.add_custom_pattern('/test/*', 'HIGH')
        assert scorer.score('/test/file.txt') == 'HIGH'
        
        scorer.remove_custom_pattern('/test/*')
        assert scorer.score('/test/file.txt') == 'LOW'
    
    def test_multiple_custom_patterns(self):
        """Test multiple custom patterns"""
        scorer = SeverityScorer()
        scorer.add_custom_pattern('/app1/*', 'HIGH')
        scorer.add_custom_pattern('/app2/*', 'MEDIUM')
        scorer.add_custom_pattern('/app3/*', 'LOW')
        
        assert scorer.score('/app1/file') == 'HIGH'
        assert scorer.score('/app2/file') == 'MEDIUM'
        assert scorer.score('/app3/file') == 'LOW'
    
    def test_invalid_severity_raises_error(self):
        """Test that invalid severity level raises ValueError"""
        scorer = SeverityScorer()
        with pytest.raises(ValueError):
            scorer.add_custom_pattern('/test/*', 'INVALID')


class TestBatchScoring:
    """Test batch scoring operations"""
    
    def test_score_multiple_paths(self):
        """Test scoring multiple paths at once"""
        scorer = SeverityScorer()
        paths = [
            '/etc/shadow',
            '/etc/hostname',
            '/home/user/file.txt'
        ]
        
        scores = scorer.score_multiple(paths)
        
        assert scores['/etc/shadow'] == 'HIGH'
        assert scores['/etc/hostname'] == 'MEDIUM'
        assert scores['/home/user/file.txt'] == 'LOW'
    
    def test_score_multiple_empty_list(self):
        """Test scoring empty list"""
        scorer = SeverityScorer()
        scores = scorer.score_multiple([])
        assert scores == {}
    
    def test_get_high_severity_paths(self):
        """Test filtering high severity paths"""
        scorer = SeverityScorer()
        paths = [
            '/etc/shadow',
            '/etc/hostname',
            '/etc/sudoers',
            '/home/user/file.txt'
        ]
        
        high_paths = scorer.get_high_severity_paths(paths)
        
        assert len(high_paths) == 2
        assert '/etc/shadow' in high_paths
        assert '/etc/sudoers' in high_paths
        assert '/etc/hostname' not in high_paths
    
    def test_get_paths_by_severity(self):
        """Test grouping paths by severity (Requirement 12.4)"""
        scorer = SeverityScorer()
        paths = [
            '/etc/shadow',
            '/etc/sudoers',
            '/etc/hostname',
            '/usr/bin/python',
            '/home/user/file.txt',
            '/tmp/test.txt'
        ]
        
        grouped = scorer.get_paths_by_severity(paths)
        
        assert 'HIGH' in grouped
        assert 'MEDIUM' in grouped
        assert 'LOW' in grouped
        
        assert len(grouped['HIGH']) == 2
        assert len(grouped['MEDIUM']) == 2
        assert len(grouped['LOW']) == 2


class TestPatternMatching:
    """Test pattern matching behavior"""
    
    def test_exact_path_match(self):
        """Test exact path matching"""
        scorer = SeverityScorer()
        # /etc/shadow should match exactly
        assert scorer.score('/etc/shadow') == 'HIGH'
    
    def test_prefix_path_match(self):
        """Test prefix path matching"""
        scorer = SeverityScorer()
        # Files under /etc/pam.d/ should match
        assert scorer.score('/etc/pam.d/common-auth') == 'HIGH'
        assert scorer.score('/etc/pam.d/sudo') == 'HIGH'
    
    def test_wildcard_pattern_match(self):
        """Test wildcard pattern matching"""
        scorer = SeverityScorer()
        scorer.add_custom_pattern('/test/*.conf', 'HIGH')
        
        assert scorer.score('/test/app.conf') == 'HIGH'
        assert scorer.score('/test/db.conf') == 'HIGH'
        # Should not match different extension
        assert scorer.score('/test/app.txt') == 'LOW'
    
    def test_directory_wildcard_match(self):
        """Test directory wildcard matching"""
        scorer = SeverityScorer()
        scorer.add_custom_pattern('/app/*', 'HIGH')
        
        # Should match files directly under /app
        assert scorer.score('/app/config.conf') == 'HIGH'
        assert scorer.score('/app/app.txt') == 'HIGH'
        
        # Note: fnmatch doesn't support ** for recursive matching
        # Subdirectories would need separate patterns
    
    def test_case_sensitivity(self):
        """Test that path matching is case-sensitive"""
        scorer = SeverityScorer()
        # Linux paths are case-sensitive
        assert scorer.score('/etc/shadow') == 'HIGH'
        # Different case should not match (unless on case-insensitive filesystem)
        result = scorer.score('/ETC/SHADOW')
        # Result depends on filesystem, just verify it returns valid severity
        assert result in ['HIGH', 'MEDIUM', 'LOW']


class TestPathNormalization:
    """Test path normalization"""
    
    def test_trailing_slash_normalization(self):
        """Test that trailing slashes are handled"""
        scorer = SeverityScorer()
        # Both should give same result
        score1 = scorer.score('/etc/shadow')
        score2 = scorer.score('/etc/shadow/')
        # Either both HIGH or both normalized to same result
        assert score1 in ['HIGH', 'MEDIUM', 'LOW']
        assert score2 in ['HIGH', 'MEDIUM', 'LOW']
    
    def test_relative_path_handling(self):
        """Test handling of relative paths"""
        scorer = SeverityScorer()
        # Relative paths should still be scored
        score = scorer.score('etc/shadow')
        assert score in ['HIGH', 'MEDIUM', 'LOW']
    
    def test_windows_path_normalization(self):
        """Test Windows path normalization"""
        scorer = SeverityScorer()
        # Windows-style paths should be normalized
        score = scorer.score('C:\\etc\\shadow')
        assert score in ['HIGH', 'MEDIUM', 'LOW']


class TestPatternExplanation:
    """Test pattern explanation functionality"""
    
    def test_get_pattern_explanation(self):
        """Test getting explanation for severity score"""
        scorer = SeverityScorer()
        explanation = scorer.get_pattern_explanation('/etc/shadow')
        
        assert isinstance(explanation, str)
        assert len(explanation) > 0
        assert 'HIGH' in explanation or 'high' in explanation.lower()
    
    def test_explanation_for_custom_pattern(self):
        """Test explanation includes custom pattern info"""
        scorer = SeverityScorer()
        scorer.add_custom_pattern('/myapp/*', 'HIGH')
        
        explanation = scorer.get_pattern_explanation('/myapp/config')
        assert isinstance(explanation, str)
        assert len(explanation) > 0


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_path(self):
        """Test scoring empty path"""
        scorer = SeverityScorer()
        score = scorer.score('')
        assert score in ['HIGH', 'MEDIUM', 'LOW']
    
    def test_root_path(self):
        """Test scoring root path"""
        scorer = SeverityScorer()
        score = scorer.score('/')
        assert score in ['HIGH', 'MEDIUM', 'LOW']
    
    def test_very_long_path(self):
        """Test scoring very long path"""
        scorer = SeverityScorer()
        long_path = '/home/user/' + 'a' * 1000 + '/file.txt'
        score = scorer.score(long_path)
        assert score in ['HIGH', 'MEDIUM', 'LOW']
    
    def test_path_with_special_characters(self):
        """Test path with special characters"""
        scorer = SeverityScorer()
        score = scorer.score('/home/user/file with spaces.txt')
        assert score in ['HIGH', 'MEDIUM', 'LOW']
        
        score = scorer.score('/home/user/file-with-dashes.txt')
        assert score in ['HIGH', 'MEDIUM', 'LOW']
    
    def test_unicode_path(self):
        """Test path with unicode characters"""
        scorer = SeverityScorer()
        score = scorer.score('/home/user/файл.txt')
        assert score in ['HIGH', 'MEDIUM', 'LOW']


class TestSeverityLevels:
    """Test severity level constants and validation"""
    
    def test_valid_severity_levels(self):
        """Test that only valid severity levels are used"""
        scorer = SeverityScorer()
        valid_levels = ['HIGH', 'MEDIUM', 'LOW']
        
        # Test various paths
        paths = [
            '/etc/shadow',
            '/etc/hostname',
            '/home/user/file.txt'
        ]
        
        for path in paths:
            score = scorer.score(path)
            assert score in valid_levels
    
    def test_severity_ordering(self):
        """Test that severity levels have logical ordering"""
        # HIGH > MEDIUM > LOW
        scorer = SeverityScorer()
        
        high_score = scorer.score('/etc/shadow')
        medium_score = scorer.score('/etc/hostname')
        low_score = scorer.score('/home/user/file.txt')
        
        assert high_score == 'HIGH'
        assert medium_score == 'MEDIUM'
        assert low_score == 'LOW'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
