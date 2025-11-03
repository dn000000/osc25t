@echo off
REM Installation script for GitProc on Windows systems

echo ==========================================
echo GitProc Installation Script
echo ==========================================
echo.

REM Check Python version
echo Checking Python version...
python --version >nul 2>&1
if errorlevel 1 (
    echo Error: Python is not installed or not in PATH.
    echo Please install Python 3.8 or higher and try again.
    exit /b 1
)

REM Get Python version
for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i

echo Python %PYTHON_VERSION% detected
echo.

REM Check if version is 3.8 or higher (simplified check)
python -c "import sys; exit(0 if sys.version_info >= (3, 8) else 1)"
if errorlevel 1 (
    echo Error: Python 3.8 or higher is required.
    echo Current version: %PYTHON_VERSION%
    exit /b 1
)

echo Python version check - OK
echo.

REM Install dependencies
echo Installing Python dependencies...
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Error: Failed to install dependencies.
    exit /b 1
)

echo.
echo Dependencies installed successfully!
echo.

echo ==========================================
echo Installation completed successfully!
echo ==========================================
echo.
echo NOTE: Windows support is limited. Some features may not work:
echo   - PID namespace isolation (Linux-only)
echo   - cgroups resource limits (Linux-only)
echo.
echo To get started:
echo   1. Initialize a repository: python -m gitproc.cli init --repo C:\path\to\services
echo   2. Start the daemon: python -m gitproc.cli daemon
echo.
echo For more information, see docs\README.md

pause
