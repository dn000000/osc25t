#!/bin/bash
# Simple test script for compaction functionality

echo "Testing compaction implementation..."
echo ""

# Run compaction tests
echo "Running compaction module tests..."
cargo test --lib compaction::tests --no-fail-fast

echo ""
echo "Running engine tests (which use compaction)..."
cargo test --lib engine::tests --no-fail-fast

echo ""
echo "Test run complete!"
