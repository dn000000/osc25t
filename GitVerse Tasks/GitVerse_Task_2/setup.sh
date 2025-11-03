#!/bin/bash

# Setup script for GitConfig on Linux/Mac
# This script makes all .sh scripts executable and runs quickstart

echo "========================================"
echo "GitConfig Setup for Linux/Mac"
echo "========================================"
echo

echo "Making scripts executable..."
chmod +x scripts/*.sh
echo "✓ Scripts are now executable"

echo
echo "Running quickstart..."
bash scripts/quickstart.sh

echo
echo "========================================"
echo "Setup Complete!"
echo "========================================"
echo
echo "You can now use:"
echo "  bash scripts/quickstart.sh"
echo "  bash scripts/install.sh"
echo "  bash scripts/demo.sh"
echo "  bash scripts/run_all_tests.sh"
echo
