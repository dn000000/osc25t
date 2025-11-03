"""Shared pytest fixtures and configuration for sysaudit tests"""

import os
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
import pytest

from sysaudit.models import Config, FileEvent, ProcessInfo


@pytest.fixture
def temp_dir():
    """Create a temporary directory for testing"""
    tmpdir = tempfile.mkdtemp(prefix='sysaudit_test_')
    yield tmpdir
    shutil.rmtree(tmpdir, ignore_errors=True)


@pytest.fixture
def temp_dirs():
    """Create multiple temporary directories for testing"""
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
def test_config(temp_dirs):
    """Create a test configuration"""
    return Config(
        repo_path=temp_dirs['repo'],
        watch_paths=[temp_dirs['watch']],
        baseline_branch='main',
        gpg_sign=False,
        auto_compliance=False,
        webhook_url=None
    )


@pytest.fixture
def test_file(temp_dir):
    """Create a test file"""
    file_path = Path(temp_dir) / 'test.txt'
    file_path.write_text('test content')
    return str(file_path)


@pytest.fixture
def test_files(temp_dir):
    """Create multiple test files"""
    files = []
    for i in range(3):
        file_path = Path(temp_dir) / f'test{i}.txt'
        file_path.write_text(f'content {i}')
        files.append(str(file_path))
    return files


@pytest.fixture
def sample_file_event(test_file):
    """Create a sample FileEvent"""
    return FileEvent(
        path=test_file,
        event_type='created',
        timestamp=datetime.now(),
        process_info=ProcessInfo(
            pid=1234,
            name='test_process',
            cmdline='test command'
        )
    )


@pytest.fixture
def sample_file_events(test_files):
    """Create multiple sample FileEvents"""
    events = []
    for file_path in test_files:
        events.append(FileEvent(
            path=file_path,
            event_type='created',
            timestamp=datetime.now(),
            process_info=None
        ))
    return events


@pytest.fixture
def blacklist_file(temp_dir):
    """Create a test blacklist file"""
    blacklist_path = Path(temp_dir) / 'blacklist.txt'
    blacklist_path.write_text('*.tmp\n*.log\n*.swp\n')
    return str(blacklist_path)


@pytest.fixture
def whitelist_file(temp_dir):
    """Create a test whitelist file"""
    whitelist_path = Path(temp_dir) / 'whitelist.txt'
    whitelist_path.write_text('*.conf\n*.yaml\n')
    return str(whitelist_path)


@pytest.fixture
def config_yaml_file(temp_dir):
    """Create a test YAML configuration file"""
    config_path = Path(temp_dir) / 'config.yaml'
    config_content = """
repository:
  path: /var/lib/sysaudit
  baseline: main
  gpg_sign: false

monitoring:
  paths:
    - /etc
    - /usr/local/bin
  batch_interval: 5
  batch_size: 10

compliance:
  auto_check: false

alerts:
  enabled: false
  webhook_url: null
"""
    config_path.write_text(config_content)
    return str(config_path)


# Platform-specific fixtures
@pytest.fixture
def skip_on_windows():
    """Skip test on Windows platform"""
    if sys.platform == 'win32':
        pytest.skip("Test not supported on Windows")


@pytest.fixture
def skip_on_unix():
    """Skip test on Unix platforms"""
    if sys.platform != 'win32':
        pytest.skip("Test not supported on Unix")


# Helper functions available to all tests
def create_file_with_permissions(path, mode=0o644):
    """Create a file with specific permissions (Unix only)"""
    Path(path).touch()
    if sys.platform != 'win32':
        os.chmod(path, mode)
    return path


def create_directory_structure(base_dir, structure):
    """
    Create a directory structure from a dict.
    
    Example:
        structure = {
            'dir1': {
                'file1.txt': 'content1',
                'file2.txt': 'content2'
            },
            'dir2': {
                'subdir': {
                    'file3.txt': 'content3'
                }
            }
        }
    """
    for name, content in structure.items():
        path = Path(base_dir) / name
        if isinstance(content, dict):
            path.mkdir(parents=True, exist_ok=True)
            create_directory_structure(path, content)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)


# Make helper functions available as fixtures
@pytest.fixture
def create_file_helper():
    """Fixture that provides create_file_with_permissions function"""
    return create_file_with_permissions


@pytest.fixture
def create_structure_helper():
    """Fixture that provides create_directory_structure function"""
    return create_directory_structure


# Session-scoped fixtures for expensive setup
@pytest.fixture(scope="session")
def test_data_dir():
    """Create a session-scoped test data directory"""
    data_dir = tempfile.mkdtemp(prefix='sysaudit_testdata_')
    yield data_dir
    shutil.rmtree(data_dir, ignore_errors=True)


# Markers for test categorization
def pytest_configure(config):
    """Register custom markers"""
    config.addinivalue_line(
        "markers", "unit: mark test as a unit test"
    )
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )
    config.addinivalue_line(
        "markers", "compliance: mark test as a compliance test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "requires_git: mark test as requiring git"
    )
    config.addinivalue_line(
        "markers", "requires_unix: mark test as requiring Unix platform"
    )
