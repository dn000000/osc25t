#!/bin/bash
# Test runner script for GitProc
# Executes all tests with pytest and generates coverage report

set -e

echo "========================================="
echo "GitProc Test Suite"
echo "========================================="
echo ""

# Check if pytest is installed
if ! command -v pytest &> /dev/null; then
    echo "Error: pytest is not installed"
    echo "Please install it with: pip install pytest pytest-cov"
    exit 1
fi

# Check if pytest-cov is installed
if ! python -c "import pytest_cov" &> /dev/null; then
    echo "Warning: pytest-cov is not installed"
    echo "Coverage report will not be generated"
    echo "Install it with: pip install pytest-cov"
    echo ""
    RUN_COVERAGE=false
else
    RUN_COVERAGE=true
fi

# Set Python path to include current directory
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

echo "Running tests..."
echo ""

# Run tests with or without coverage
if [ "$RUN_COVERAGE" = true ]; then
    pytest tests/ \
        --verbose \
        --tb=short \
        --cov=gitproc \
        --cov-report=term-missing \
        --cov-report=html:htmlcov \
        --cov-report=xml:coverage.xml \
        "$@"
    
    echo ""
    echo "========================================="
    echo "Coverage report generated:"
    echo "  - Terminal: (shown above)"
    echo "  - HTML: htmlcov/index.html"
    echo "  - XML: coverage.xml"
    echo "========================================="
else
    pytest tests/ \
        --verbose \
        --tb=short \
        "$@"
fi

echo ""
echo "========================================="
echo "Test suite completed successfully!"
echo "========================================="
