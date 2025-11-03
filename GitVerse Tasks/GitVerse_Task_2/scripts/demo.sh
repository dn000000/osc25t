#!/bin/bash

echo "========================================"
echo "GitConfig Demo"
echo "========================================"
echo

echo "Cleaning up old data..."
rm -rf demo_data example_data
mkdir -p demo_data

echo
echo "=== Creating bare repository (remote) ==="
git init --bare demo_data/bare.git

echo
echo "=== Running example scenarios ==="
python3 examples/example_usage.py

echo
echo "=== Running tests ==="
python3 tests/test_gitconfig.py

echo
echo "Demo complete!"
echo
echo "To start HTTP nodes manually:"
echo "  Node 1: python3 src/gitconfig_node.py start --repo demo_data/node1 --http-port 8080"
echo "  Node 2: python3 src/gitconfig_node.py start --repo demo_data/node2 --http-port 8081 --remote demo_data/node1"
echo
echo "To use CLI:"
echo "  python3 src/gitconfig_cli.py set /test/key value --repo demo_data/node1"
echo "  python3 src/gitconfig_cli.py get /test/key --http http://localhost:8080"
