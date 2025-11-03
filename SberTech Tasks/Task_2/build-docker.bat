@echo off
echo Building uringKV in Docker and extracting binaries...
echo.

REM Check if Docker is available
docker --version >nul 2>&1
if errorlevel 1 (
    echo Error: Docker is not installed or not in PATH
    exit /b 1
)

REM Build the Docker image
echo [1/4] Building Docker image...
docker build -t uringkv:latest -f Dockerfile .
if errorlevel 1 (
    echo Error: Docker build failed
    exit /b 1
)

REM Create build directory
echo [2/4] Creating build directory...
if not exist "build" mkdir build

REM Extract binaries from Docker container
echo [3/4] Extracting binaries from Docker container...

REM Create temporary container
for /f "tokens=*" %%i in ('docker create uringkv:latest') do set CONTAINER_ID=%%i
echo Container ID: %CONTAINER_ID%

REM Copy binary from container
docker cp %CONTAINER_ID%:/app/target/release/uringkv build/uringkv
if errorlevel 1 (
    echo Error: Failed to copy binary from container
    docker rm %CONTAINER_ID% >nul 2>&1
    exit /b 1
)

REM Copy additional files if they exist
docker cp %CONTAINER_ID%:/app/target/release/liburingkv.so build/ >nul 2>&1
docker cp %CONTAINER_ID%:/app/target/release/liburingkv.a build/ >nul 2>&1

REM Cleanup container
docker rm %CONTAINER_ID% >nul

echo [4/4] Running tests in Docker with privileged mode...
docker run --rm --privileged uringkv:latest cargo test --release -- --test-threads=1
if errorlevel 1 (
    echo Warning: Some tests failed
)

echo.
echo ========================================
echo Build complete!
echo Binary location: build\uringkv
echo ========================================
echo.
dir build\uringkv
echo.
echo To run in WSL: wsl ./build/uringkv --help
