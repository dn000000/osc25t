#!/bin/bash
set -e

echo "Testing uringKV benchmark..."

# Create test directory
TEST_DIR="/tmp/uringkv_bench_test"
rm -rf $TEST_DIR
mkdir -p $TEST_DIR

# Initialize storage
echo "1. Initializing storage..."
./uringkv init --path $TEST_DIR

# Run small benchmark
echo "2. Running small benchmark (100 keys, 5 seconds)..."
./uringkv bench --keys 100 --read-pct 70 --write-pct 30 --duration 5 --path $TEST_DIR

echo "✓ Benchmark test completed successfully!"

# Cleanup
rm -rf $TEST_DIR
