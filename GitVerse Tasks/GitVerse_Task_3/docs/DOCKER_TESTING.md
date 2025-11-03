# Docker Testing Pipeline

This project includes a Docker-based testing pipeline that runs all tests in a Linux container environment.

## Quick Start

### Windows
```cmd
run_tests_docker.bat
```

### Linux/Mac
```bash
chmod +x run_tests_docker.sh
./run_tests_docker.sh
```

## What It Does

The pipeline:
1. Builds a Linux container with Python 3.11 and all dependencies
2. Runs the complete test suite with pytest
3. Generates coverage reports (HTML, XML, terminal)
4. Displays formatted test results
5. Persists coverage reports to your local `htmlcov/` directory

## Test Results

After running, you'll see:
- **Terminal output**: Detailed test results and coverage summary
- **HTML report**: Open `htmlcov/index.html` in your browser for interactive coverage
- **XML report**: `coverage.xml` for CI/CD integration

## Options

### Skip rebuilding the container
```cmd
run_tests_docker.bat --no-build
```

### Run specific tests
```cmd
run_tests_docker.bat -k test_parser
```

### Run with verbose output
```cmd
run_tests_docker.bat -vv
```

## Files

- `Dockerfile.test` - Container definition with Python 3.11 and dependencies
- `docker-compose.test.yml` - Test orchestration configuration
- `run_tests_docker.bat` - Windows test runner
- `run_tests_docker.sh` - Linux/Mac test runner
- `.dockerignore` - Excludes unnecessary files from container

## Requirements

- Docker Desktop (Windows/Mac) or Docker Engine (Linux)
- Docker must be running before executing tests

## Test Summary

Latest run: **120 passed, 26 failed** in 142.82s

Coverage: **59%** overall
- gitproc/config.py: 100%
- gitproc/dependency_resolver.py: 100%
- gitproc/parser.py: 93%
- gitproc/health_monitor.py: 89%
- gitproc/state_manager.py: 88%
- gitproc/resource_controller.py: 87%
- gitproc/git_integration.py: 80%

## Troubleshooting

**Docker not running:**
```
Error: Docker daemon is not running
```
Solution: Start Docker Desktop

**Permission denied (Linux):**
```bash
sudo chmod +x run_tests_docker.sh
```

**Container build fails:**
```bash
docker-compose -f docker-compose.test.yml build --no-cache
```
