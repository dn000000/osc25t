"""Tests for FilterManager"""

import os
import tempfile
from pathlib import Path
import pytest
from sysaudit.monitor.filter import FilterManager


class TestFilterManager:
    """Test suite for FilterManager class"""
    
    def test_default_ignore_patterns(self):
        """Test that default ignore patterns are loaded"""
        filter_mgr = FilterManager()
        
        # Should ignore temporary files (Requirement 3.1)
        assert filter_mgr.should_ignore('/tmp/test.tmp') == True
        assert filter_mgr.should_ignore('/etc/config.swp') == True
        assert filter_mgr.should_ignore('/home/user/file~') == True
        assert filter_mgr.should_ignore('/var/log/system.log') == True
        
        # Should not ignore regular files
        assert filter_mgr.should_ignore('/etc/config.conf') == False
        assert filter_mgr.should_ignore('/home/user/script.py') == False
    
    def test_no_defaults(self):
        """Test FilterManager without default patterns"""
        filter_mgr = FilterManager(use_defaults=False)
        
        # Should not ignore anything without patterns
        assert filter_mgr.should_ignore('/tmp/test.tmp') == False
        assert filter_mgr.should_ignore('/etc/config.swp') == False
    
    def test_blacklist_from_file(self):
        """Test loading blacklist patterns from file (Requirement 3.3, 3.4)"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write('*.secret\n')
            f.write('*.key\n')
            f.write('# This is a comment\n')
            f.write('\n')  # Empty line
            f.write('passwords/*\n')
            blacklist_file = f.name
        
        try:
            filter_mgr = FilterManager(blacklist_file=blacklist_file, use_defaults=False)
            
            # Should ignore files matching blacklist patterns
            assert filter_mgr.should_ignore('/etc/app.secret') == True
            assert filter_mgr.should_ignore('/home/user/private.key') == True
            assert filter_mgr.should_ignore('passwords/admin.txt') == True
            
            # Should not ignore other files
            assert filter_mgr.should_ignore('/etc/config.conf') == False
        finally:
            os.unlink(blacklist_file)
    
    def test_whitelist_from_file(self):
        """Test loading whitelist patterns from file (Requirement 3.3, 3.5)"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write('*.conf\n')
            f.write('*.yaml\n')
            f.write('/etc/*\n')
            whitelist_file = f.name
        
        try:
            filter_mgr = FilterManager(whitelist_file=whitelist_file, use_defaults=False)
            
            # Should NOT ignore files matching whitelist
            assert filter_mgr.should_ignore('/etc/app.conf') == False
            assert filter_mgr.should_ignore('/etc/config.yaml') == False
            assert filter_mgr.should_ignore('/etc/hosts') == False
            
            # Should ignore files NOT matching whitelist (Requirement 3.5)
            assert filter_mgr.should_ignore('/home/user/script.py') == True
            assert filter_mgr.should_ignore('/var/log/system.log') == True
        finally:
            os.unlink(whitelist_file)
    
    def test_whitelist_overrides_blacklist(self):
        """Test that whitelist takes precedence (Requirement 3.5)"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write('*.conf\n')
            whitelist_file = f.name
        
        try:
            # Even with defaults (which include *.log), whitelist should restrict
            filter_mgr = FilterManager(whitelist_file=whitelist_file, use_defaults=True)
            
            # Only .conf files should pass
            assert filter_mgr.should_ignore('/etc/app.conf') == False
            
            # Everything else should be ignored, even if not in blacklist
            assert filter_mgr.should_ignore('/etc/app.yaml') == True
            assert filter_mgr.should_ignore('/etc/script.py') == True
        finally:
            os.unlink(whitelist_file)
    
    def test_glob_pattern_matching(self):
        """Test glob pattern matching with wildcards (Requirement 3.4, 3.5)"""
        filter_mgr = FilterManager(use_defaults=False)
        
        # Add patterns with wildcards
        filter_mgr.add_blacklist_pattern('test_*.py')
        filter_mgr.add_blacklist_pattern('*.tmp')
        filter_mgr.add_blacklist_pattern('backup_??.sql')
        
        # Test * wildcard
        assert filter_mgr.should_ignore('test_file.py') == True
        assert filter_mgr.should_ignore('test_another.py') == True
        assert filter_mgr.should_ignore('data.tmp') == True
        
        # Test ? wildcard
        assert filter_mgr.should_ignore('backup_01.sql') == True
        assert filter_mgr.should_ignore('backup_99.sql') == True
        
        # Should not match
        assert filter_mgr.should_ignore('test.py') == False
        assert filter_mgr.should_ignore('backup_001.sql') == False
    
    def test_directory_patterns(self):
        """Test directory-based patterns"""
        filter_mgr = FilterManager(use_defaults=False)
        
        filter_mgr.add_blacklist_pattern('.git/*')
        filter_mgr.add_blacklist_pattern('node_modules/*')
        
        # Should ignore files in these directories
        assert filter_mgr.should_ignore('.git/config') == True
        assert filter_mgr.should_ignore('.git/HEAD') == True
        assert filter_mgr.should_ignore('node_modules/package.json') == True
        
        # Should not ignore files outside these directories
        assert filter_mgr.should_ignore('src/config') == False
    
    def test_add_remove_patterns(self):
        """Test adding and removing patterns at runtime"""
        filter_mgr = FilterManager(use_defaults=False)
        
        # Add pattern
        filter_mgr.add_blacklist_pattern('*.test')
        assert filter_mgr.should_ignore('file.test') == True
        
        # Remove pattern
        filter_mgr.remove_blacklist_pattern('*.test')
        assert filter_mgr.should_ignore('file.test') == False
        
        # Whitelist patterns
        filter_mgr.add_whitelist_pattern('*.conf')
        assert filter_mgr.should_ignore('app.conf') == False
        assert filter_mgr.should_ignore('app.yaml') == True
        
        filter_mgr.remove_whitelist_pattern('*.conf')
        assert filter_mgr.should_ignore('app.yaml') == False
    
    def test_get_patterns(self):
        """Test retrieving pattern lists"""
        filter_mgr = FilterManager(use_defaults=False)
        
        filter_mgr.add_blacklist_pattern('*.tmp')
        filter_mgr.add_blacklist_pattern('*.log')
        
        blacklist = filter_mgr.get_blacklist_patterns()
        assert '*.tmp' in blacklist
        assert '*.log' in blacklist
        assert len(blacklist) == 2
        
        filter_mgr.add_whitelist_pattern('*.conf')
        whitelist = filter_mgr.get_whitelist_patterns()
        assert '*.conf' in whitelist
        assert len(whitelist) == 1
    
    def test_clear_patterns(self):
        """Test clearing pattern lists"""
        filter_mgr = FilterManager(use_defaults=True)
        
        # Clear blacklist but keep defaults
        initial_count = len(filter_mgr.get_blacklist_patterns())
        filter_mgr.add_blacklist_pattern('*.custom')
        assert len(filter_mgr.get_blacklist_patterns()) == initial_count + 1
        
        filter_mgr.clear_blacklist(keep_defaults=True)
        assert len(filter_mgr.get_blacklist_patterns()) == initial_count
        
        # Clear blacklist including defaults
        filter_mgr.clear_blacklist(keep_defaults=False)
        assert len(filter_mgr.get_blacklist_patterns()) == 0
        
        # Clear whitelist
        filter_mgr.add_whitelist_pattern('*.conf')
        assert len(filter_mgr.get_whitelist_patterns()) == 1
        filter_mgr.clear_whitelist()
        assert len(filter_mgr.get_whitelist_patterns()) == 0
    
    def test_path_normalization(self):
        """Test that paths are normalized correctly across platforms"""
        filter_mgr = FilterManager(use_defaults=False)
        filter_mgr.add_blacklist_pattern('*.tmp')
        
        # Test with different path separators
        assert filter_mgr.should_ignore('C:\\Users\\test\\file.tmp') == True
        assert filter_mgr.should_ignore('/home/user/file.tmp') == True
        assert filter_mgr.should_ignore('./file.tmp') == True
    
    def test_file_not_found_error(self):
        """Test that FileNotFoundError is raised for missing pattern files"""
        with pytest.raises(FileNotFoundError):
            FilterManager(blacklist_file='/nonexistent/file.txt')
    
    def test_invalid_pattern_file(self):
        """Test that ValueError is raised for invalid pattern file"""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Try to use a directory as a pattern file
            with pytest.raises(ValueError):
                FilterManager(blacklist_file=tmpdir)
    
    def test_combined_blacklist_and_whitelist(self):
        """Test using both blacklist and whitelist together"""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as bf:
            bf.write('*.log\n')
            bf.write('*.tmp\n')
            blacklist_file = bf.name
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as wf:
            wf.write('*.conf\n')
            wf.write('*.yaml\n')
            whitelist_file = wf.name
        
        try:
            filter_mgr = FilterManager(
                blacklist_file=blacklist_file,
                whitelist_file=whitelist_file,
                use_defaults=False
            )
            
            # Whitelist takes precedence - only .conf and .yaml allowed
            assert filter_mgr.should_ignore('app.conf') == False
            assert filter_mgr.should_ignore('config.yaml') == False
            
            # Everything else ignored (including blacklisted items)
            assert filter_mgr.should_ignore('system.log') == True
            assert filter_mgr.should_ignore('data.tmp') == True
            assert filter_mgr.should_ignore('script.py') == True
        finally:
            os.unlink(blacklist_file)
            os.unlink(whitelist_file)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
