#!/bin/bash
set -e

echo "=========================================="
echo "RPM Dependency Graph System"
echo "WITH DEPENDENCY EXTRACTION"
echo "=========================================="
echo ""
echo "WARNING: This will download all RPM files from the repository"
echo "This process may take a long time depending on:"
echo "  - Number of packages"
echo "  - Size of RPM files"
echo "  - Network speed"
echo ""

# Check for repository URL argument
if [ $# -eq 0 ]; then
    echo "Error: Repository URL is required"
    echo ""
    echo "Usage: ./run_with_deps.sh <repository-url> [--max-packages N]"
    echo ""
    echo "Example:"
    echo "  ./run_with_deps.sh https://example.com/openscaler/repo"
    echo "  ./run_with_deps.sh https://example.com/openscaler/repo --max-packages 100"
    echo ""
    exit 1
fi

REPO_URL="$1"
shift  # Remove first argument, keep remaining options

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "Error: Virtual environment not found"
    echo "Please run ./install.sh first"
    echo ""
    exit 1
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate
echo "✓ Virtual environment activated"
echo ""

# Run main script with --extract-deps flag
echo "Building dependency graphs from: $REPO_URL"
echo ""
echo "Mode: Full dependency extraction"
echo "  - Downloads RPM files from repository"
echo "  - Extracts dependencies from RPM headers"
echo "  - Builds complete dependency graphs"
echo ""
echo "This will take a while..."
echo ""

python -m src.main --repo-url "$REPO_URL" --extract-deps "$@"

# Check if graphs were created successfully
if [ $? -eq 0 ]; then
    echo ""
    echo "=========================================="
    echo "✓ Graphs built successfully!"
    echo "=========================================="
    echo ""
    echo "Starting web server..."
    echo ""
    
    # Start Flask server
    echo "Web server starting on http://localhost:5000"
    echo ""
    echo "Press Ctrl+C to stop the server"
    echo ""
    
    python -m src.server
else
    echo ""
    echo "=========================================="
    echo "✗ Error: Failed to build graphs"
    echo "=========================================="
    echo ""
    echo "Please check the error messages above and try again."
    echo ""
    exit 1
fi
