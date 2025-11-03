#!/bin/bash

echo "Installing dependencies for GitConfig..."
echo
python3 -m pip install --upgrade pip
python3 -m pip install -r requirements.txt
echo
echo "Installation complete!"
echo
echo "To run demos:"
echo "  python3 examples/full_demo.py"
echo "  python3 examples/example_usage.py"
echo
echo "To run tests:"
echo "  python3 tests/test_gitconfig.py"
echo "  python3 tests/test_http_api.py"
echo
echo "To start a node:"
echo "  python3 src/gitconfig_node.py start --repo ./data/node1 --http-port 8080"
