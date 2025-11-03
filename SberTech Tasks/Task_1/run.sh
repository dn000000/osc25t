#!/bin/bash
set -e

echo "=========================================="
echo "RPM Dependency Graph System"
echo "=========================================="
echo ""

# Check for repository URL argument
if [ $# -eq 0 ]; then
    echo "Error: Repository URL is required"
    echo ""
    echo "Usage: ./run.sh <repository-url> [options]"
    echo ""
    echo "Example:"
    echo "  ./run.sh https://example.com/openscaler/repo"
    echo "  ./run.sh https://example.com/openscaler/repo --verbose"
    echo "  ./run.sh https://example.com/openscaler/repo --clear-cache"
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

# Run main script to build graphs
echo "Building dependency graphs from: $REPO_URL"
echo ""
echo "Note: The system will automatically:"
echo "  - Try standard repository metadata first"
echo "  - Fall back to HTML parsing if metadata is unavailable"
echo "  - Extract dependencies from RPM files if needed"
echo ""
echo "This may take a few minutes..."
echo ""

python -m src.main --repo-url "$REPO_URL" "$@"

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
