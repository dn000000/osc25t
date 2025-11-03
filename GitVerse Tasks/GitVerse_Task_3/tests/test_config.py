"""
Tests for Config class.
"""

import json
import os
import tempfile
import pytest
from gitproc.config import Config


def test_config_default_values():
    """Test that Config has correct default values."""
    config = Config()
    
    assert config.repo_path == "/etc/gitproc/services"
    assert config.branch == "main"
    assert config.socket_path == "/var/run/gitproc.sock"
    assert config.state_file == "/var/lib/gitproc/state.json"
    assert config.log_dir == "/var/log/gitproc"
    assert config.cgroup_root == "/sys/fs/cgroup/gitproc"


def test_config_load_from_file():
    """Test loading configuration from JSON file."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
        config_data = {
            "repo_path": "/custom/path",
            "branch": "develop",
            "socket_path": "/tmp/gitproc.sock",
            "state_file": "/tmp/state.json",
            "log_dir": "/tmp/logs",
            "cgroup_root": "/sys/fs/cgroup/custom"
        }
        json.dump(config_data, f)
        config_path = f.name
    
    try:
        config = Config.load(config_path)
        
        assert config.repo_path == "/custom/path"
        assert config.branch == "develop"
        assert config.socket_path == "/tmp/gitproc.sock"
        assert config.state_file == "/tmp/state.json"
        assert config.log_dir == "/tmp/logs"
        assert config.cgroup_root == "/sys/fs/cgroup/custom"
    finally:
        os.unlink(config_path)


def test_config_load_missing_file():
    """Test that loading non-existent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        Config.load("/nonexistent/config.json")


def test_config_load_or_default():
    """Test load_or_default returns default config when file doesn't exist."""
    config = Config.load_or_default("/nonexistent/config.json")
    
    assert config.repo_path == "/etc/gitproc/services"
    assert config.branch == "main"


def test_config_save():
    """Test saving configuration to JSON file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = os.path.join(tmpdir, "config.json")
        
        config = Config(
            repo_path="/test/path",
            branch="test-branch"
        )
        config.save(config_path)
        
        assert os.path.exists(config_path)
        
        # Load and verify
        loaded_config = Config.load(config_path)
        assert loaded_config.repo_path == "/test/path"
        assert loaded_config.branch == "test-branch"
