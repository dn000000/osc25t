# Sysaudit Test Suite

This directory contains the comprehensive test suite for the sysaudit system.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures and configuration
├── test_filter.py           # FilterManager tests
├── test_file_monitor.py     # FileMonitor tests
├── test_git_manager.py      # GitManager tests
├── test_drift_detector.py   # DriftDetector tests
├── test_compliance.py       # Compliance checking tests
├── test_alert_manager.py    # AlertManager tests
├── test_rollback_manager.py # RollbackManager tests
├── test_engine.py           # AuditEngine tests
└── test_systemd_service.sh  # Systemd service tests
```

## Running Tests

### Using the Test Runner Script

The easiest way to run tests is using the `run_tests.py` script in the project root:

```bash
# Run all tests
python run_tests.py

# Run only unit tests
python run_tests.py --unit

# Run only integration tests
python run_tests.py --integration

# Run only compliance tests
python run_tests.py --compliance

# Run with coverage report
python run_tests.py --coverage

# Run with HTML coverage report
python run_tests.py --html-coverage

# Run specific test file
python run_tests.py tests/test_filter.py

# Run tests in parallel (requires pytest-xdist)
python run_tests.py --parallel 4

# Skip slow tests
python run_tests.py --fast

# Stop on first failure
python run_tests.py --failfast

# Run only tests that failed last time
python run_tests.py --last-failed

# Verbose output
python run_tests.py --verbose
```

### Using pytest Directly

You can also run pytest directly:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=sysaudit --cov-report=term-missing

# Run specific test file
pytest tests/test_filter.py

# Run specific test class
pytest tests/test_filter.py::TestFilterManager

# Run specific test method
pytest tests/test_filter.py::TestFilterManager::test_default_ignore_patterns

# Run tests matching a pattern
pytest -k "filter"

# Run tests with specific marker
pytest -m unit
pytest -m integration
pytest -m compliance

# Verbose output
pytest -vv

# Stop on first failure
pytest -x

# Show local variables on failure
pytest -l

# Run in parallel (requires pytest-xdist)
pytest -n 4
```

## Test Categories

Tests are organized using pytest markers:

- `@pytest.mark.unit` - Unit tests for individual components
- `@pytest.mark.integration` - Integration tests for component interactions
- `@pytest.mark.compliance` - Compliance checking tests
- `@pytest.mark.slow` - Tests that take longer to run
- `@pytest.mark.requires_git` - Tests that require git to be installed
- `@pytest.mark.requires_unix` - Tests that require Unix platform

## Shared Fixtures

The `conftest.py` file provides shared fixtures available to all tests:

### Directory Fixtures
- `temp_dir` - Single temporary directory
- `temp_dirs` - Multiple temporary directories (repo and watch)
- `test_data_dir` - Session-scoped test data directory

### Configuration Fixtures
- `test_config` - Test configuration object
- `config_yaml_file` - Test YAML configuration file

### File Fixtures
- `test_file` - Single test file
- `test_files` - Multiple test files
- `blacklist_file` - Test blacklist file
- `whitelist_file` - Test whitelist file

### Event Fixtures
- `sample_file_event` - Single FileEvent object
- `sample_file_events` - Multiple FileEvent objects

### Helper Fixtures
- `create_file_helper` - Function to create files with permissions
- `create_structure_helper` - Function to create directory structures
- `skip_on_windows` - Skip test on Windows
- `skip_on_unix` - Skip test on Unix

## Writing Tests

### Example Unit Test

```python
import pytest
from sysaudit.monitor.filter import FilterManager

@pytest.mark.unit
def test_filter_ignores_tmp_files():
    """Test that temporary files are ignored"""
    filter_mgr = FilterManager()
    assert filter_mgr.should_ignore('/tmp/test.tmp') == True
```

### Example Integration Test

```python
import pytest
from sysaudit.core.engine import AuditEngine

@pytest.mark.integration
def test_end_to_end_monitoring(test_config, test_file):
    """Test complete monitoring workflow"""
    engine = AuditEngine(test_config)
    engine.start_monitoring()
    # ... test logic ...
```

### Using Fixtures

```python
def test_with_temp_dir(temp_dir):
    """Test using temporary directory fixture"""
    test_file = Path(temp_dir) / 'test.txt'
    test_file.write_text('content')
    assert test_file.exists()

def test_with_config(test_config):
    """Test using configuration fixture"""
    assert test_config.baseline_branch == 'main'
```

### Platform-Specific Tests

```python
import sys
import pytest

@pytest.mark.skipif(sys.platform == 'win32', reason="Unix only")
def test_unix_permissions():
    """Test Unix file permissions"""
    # ... Unix-specific test ...

@pytest.mark.requires_unix
def test_with_unix_fixture(skip_on_windows):
    """Test that automatically skips on Windows"""
    # ... Unix-specific test ...
```

## Coverage Reports

After running tests with coverage, you can view the reports:

```bash
# Terminal report (shown automatically)
python run_tests.py --coverage

# HTML report (open in browser)
python run_tests.py --html-coverage
# Then open htmlcov/index.html in your browser
```

## Continuous Integration

The test suite is designed to run in CI environments. Example CI configuration:

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.8'
      - run: pip install -e .[dev]
      - run: python run_tests.py --coverage
```

## Troubleshooting

### Tests Fail on Windows

Some tests require Unix-specific features (file permissions, etc.) and will be automatically skipped on Windows. This is expected behavior.

### Import Errors

Make sure sysaudit is installed in development mode:

```bash
pip install -e .
```

### Missing Dependencies

Install development dependencies:

```bash
pip install -e .[dev]
```

Or install pytest manually:

```bash
pip install pytest pytest-cov
```

### Slow Tests

Skip slow tests during development:

```bash
python run_tests.py --fast
```

## Requirements Coverage

The test suite covers all requirements from the requirements document:

- **Requirement 1**: File system monitoring - `test_file_monitor.py`
- **Requirement 2**: Git integration - `test_git_manager.py`
- **Requirement 3**: Filtering - `test_filter.py`
- **Requirement 4**: Process tracking - `test_file_monitor.py`
- **Requirement 5**: Drift detection - `test_drift_detector.py`
- **Requirement 6**: Compliance checking - `test_compliance.py`
- **Requirement 7**: Systemd integration - `test_systemd_service.sh`
- **Requirement 8**: Rollback functionality - `test_rollback_manager.py`
- **Requirement 9**: Edge cases - All test files
- **Requirement 10**: CLI interface - `test_engine.py`
- **Requirement 13**: Alerts - `test_alert_manager.py`
- **Requirement 15**: Testing - This test suite

## Contributing

When adding new tests:

1. Use appropriate markers (`@pytest.mark.unit`, etc.)
2. Use shared fixtures from `conftest.py` when possible
3. Add docstrings explaining what the test does
4. Reference requirements in comments
5. Handle platform differences appropriately
6. Keep tests focused and minimal
7. Avoid mocking when testing real functionality

## Additional Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [pytest markers](https://docs.pytest.org/en/stable/mark.html)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
