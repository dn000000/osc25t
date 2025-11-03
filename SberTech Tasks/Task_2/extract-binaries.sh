#!/bin/bash
set -e

echo "Extracting binaries from Docker container..."

# Check if docker is available
if ! command -v docker &> /dev/null; then
    echo "Error: Docker is not installed."
    exit 1
fi

# Check if image exists
if ! docker image inspect uringkv:latest > /dev/null 2>&1; then
    echo "Error: Docker image 'uringkv:latest' not found. Please run 'docker-compose build' first."
    exit 1
fi

# Create target directory
mkdir -p ./target/release

# Create temporary container and copy binaries
echo "Creating temporary container..."
CONTAINER_ID=$(docker create uringkv:latest)

echo "Copying binaries..."
docker cp $CONTAINER_ID:/app/target/release/uringkv ./target/release/uringkv 2>/dev/null || {
    echo "Error: Failed to copy binary from container"
    docker rm $CONTAINER_ID > /dev/null
    exit 1
}

# Copy any additional binaries or libraries if they exist
docker cp $CONTAINER_ID:/app/target/release/liburingkv.so ./target/release/ 2>/dev/null || true
docker cp $CONTAINER_ID:/app/target/release/liburingkv.a ./target/release/ 2>/dev/null || true

# Cleanup
docker rm $CONTAINER_ID > /dev/null

# Make binary executable
chmod +x ./target/release/uringkv

echo "✓ Binaries extracted successfully!"
echo ""
echo "Binary location: ./target/release/uringkv"
ls -lh ./target/release/uringkv
echo ""
echo "To run: ./target/release/uringkv --help"
