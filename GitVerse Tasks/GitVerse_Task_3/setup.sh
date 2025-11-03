#!/bin/bash
# Installation script for GitProc on Linux/Unix systems

set -e

echo "=========================================="
echo "GitProc Installation Script"
echo "=========================================="
echo ""

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed."
    echo "Please install Python 3.8 or higher and try again."
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(".".join(map(str, sys.version_info[:2])))')
REQUIRED_VERSION="3.8"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "Error: Python $PYTHON_VERSION is installed, but Python $REQUIRED_VERSION or higher is required."
    exit 1
fi

echo "Python $PYTHON_VERSION detected - OK"
echo ""

# Check if pip is installed
echo "Checking for pip..."
if ! command -v pip3 &> /dev/null; then
    echo "pip3 not found. Attempting to install pip..."
    python3 -m ensurepip --default-pip || {
        echo "Error: Failed to install pip."
        echo "Please install pip manually and try again."
        exit 1
    }
fi

echo "pip is available - OK"
echo ""

# Install dependencies
echo "Installing Python dependencies..."
pip3 install -r requirements.txt || {
    echo "Error: Failed to install dependencies."
    exit 1
}

echo ""
echo "Dependencies installed successfully!"
echo ""

# Make CLI executable (if it exists)
if [ -f "gitproc/cli.py" ]; then
    chmod +x gitproc/cli.py
    echo "Made gitproc CLI executable"
fi

echo "=========================================="
echo "Installation completed successfully!"
echo "=========================================="
echo ""
echo "To get started:"
echo "  1. Initialize a repository: python3 -m gitproc.cli init --repo /path/to/services"
echo "  2. Start the daemon: python3 -m gitproc.cli daemon"
echo ""
echo "For more information, see docs/README.md"
