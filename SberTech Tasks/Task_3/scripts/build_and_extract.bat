@echo off
setlocal enabledelayedexpansion
set IMAGE=secmem-agent
set BUILD_DIR=build

echo Building Docker image...
docker build -t %IMAGE% . || exit /b 1

echo Creating build directory...
if not exist %BUILD_DIR% mkdir %BUILD_DIR%

echo Creating temporary container...
docker create --name secmem-temp %IMAGE% || exit /b 1

echo Extracting binaries from container...
docker cp secmem-temp:/app/target/release/secmem-agent %BUILD_DIR%/secmem-agent || goto :cleanup
docker cp secmem-temp:/app/target/release/secmemctl %BUILD_DIR%/secmemctl || goto :cleanup

echo Cleaning up temporary container...
docker rm secmem-temp

echo.
echo Build complete! Binaries extracted to %BUILD_DIR%/
echo - %BUILD_DIR%/secmem-agent
echo - %BUILD_DIR%/secmemctl
echo.
echo Note: These are Linux binaries and require WSL or Linux to run.
exit /b 0

:cleanup
echo Cleaning up temporary container...
docker rm secmem-temp
exit /b 1
