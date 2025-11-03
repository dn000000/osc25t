@echo off
REM Docker-based test runner for GitProc (Windows)
REM Runs all tests in a Linux container and displays results

setlocal enabledelayedexpansion

echo =========================================
echo GitProc Docker Test Pipeline
echo =========================================
echo.

REM Check if Docker is installed
docker --version >nul 2>&1
if errorlevel 1 (
    echo Error: Docker is not installed
    echo Please install Docker Desktop and try again
    echo Visit: https://docs.docker.com/desktop/install/windows-install/
    exit /b 1
)

REM Check if Docker daemon is running
docker info >nul 2>&1
if errorlevel 1 (
    echo Error: Docker daemon is not running
    echo Please start Docker Desktop and try again
    exit /b 1
)

echo Docker detected - OK
echo.

REM Parse command line arguments
set BUILD_FLAG=--build
set EXTRA_ARGS=

:parse_args
if "%~1"=="" goto end_parse
if /i "%~1"=="--no-build" (
    set BUILD_FLAG=
    shift
    goto parse_args
)
set EXTRA_ARGS=!EXTRA_ARGS! %~1
shift
goto parse_args
:end_parse

REM Build and run tests using docker-compose
echo Building test container...
echo.

if defined BUILD_FLAG (
    docker-compose -f docker-compose.test.yml build
    if errorlevel 1 (
        echo Error: Failed to build container
        exit /b 1
    )
    echo.
)

echo Running tests in container...
echo.

REM Run the tests
docker-compose -f docker-compose.test.yml run --rm test %EXTRA_ARGS%
set EXIT_CODE=%errorlevel%

echo.
if %EXIT_CODE% equ 0 (
    echo =========================================
    echo √ All tests passed successfully!
    echo =========================================
    echo.
    echo View detailed coverage report:
    echo   Open: htmlcov\index.html
) else (
    echo =========================================
    echo × Tests failed with exit code: %EXIT_CODE%
    echo =========================================
)

echo.
echo Cleaning up...
docker-compose -f docker-compose.test.yml down >nul 2>&1

exit /b %EXIT_CODE%
