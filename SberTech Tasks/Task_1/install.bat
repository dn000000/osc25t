@echo off
setlocal enabledelayedexpansion

echo Installing RPM Dependency Graph System...
echo.

REM Check Python version
echo Checking Python version...
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo Error: Python is not installed or not in PATH
    exit /b 1
)

for /f "tokens=2" %%i in ('python --version 2^>^&1') do set PYTHON_VERSION=%%i
echo Python %PYTHON_VERSION% detected

REM Extract major and minor version
for /f "tokens=1,2 delims=." %%a in ("%PYTHON_VERSION%") do (
    set PYTHON_MAJOR=%%a
    set PYTHON_MINOR=%%b
)

if %PYTHON_MAJOR% LSS 3 (
    echo Error: Python 3.8 or higher is required ^(found %PYTHON_VERSION%^)
    exit /b 1
)

if %PYTHON_MAJOR% EQU 3 if %PYTHON_MINOR% LSS 8 (
    echo Error: Python 3.8 or higher is required ^(found %PYTHON_VERSION%^)
    exit /b 1
)

echo Python version check passed [OK]
echo.

REM Create virtual environment
echo Creating virtual environment...
python -m venv venv
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to create virtual environment
    exit /b 1
)
echo Virtual environment created [OK]
echo.

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to activate virtual environment
    exit /b 1
)

REM Upgrade pip
echo Upgrading pip...
python -m pip install --upgrade pip --quiet
if %ERRORLEVEL% NEQ 0 (
    echo Warning: Failed to upgrade pip, continuing anyway...
)

REM Install dependencies
echo Installing dependencies...
pip install -r requirements.txt --quiet
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to install dependencies
    exit /b 1
)
echo Dependencies installed [OK]
echo.

REM Create necessary directories
echo Creating directory structure...
if not exist "data\cache" mkdir data\cache
if not exist "data\logs" mkdir data\logs
if not exist "static\css" mkdir static\css
if not exist "static\js" mkdir static\js
if not exist "templates" mkdir templates
echo Directory structure created [OK]
echo.

echo ==========================================
echo Installation complete!
echo ==========================================
echo.
echo Next steps:
echo.
echo Option 1: Use the run script ^(recommended^)
echo   run.bat ^<repository-url^>
echo.
echo Option 2: Manual execution
echo   1. Activate the virtual environment:
echo      venv\Scripts\activate.bat
echo.
echo   2. Build dependency graphs:
echo      python -m src.main --repo-url ^<repository-url^>
echo.
echo   3. Start the web server:
echo      python -m src.server
echo.
echo   4. Open your browser to:
echo      http://localhost:5000
echo.
echo For more options, run:
echo   python -m src.main --help
echo.

endlocal
