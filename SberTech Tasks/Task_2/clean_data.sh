#!/bin/bash
# Clean up corrupted data directory

echo "Cleaning up data directory..."
rm -rf ./data/wal/*
echo "WAL files removed"
echo "SST files kept for recovery"
echo "Done! You can now run the benchmark again."
