@echo off
REM Test runner script for GitProc (Windows)
REM Executes all tests with pytest and generates coverage report

echo =========================================
echo GitProc Test Suite
echo =========================================
echo.

REM Check if pytest is installed
python -c "import pytest" 2>nul
if errorlevel 1 (
    echo Error: pytest is not installed
    echo Please install it with: pip install pytest pytest-cov
    exit /b 1
)

REM Check if pytest-cov is installed
python -c "import pytest_cov" 2>nul
if errorlevel 1 (
    echo Warning: pytest-cov is not installed
    echo Coverage report will not be generated
    echo Install it with: pip install pytest-cov
    echo.
    set RUN_COVERAGE=false
) else (
    set RUN_COVERAGE=true
)

REM Set Python path to include current directory
set PYTHONPATH=%PYTHONPATH%;%CD%

echo Running tests...
echo.

REM Run tests with or without coverage
if "%RUN_COVERAGE%"=="true" (
    python -m pytest tests\ ^
        --verbose ^
        --tb=short ^
        --cov=gitproc ^
        --cov-report=term-missing ^
        --cov-report=html:htmlcov ^
        --cov-report=xml:coverage.xml ^
        %*
    
    echo.
    echo =========================================
    echo Coverage report generated:
    echo   - Terminal: (shown above^)
    echo   - HTML: htmlcov\index.html
    echo   - XML: coverage.xml
    echo =========================================
) else (
    python -m pytest tests\ ^
        --verbose ^
        --tb=short ^
        %*
)

echo.
echo =========================================
echo Test suite completed successfully!
echo =========================================
