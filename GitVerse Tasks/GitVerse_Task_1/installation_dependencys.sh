#!/bin/bash
# Simple setup script for sysaudit project
# Installs all dependencies needed for development

set -e

echo "=========================================="
echo "Sysaudit Setup Script"
echo "=========================================="
echo ""

# Check Python
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    echo "Install with: sudo apt-get install python3 python3-pip"
    exit 1
fi

PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "Found Python $PYTHON_VERSION"

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 is not installed"
    echo "Install with: sudo apt-get install python3-pip"
    exit 1
fi

echo "Found pip3"
echo ""

# Install dependencies
echo "Installing project dependencies..."
echo ""

if [ -f "Makefile" ]; then
    echo "Using Makefile to install..."
    make install-dev
else
    echo "Installing with pip..."
    pip3 install -e .[dev]
fi

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Dependencies installed:"
echo "  - watchdog (file monitoring)"
echo "  - GitPython (git operations)"
echo "  - click (CLI framework)"
echo "  - PyYAML (config files)"
echo "  - requests (HTTP requests)"
echo "  - pytest (testing)"
echo "  - pytest-cov (coverage)"
echo ""
echo "Next steps:"
echo "  - Run tests: make test"
echo "  - Run specific tests: python run_tests.py"
echo "  - Install system-wide: sudo ./install_system-wide.sh"
echo ""
