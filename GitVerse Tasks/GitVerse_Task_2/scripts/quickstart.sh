#!/bin/bash

echo "========================================"
echo "GitConfig Quick Start"
echo "========================================"
echo

echo "Step 1: Installing dependencies..."
bash scripts/install.sh
if [ $? -ne 0 ]; then
    echo "Installation failed!"
    exit 1
fi

echo
echo "Step 2: Running full demonstration..."
python3 examples/full_demo.py
if [ $? -ne 0 ]; then
    echo "Demo failed!"
    exit 1
fi

echo
echo "========================================"
echo "Quick Start Complete!"
echo "========================================"
echo
echo "Next steps:"
echo
echo "1. Run tests:"
echo "   python3 tests/test_gitconfig.py"
echo "   python3 tests/test_http_api.py"
echo
echo "2. Start HTTP node:"
echo "   python3 src/gitconfig_node.py start --repo ./data/node1 --http-port 8080"
echo
echo "3. Use CLI:"
echo "   python3 src/gitconfig_cli.py set /test/key value --http http://localhost:8080"
echo "   python3 src/gitconfig_cli.py get /test/key --http http://localhost:8080"
echo
echo "4. Read documentation:"
echo "   docs/README.md - Overview"
echo "   docs/USAGE.md - Detailed usage guide"
echo "   docs/ARCHITECTURE.md - Architecture details"
echo "   docs/SCORING.md - Scoring breakdown"
echo
