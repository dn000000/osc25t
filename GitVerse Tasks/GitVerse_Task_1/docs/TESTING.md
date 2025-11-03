# Testing Guide for Sysaudit

This document provides a comprehensive guide to testing the sysaudit system.

## Quick Start

```bash
# Install development dependencies
pip install -e .[dev]

# Run all tests
python run_tests.py

# Run tests with coverage
python run_tests.py --coverage

# Run specific test file
python run_tests.py tests/test_filter.py
```

## Test Runner

The project includes a custom test runner (`run_tests.py`) that wraps pytest with convenient options.

### Basic Usage

```bash
# Run all tests
python run_tests.py

# Run with verbose output
python run_tests.py --verbose

# Run with quiet output (summary only)
python run_tests.py --quiet

# Stop on first failure
python run_tests.py --failfast
```

### Test Selection

```bash
# Run only unit tests
python run_tests.py --unit

# Run only integration tests
python run_tests.py --integration

# Run only compliance tests
python run_tests.py --compliance

# Skip slow tests
python run_tests.py --fast

# Run specific test file
python run_tests.py tests/test_filter.py

# Run specific test class
python run_tests.py tests/test_filter.py::TestFilterManager

# Run specific test method
python run_tests.py tests/test_filter.py::TestFilterManager::test_default_ignore_patterns
```

### Coverage Reports

```bash
# Generate terminal coverage report
python run_tests.py --coverage

# Generate HTML coverage report
python run_tests.py --html-coverage
# Then open htmlcov/index.html in your browser
```

### Advanced Options

```bash
# Run tests in parallel (requires pytest-xdist)
python run_tests.py --parallel 4

# Run only tests that failed last time
python run_tests.py --last-failed

# Run failed tests first, then others
python run_tests.py --failed-first

# Pass additional pytest arguments
python run_tests.py --pytest-args -k filter
```

## Using Make

If you have `make` installed, you can use convenient shortcuts:

```bash
# Run all tests
make test

# Run unit tests only
make test-unit

# Run integration tests only
make test-integration

# Run compliance tests only
make test-compliance

# Run tests with coverage
make test-coverage

# Run tests with HTML coverage
make test-html

# Skip slow tests
make test-fast

# Run linting checks
make lint

# Format code
make format

# Run all checks (lint + test)
make check

# Clean build artifacts
make clean
```

## Using Pytest Directly

You can also use pytest directly for more control:

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=sysaudit --cov-report=term-missing

# Run specific test file
pytest tests/test_filter.py

# Run tests matching a pattern
pytest -k "filter"

# Run tests with specific marker
pytest -m unit

# Verbose output with local variables
pytest -vv -l

# Show print statements
pytest -s

# Run in parallel
pytest -n 4
```

## Test Organization

### Test Files

- `test_filter.py` - FilterManager tests (Requirement 3)
- `test_file_monitor.py` - FileMonitor tests (Requirements 1, 4)
- `test_git_manager.py` - GitManager tests (Requirement 2)
- `test_drift_detector.py` - DriftDetector tests (Requirement 5)
- `test_compliance.py` - Compliance checking tests (Requirement 6)
- `test_alert_manager.py` - AlertManager tests (Requirement 13)
- `test_rollback_manager.py` - RollbackManager tests (Requirement 8)
- `test_engine.py` - AuditEngine tests (Requirements 1, 2, 6)
- `test_systemd_service.sh` - Systemd service tests (Requirement 7)

### Test Markers

Tests are categorized using pytest markers:

- `@pytest.mark.unit` - Unit tests for individual components
- `@pytest.mark.integration` - Integration tests for component interactions
- `@pytest.mark.compliance` - Compliance checking tests
- `@pytest.mark.slow` - Tests that take longer to run
- `@pytest.mark.requires_git` - Tests that require git to be installed
- `@pytest.mark.requires_unix` - Tests that require Unix platform

### Shared Fixtures

Common fixtures are defined in `tests/conftest.py`:

**Directory Fixtures:**
- `temp_dir` - Single temporary directory
- `temp_dirs` - Multiple temporary directories (repo and watch)
- `test_data_dir` - Session-scoped test data directory

**Configuration Fixtures:**
- `test_config` - Test configuration object
- `config_yaml_file` - Test YAML configuration file

**File Fixtures:**
- `test_file` - Single test file
- `test_files` - Multiple test files
- `blacklist_file` - Test blacklist file
- `whitelist_file` - Test whitelist file

**Event Fixtures:**
- `sample_file_event` - Single FileEvent object
- `sample_file_events` - Multiple FileEvent objects

**Helper Fixtures:**
- `create_file_helper` - Function to create files with permissions
- `create_structure_helper` - Function to create directory structures
- `skip_on_windows` - Skip test on Windows
- `skip_on_unix` - Skip test on Unix

## Writing Tests

### Basic Test Structure

```python
import pytest
from sysaudit.monitor.filter import FilterManager

@pytest.mark.unit
def test_filter_ignores_tmp_files():
    """Test that temporary files are ignored"""
    filter_mgr = FilterManager()
    assert filter_mgr.should_ignore('/tmp/test.tmp') == True
```

### Using Fixtures

```python
def test_with_temp_dir(temp_dir):
    """Test using temporary directory fixture"""
    from pathlib import Path
    test_file = Path(temp_dir) / 'test.txt'
    test_file.write_text('content')
    assert test_file.exists()

def test_with_config(test_config):
    """Test using configuration fixture"""
    assert test_config.baseline_branch == 'main'
    assert test_config.gpg_sign == False
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

### Integration Tests

```python
@pytest.mark.integration
def test_end_to_end_monitoring(test_config, test_file):
    """Test complete monitoring workflow"""
    from sysaudit.core.engine import AuditEngine
    
    engine = AuditEngine(test_config)
    engine.start_monitoring()
    
    # Modify file
    Path(test_file).write_text('modified content')
    
    # Wait for processing
    time.sleep(2)
    
    # Verify commit was created
    assert engine.git_manager.get_latest_commit() is not None
```

### Compliance Tests

```python
@pytest.mark.compliance
def test_world_writable_detection(temp_dir, create_file_helper):
    """Test detection of world-writable files"""
    from sysaudit.compliance import WorldWritableRule
    
    rule = WorldWritableRule()
    test_file = create_file_helper(
        f"{temp_dir}/etc/test",
        mode=0o666
    )
    
    issue = rule.check(test_file)
    assert issue is not None
    assert issue.severity == 'HIGH'
```

## Best Practices

### 1. Test Naming

- Use descriptive test names that explain what is being tested
- Start test functions with `test_`
- Use `Test` prefix for test classes

```python
# Good
def test_filter_ignores_tmp_files():
    pass

# Bad
def test1():
    pass
```

### 2. Test Documentation

- Add docstrings to explain what the test does
- Reference requirements in comments

```python
def test_filter_ignores_tmp_files():
    """Test that temporary files are ignored (Requirement 3.1)"""
    pass
```

### 3. Test Independence

- Each test should be independent
- Use fixtures for setup and teardown
- Don't rely on test execution order

```python
# Good - uses fixture
def test_with_clean_state(temp_dir):
    # Fresh temporary directory for each test
    pass

# Bad - relies on global state
global_state = []

def test_modifies_global():
    global_state.append(1)
    
def test_depends_on_previous():
    assert len(global_state) == 1  # Fragile!
```

### 4. Assertions

- Use clear, specific assertions
- One logical assertion per test (when possible)
- Use pytest's rich assertion introspection

```python
# Good
assert result == expected_value
assert 'error' in error_message
assert len(items) == 3

# Avoid
assert result  # Too vague
```

### 5. Test Data

- Use fixtures for test data
- Keep test data minimal and focused
- Use realistic but simple examples

```python
@pytest.fixture
def sample_config():
    return Config(
        repo_path='/tmp/repo',
        watch_paths=['/tmp/watch'],
        baseline_branch='main'
    )
```

### 6. Error Testing

- Test both success and failure cases
- Use `pytest.raises` for expected exceptions

```python
def test_invalid_config_raises_error():
    """Test that invalid configuration raises ValueError"""
    with pytest.raises(ValueError):
        Config(repo_path=None)
```

### 7. Mocking

- Avoid mocking when testing real functionality
- Mock external dependencies (network, filesystem)
- Use `pytest-mock` or `unittest.mock`

```python
def test_webhook_failure_handled(mocker):
    """Test that webhook failures don't crash the system"""
    mock_post = mocker.patch('requests.post')
    mock_post.side_effect = Exception("Network error")
    
    # Should not raise
    alert_manager.send_webhook(issue)
```

## Continuous Integration

The test suite is designed to run in CI environments:

```yaml
# Example GitHub Actions workflow
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.8', '3.9', '3.10', '3.11']
    
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          pip install -e .[dev]
      
      - name: Run tests
        run: |
          python run_tests.py --coverage
      
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## Troubleshooting

### Tests Fail on Windows

Some tests require Unix-specific features and will be automatically skipped on Windows. This is expected.

### Import Errors

```bash
# Install package in development mode
pip install -e .
```

### Missing Dependencies

```bash
# Install development dependencies
pip install -e .[dev]
```

### Slow Tests

```bash
# Skip slow tests during development
python run_tests.py --fast
```

### Coverage Not Working

```bash
# Make sure pytest-cov is installed
pip install pytest-cov

# Run with coverage explicitly
pytest --cov=sysaudit
```

### Tests Hang

- Check for infinite loops
- Check for blocking I/O operations
- Use timeout markers for long-running tests

```python
@pytest.mark.timeout(10)
def test_might_hang():
    pass
```

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest fixtures](https://docs.pytest.org/en/stable/fixture.html)
- [pytest markers](https://docs.pytest.org/en/stable/mark.html)
- [pytest-cov documentation](https://pytest-cov.readthedocs.io/)
- [Python unittest.mock](https://docs.python.org/3/library/unittest.mock.html)

## Getting Help

- Check `tests/README.md` for test suite documentation
- Run `python run_tests.py --help` for test runner options
- Run `pytest --help` for pytest options
- Check existing tests for examples
