"""
Pytest configuration and shared fixtures.
"""

import pytest
import tempfile
from pathlib import Path

from tests.fixtures.sample_repository import (
    get_sample_package_list,
    get_linear_dependencies,
    get_circular_dependencies,
    get_missing_dependencies,
    get_complex_dependencies,
    get_self_loop_dependencies,
    get_multiple_circular_dependencies,
    get_mixed_runtime_and_build_dependencies,
)


@pytest.fixture
def temp_cache_dir():
    """Create a temporary cache directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def temp_output_dir():
    """Create a temporary output directory for tests"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def sample_package_list():
    """Provide sample package list"""
    return get_sample_package_list()


@pytest.fixture
def linear_dependencies():
    """Provide packages with linear dependencies"""
    return get_linear_dependencies()


@pytest.fixture
def circular_dependencies():
    """Provide packages with circular dependencies"""
    return get_circular_dependencies()


@pytest.fixture
def missing_dependencies():
    """Provide packages with missing dependencies"""
    return get_missing_dependencies()


@pytest.fixture
def complex_dependencies():
    """Provide packages with complex dependencies"""
    return get_complex_dependencies()


@pytest.fixture
def self_loop_dependencies():
    """Provide packages with self-loop dependencies"""
    return get_self_loop_dependencies()


@pytest.fixture
def multiple_circular_dependencies():
    """Provide packages with multiple circular dependency chains"""
    return get_multiple_circular_dependencies()


@pytest.fixture
def mixed_runtime_and_build_dependencies():
    """Provide packages with both runtime and build dependencies"""
    return get_mixed_runtime_and_build_dependencies()
