@echo off
echo ========================================
echo Running All Tests
echo ========================================
echo.

echo [1/2] Running unit tests...
echo.
python test_gitconfig.py
if errorlevel 1 (
    echo.
    echo Unit tests FAILED!
    pause
    exit /b 1
)

echo.
echo ========================================
echo.
echo [2/2] Running HTTP API tests...
echo.
python test_http_api.py
if errorlevel 1 (
    echo.
    echo HTTP API tests FAILED!
    pause
    exit /b 1
)

echo.
echo ========================================
echo All Tests PASSED!
echo ========================================
pause
