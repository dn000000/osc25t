#!/bin/bash
set -e

echo "Building uringKV..."

# Check if we should use Docker
USE_DOCKER=${USE_DOCKER:-false}

if [ "$USE_DOCKER" = "true" ]; then
    echo "Building in Docker..."
    
    # Check if docker is available
    if ! command -v docker &> /dev/null; then
        echo "Error: Docker is not installed. Please install Docker or set USE_DOCKER=false"
        exit 1
    fi
    
    # Build the Docker image
    echo "Building Docker image..."
    docker build -t uringkv:latest -f Dockerfile .
    
    # Extract binaries from Docker container
    echo "Extracting binaries from Docker container..."
    mkdir -p ./target/release
    
    # Create temporary container and copy binaries
    CONTAINER_ID=$(docker create uringkv:latest)
    docker cp $CONTAINER_ID:/app/target/release/uringkv ./target/release/uringkv 2>/dev/null || echo "Main binary not found"
    docker cp $CONTAINER_ID:/app/target/release/uringkv.exe ./target/release/uringkv.exe 2>/dev/null || true
    docker rm $CONTAINER_ID > /dev/null
    
    # Make binary executable
    chmod +x ./target/release/uringkv 2>/dev/null || true
    
    echo "✓ Binaries extracted to ./target/release/"
    ls -lh ./target/release/uringkv 2>/dev/null || echo "Warning: Binary extraction may have failed"
    
    # Run tests in Docker with proper capabilities
    echo "Running tests in Docker with privileged mode..."
    docker run --rm \
        --privileged \
        -v "$(pwd)/data:/app/data" \
        uringkv:latest \
        cargo test --release -- --test-threads=1
    
    echo "Docker build and test complete!"
    echo "Binary available at: ./target/release/uringkv"
    
else
    echo "Building locally..."
    
    # Install Rust if not present
    if ! command -v cargo &> /dev/null; then
        echo "Installing Rust..."
        curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
        source $HOME/.cargo/env
    fi
    
    # Install liburing
    echo "Installing liburing-dev..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y liburing-dev
    elif command -v yum &> /dev/null; then
        sudo yum install -y liburing-devel
    else
        echo "Warning: Could not detect package manager. Please install liburing-dev manually."
    fi
    
    # Build project
    echo "Building release binary..."
    cargo build --release
    
    # Run tests
    echo "Running tests..."
    cargo test --release
    
    echo "Build complete! Binary at: target/release/uringkv"
fi
