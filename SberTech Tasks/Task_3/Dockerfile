FROM rust:1.75

WORKDIR /app
COPY . .

ENV RUST_LOG=info

# Build project
RUN cargo build --release

# Run tests by default
CMD ["cargo", "test", "--", "--nocapture"]