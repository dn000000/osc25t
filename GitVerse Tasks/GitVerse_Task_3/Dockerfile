# Dockerfile for running GitProc daemon
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y git procps && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application
COPY gitproc/ ./gitproc/

# Create necessary directories
RUN mkdir -p /etc/gitproc/services /var/log/gitproc /var/lib/gitproc

# Set Python path
ENV PYTHONPATH=/app

# Default command
CMD ["/bin/bash"]
