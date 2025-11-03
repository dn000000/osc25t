FROM rust:1.83-slim

# Install dependencies
RUN apt-get update && apt-get install -y \
    liburing-dev \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy project files
COPY . .

# Build release binary
RUN cargo build --release

# Run tests (note: io_uring tests may require privileged mode or --cap-add=SYS_ADMIN)
# Tests are run separately via docker-compose with proper capabilities
RUN cargo test --release --lib || echo "Some tests may require privileged mode"

# Default command
CMD ["./target/release/uringkv"]
