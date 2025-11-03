#!/bin/bash

echo "========================================"
echo "Running All Tests"
echo "========================================"
echo

echo "[1/2] Running unit tests..."
echo
python3 tests/test_gitconfig.py
if [ $? -ne 0 ]; then
    echo
    echo "Unit tests FAILED!"
    exit 1
fi

echo
echo "========================================"
echo
echo "[2/2] Running HTTP API tests..."
echo
python3 tests/test_http_api.py
if [ $? -ne 0 ]; then
    echo
    echo "HTTP API tests FAILED!"
    exit 1
fi

echo
echo "========================================"
echo "All Tests PASSED!"
echo "========================================"
