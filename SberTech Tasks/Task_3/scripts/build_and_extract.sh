#!/usr/bin/env bash
set -euo pipefail

IMAGE="secmem-agent"
BUILD_DIR="build"

echo "Building Docker image..."
docker build -t "$IMAGE" .

echo "Creating build directory..."
mkdir -p "$BUILD_DIR"

echo "Creating temporary container..."
docker create --name secmem-temp "$IMAGE"

echo "Extracting binaries from container..."
docker cp secmem-temp:/app/target/release/secmem-agent "$BUILD_DIR/secmem-agent"
docker cp secmem-temp:/app/target/release/secmemctl "$BUILD_DIR/secmemctl"

echo "Cleaning up temporary container..."
docker rm secmem-temp

echo ""
echo "Build complete! Binaries extracted to $BUILD_DIR/"
echo "- $BUILD_DIR/secmem-agent"
echo "- $BUILD_DIR/secmemctl"
echo ""
echo "Making binaries executable..."
chmod +x "$BUILD_DIR/secmem-agent"
chmod +x "$BUILD_DIR/secmemctl"

echo "Done!"
