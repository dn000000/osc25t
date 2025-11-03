@echo off
REM Test runner script for RPM Dependency Graph project (Windows)
REM Runs all tests and generates coverage reports

setlocal enabledelayedexpansion

REM Check if virtual environment is activated
if "%VIRTUAL_ENV%"=="" (
    echo Warning: Virtual environment not activated
    echo Attempting to activate venv...
    
    if exist "venv\Scripts\activate.bat" (
        call venv\Scripts\activate.bat
        echo Virtual environment activated
    ) else (
        echo Error: Virtual environment not found
        echo Please run: python -m venv venv
        echo Then run: venv\Scripts\activate.bat
        exit /b 1
    )
) else (
    echo Virtual environment is active: %VIRTUAL_ENV%
)

REM Parse command line arguments
set TEST_TYPE=%1
if "%TEST_TYPE%"=="" set TEST_TYPE=all

echo.
echo ==========================================
echo RPM Dependency Graph - Test Runner
echo ==========================================
echo.

REM Check if pytest is installed
python -c "import pytest" 2>nul
if errorlevel 1 (
    echo Error: pytest not installed
    echo Installing test dependencies...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo Failed to install dependencies
        exit /b 1
    )
)

REM Check if pytest-cov is installed
python -c "import pytest_cov" 2>nul
if errorlevel 1 (
    echo Warning: pytest-cov not installed
    echo Installing pytest-cov...
    pip install pytest-cov
)

REM Run tests based on argument
if "%TEST_TYPE%"=="unit" (
    echo.
    echo ==========================================
    echo Running Unit Tests
    echo ==========================================
    echo.
    pytest tests\unit\ -v --tb=short
    if errorlevel 1 (
        echo Unit tests failed
        exit /b 1
    )
    echo Unit tests passed
    exit /b 0
)

if "%TEST_TYPE%"=="integration" (
    echo.
    echo ==========================================
    echo Running Integration Tests
    echo ==========================================
    echo.
    pytest tests\integration\ -v --tb=short
    if errorlevel 1 (
        echo Integration tests failed
        exit /b 1
    )
    echo Integration tests passed
    exit /b 0
)

if "%TEST_TYPE%"=="coverage" (
    echo.
    echo ==========================================
    echo Running All Tests with Coverage
    echo ==========================================
    echo.
    pytest tests\ -v --cov=src --cov-report=html --cov-report=term-missing --cov-report=xml
    if errorlevel 1 (
        echo Some tests failed
        exit /b 1
    )
    
    echo.
    echo ==========================================
    echo Coverage Report Generated
    echo ==========================================
    echo.
    echo HTML coverage report: htmlcov\index.html
    echo XML coverage report: coverage.xml
    
    exit /b 0
)

if "%TEST_TYPE%"=="all" (
    echo.
    echo ==========================================
    echo Running Unit Tests
    echo ==========================================
    echo.
    pytest tests\unit\ -v --tb=short
    set UNIT_RESULT=!errorlevel!
    
    echo.
    echo ==========================================
    echo Running Integration Tests
    echo ==========================================
    echo.
    pytest tests\integration\ -v --tb=short
    set INTEGRATION_RESULT=!errorlevel!
    
    echo.
    echo ==========================================
    echo Running All Tests with Coverage
    echo ==========================================
    echo.
    pytest tests\ -v --cov=src --cov-report=html --cov-report=term-missing --cov-report=xml
    set COVERAGE_RESULT=!errorlevel!
    
    echo.
    echo ==========================================
    echo Test Summary
    echo ==========================================
    echo.
    
    if !UNIT_RESULT! equ 0 (
        echo [PASS] Unit Tests
    ) else (
        echo [FAIL] Unit Tests
    )
    
    if !INTEGRATION_RESULT! equ 0 (
        echo [PASS] Integration Tests
    ) else (
        echo [FAIL] Integration Tests
    )
    
    if !COVERAGE_RESULT! equ 0 (
        echo [PASS] Coverage Tests
    ) else (
        echo [FAIL] Coverage Tests
    )
    
    echo.
    
    if !UNIT_RESULT! equ 0 if !INTEGRATION_RESULT! equ 0 if !COVERAGE_RESULT! equ 0 (
        echo All tests passed!
        echo HTML coverage report: htmlcov\index.html
        exit /b 0
    ) else (
        echo Some tests failed. Please review the output above.
        exit /b 1
    )
)

REM Unknown option
echo Unknown option: %TEST_TYPE%
echo.
echo Usage: %0 [unit^|integration^|coverage^|all]
echo.
echo Options:
echo   unit         - Run only unit tests
echo   integration  - Run only integration tests
echo   coverage     - Run all tests with coverage report
echo   all          - Run all test suites (default)
exit /b 1
