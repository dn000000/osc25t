#!/usr/bin/env bash
set -euo pipefail
IMAGE="secmem-agent"

# Build Docker image
docker build -t "$IMAGE" .

# Run tests inside container
docker run --rm "$IMAGE"