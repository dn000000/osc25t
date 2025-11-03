#!/bin/bash
# Docker-based test runner for GitProc
# Runs all tests in a Linux container and displays results

set -e

echo "========================================="
echo "GitProc Docker Test Pipeline"
echo "========================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed"
    echo "Please install Docker and try again"
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo "Error: Docker daemon is not running"
    echo "Please start Docker and try again"
    exit 1
fi

echo "Docker detected - OK"
echo ""

# Parse command line arguments
BUILD_FLAG="--build"
DETACH_FLAG=""
EXTRA_ARGS=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-build)
            BUILD_FLAG=""
            shift
            ;;
        --detach|-d)
            DETACH_FLAG="-d"
            shift
            ;;
        *)
            EXTRA_ARGS="$EXTRA_ARGS $1"
            shift
            ;;
    esac
done

# Build and run tests using docker-compose
echo "Building test container..."
echo ""

if [ -n "$BUILD_FLAG" ]; then
    docker-compose -f docker-compose.test.yml build
    echo ""
fi

echo "Running tests in container..."
echo ""

# Run the tests
docker-compose -f docker-compose.test.yml run --rm $DETACH_FLAG test $EXTRA_ARGS

EXIT_CODE=$?

echo ""
if [ $EXIT_CODE -eq 0 ]; then
    echo "========================================="
    echo "✓ All tests passed successfully!"
    echo "========================================="
    echo ""
    echo "View detailed coverage report:"
    echo "  Open: htmlcov/index.html"
else
    echo "========================================="
    echo "✗ Tests failed with exit code: $EXIT_CODE"
    echo "========================================="
fi

echo ""
echo "Cleaning up..."
docker-compose -f docker-compose.test.yml down 2>/dev/null || true

exit $EXIT_CODE
