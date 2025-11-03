# Build and Deployment Guide

## Overview

This document describes the build and deployment scripts for uringKV, including Docker-based testing with proper io_uring support.

## Build Scripts

### Linux Build Script (`build.sh`)

The `build.sh` script supports both local and Docker-based builds:

**Local Build:**
```bash
./build.sh
```

**Docker Build:**
```bash
USE_DOCKER=true ./build.sh
```

Features:
- Automatically installs Rust toolchain if not present
- Installs liburing-dev dependency
- Builds release binary
- Runs tests
- Supports both apt-get and yum package managers

### Windows Build Script (`build.bat`)

For Windows users, the build script uses WSL to execute the Linux build script:

```batch
build.bat
```

This automatically invokes WSL and runs `build.sh`.

## Docker Support

### Dockerfile

The main Dockerfile builds the uringKV binary:

```bash
docker build -t uringkv:latest .
```

Features:
- Based on `rust:1.83-slim`
- Installs liburing-dev and build-essential
- Builds release binary
- Runs library tests (note: some io_uring tests require privileged mode)

### Dockerfile.test

A specialized Dockerfile for running tests:

```bash
docker build -f Dockerfile.test -t uringkv-test .
```

### docker-compose.yml

The docker-compose configuration provides two services:

1. **uringkv**: Main application service
2. **test**: Test runner with privileged mode for io_uring

**Build all services:**
```bash
docker-compose build
```

**Run tests with proper io_uring support:**
```bash
docker-compose run --rm test
```

The test service runs in privileged mode to allow io_uring operations, which require special kernel capabilities.

## io_uring Permissions

io_uring operations require special permissions. There are two approaches:

### Option 1: Privileged Mode (Simpler, used in docker-compose)
```yaml
privileged: true
```

### Option 2: Specific Capabilities (More Secure)
```yaml
cap_add:
  - SYS_ADMIN
  - IPC_LOCK
```

The docker-compose.yml uses privileged mode for simplicity in testing environments.

## Test Results

### Current Status (After Fixes)
- **95 tests passed** ✅
- **20 tests failing** (down from 41)

### Fixed Issues
1. ✅ **io_uring permissions** - Tests now run in privileged Docker mode
2. ✅ **SST file format** - Fixed min/max key storage offset calculation
3. ✅ **Compilation errors** - Added serde_json::Error support to StorageError

### Remaining Issues
- WAL recovery tests (10 failures) - Checksum verification issues with multiple entries
- Engine crash recovery tests (7 failures) - Related to WAL recovery
- Compaction tests (2 failures) - Empty entry handling
- SST tests (1 failure) - Capacity overflow in some edge cases

To run tests with proper permissions:
```bash
docker-compose run --rm test
```

Or use the Windows batch script:
```batch
test-docker.bat
```

## Directory Structure

```
.
├── build.sh              # Linux build script
├── build.bat             # Windows build script (uses WSL)
├── Dockerfile            # Main application Docker image
├── Dockerfile.test       # Test runner Docker image
├── docker-compose.yml    # Docker Compose configuration
└── src/                  # Source code
```

## Requirements Met

This implementation satisfies all requirements from task 13:

- ✅ 13.1: Created build.sh for Linux with Rust installation, liburing-dev, and Docker support
- ✅ 13.2: Created build.bat for Windows using WSL
- ✅ 13.3: Created Dockerfile with rust:1.83-slim, liburing-dev, build and test steps
- ✅ 13.4: Created docker-compose.yml with test service and proper io_uring capabilities

## Known Issues and Solutions

### Issue: io_uring "Operation not permitted" errors

**Cause:** io_uring requires special kernel capabilities

**Solution:** Run tests in privileged Docker container:
```bash
docker-compose run --rm test
```

### Issue: Permission denied on target directory in WSL

**Cause:** Windows filesystem permissions in WSL

**Solution:** Use Docker build instead:
```bash
USE_DOCKER=true ./build.sh
```

## Next Steps

To continue development:

1. Run tests: `docker-compose run --rm test`
2. Build binary: `docker-compose build uringkv`
3. Run application: `docker-compose up uringkv`

For production deployment, consider using the specific capabilities approach instead of privileged mode for better security.
