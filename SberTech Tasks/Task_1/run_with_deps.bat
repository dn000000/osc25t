@echo off
setlocal enabledelayedexpansion

echo ==========================================
echo RPM Dependency Graph System
echo WITH DEPENDENCY EXTRACTION
echo ==========================================
echo.
echo WARNING: This will download all RPM files from the repository
echo This process may take a long time depending on:
echo   - Number of packages
echo   - Size of RPM files
echo   - Network speed
echo.

REM Check for repository URL argument
if "%~1"=="" (
    echo Error: Repository URL is required
    echo.
    echo Usage: run_with_deps.bat ^<repository-url^> [--max-packages N]
    echo.
    echo Example:
    echo   run_with_deps.bat https://example.com/openscaler/repo
    echo   run_with_deps.bat https://example.com/openscaler/repo --max-packages 100
    echo.
    exit /b 1
)

set REPO_URL=%~1
shift

REM Collect remaining arguments
set EXTRA_ARGS=
:parse_args
if not "%~1"=="" (
    set EXTRA_ARGS=!EXTRA_ARGS! %~1
    shift
    goto parse_args
)

REM Check if virtual environment exists
if not exist "venv\Scripts\activate.bat" (
    echo Error: Virtual environment not found
    echo Please run install.bat first
    echo.
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat
if %ERRORLEVEL% NEQ 0 (
    echo Error: Failed to activate virtual environment
    exit /b 1
)
echo Virtual environment activated [OK]
echo.

REM Run main script with --extract-deps flag
echo Building dependency graphs from: %REPO_URL%
echo.
echo Mode: Full dependency extraction
echo   - Downloads RPM files from repository
echo   - Extracts dependencies from RPM headers
echo   - Builds complete dependency graphs
echo.
echo This will take a while...
echo.

python -m src.main --repo-url "%REPO_URL%" --extract-deps %EXTRA_ARGS%

REM Check if graphs were created successfully
if %ERRORLEVEL% EQU 0 (
    echo.
    echo ==========================================
    echo Graphs built successfully!
    echo ==========================================
    echo.
    echo Starting web server...
    echo.
    echo Web server starting on http://localhost:5000
    echo.
    echo Press Ctrl+C to stop the server
    echo.
    
    python -m src.server
) else (
    echo.
    echo ==========================================
    echo Error: Failed to build graphs
    echo ==========================================
    echo.
    echo Please check the error messages above and try again.
    echo.
    exit /b 1
)

endlocal
