"""
Pytest configuration and fixtures for GitConfig tests
"""
import os
import platform
import pytest


def is_windows():
    """Check if running on Windows"""
    return platform.system() == 'Windows' or os.name == 'nt'


def pytest_collection_modifyitems(config, items):
    """
    Automatically skip tests marked with windows_skip on Windows platform
    """
    if is_windows():
        skip_windows = pytest.mark.skip(reason="Skipped on Windows due to file locking issues")
        for item in items:
            if "windows_skip" in item.keywords:
                item.add_marker(skip_windows)


def pytest_configure(config):
    """
    Configure pytest with custom settings
    """
    # Add custom markers
    config.addinivalue_line(
        "markers", "windows_skip: mark test to skip on Windows"
    )
    config.addinivalue_line(
        "markers", "sync: mark test as synchronization test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
