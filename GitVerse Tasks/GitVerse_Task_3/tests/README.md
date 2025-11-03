# GitProc Test Suite

This directory contains the comprehensive test suite for GitProc.

## Test Structure

- **test_helpers.py** - Test fixtures and helper utilities
  - `TestHelper` - Helper class for creating test unit files, repositories, and scripts
  - `MockHTTPServer` - Mock HTTP server for health check testing
  - `ProcessHelper` - Helper for managing test processes

- **test_e2e_integration.py** - End-to-end integration tests
  - Complete workflow tests (init → daemon → service management)
  - Auto-restart workflow tests
  - Git sync workflow tests
  - Rollback workflow tests
  - Dependency workflow tests
  - Resource limit workflow tests
  - Health check workflow tests
  - Multi-service workflow tests
  - Log capture tests

- **test_*.py** - Unit and integration tests for individual components
  - test_parser.py - Unit file parser tests
  - test_state_manager.py - State management tests
  - test_git_integration.py - Git integration tests
  - test_resource_controller.py - Resource controller tests
  - test_process_manager.py - Process manager tests
  - test_dependency_resolver.py - Dependency resolver tests
  - test_health_monitor.py - Health monitor tests
  - test_daemon.py - Daemon integration tests
  - test_cli.py - CLI interface tests
  - test_config.py - Configuration tests

## Running Tests

### Run All Tests

**Linux/Unix:**
```bash
./run_tests.sh
```

**Windows:**
```cmd
run_tests.bat
```

### Run Specific Test File

```bash
python -m pytest tests/test_parser.py -v
```

### Run Specific Test

```bash
python -m pytest tests/test_parser.py::TestUnitFileParser::test_parse_valid_unit_file -v
```

### Run Tests with Coverage

```bash
python -m pytest tests/ --cov=gitproc --cov-report=html
```

### Run Tests Matching Pattern

```bash
python -m pytest tests/ -k "test_auto_restart" -v
```

### Skip Windows-Incompatible Tests

Some tests require Unix-specific features (PID namespaces, cgroups) and are automatically skipped on Windows using the `@SKIP_ON_WINDOWS` decorator.

## Test Requirements

Install test dependencies:

```bash
pip install pytest pytest-cov pytest-timeout pytest-mock
```

## Test Coverage

The test suite aims for >80% code coverage across all components. Coverage reports are generated in:
- Terminal output (summary)
- `htmlcov/index.html` (detailed HTML report)
- `coverage.xml` (XML format for CI/CD)

## Writing New Tests

When adding new tests:

1. Use the `TestHelper` class for creating test fixtures
2. Use `@SKIP_ON_WINDOWS` decorator for Unix-specific tests
3. Clean up resources in `finally` blocks
4. Use descriptive test names that explain what is being tested
5. Follow the existing test structure and patterns

## Continuous Integration

The test suite is designed to run in CI/CD environments. Use the test runner scripts or run pytest directly:

```bash
python -m pytest tests/ --verbose --tb=short --cov=gitproc --cov-report=xml
```
