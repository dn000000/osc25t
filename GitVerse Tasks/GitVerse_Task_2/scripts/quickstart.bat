@echo off
echo ========================================
echo GitConfig Quick Start
echo ========================================
echo.

echo Step 1: Installing dependencies...
call install.bat
if errorlevel 1 (
    echo Installation failed!
    pause
    exit /b 1
)

echo.
echo Step 2: Running full demonstration...
python full_demo.py
if errorlevel 1 (
    echo Demo failed!
    pause
    exit /b 1
)

echo.
echo ========================================
echo Quick Start Complete!
echo ========================================
echo.
echo Next steps:
echo.
echo 1. Run tests:
echo    python test_gitconfig.py
echo    python test_http_api.py
echo.
echo 2. Start HTTP node:
echo    python gitconfig_node.py start --repo ./data/node1 --http-port 8080
echo.
echo 3. Use CLI:
echo    python gitconfig_cli.py set /test/key value --http http://localhost:8080
echo    python gitconfig_cli.py get /test/key --http http://localhost:8080
echo.
echo 4. Read documentation:
echo    README.md - Overview
echo    USAGE.md - Detailed usage guide
echo    ARCHITECTURE.md - Architecture details
echo    SCORING.md - Scoring breakdown
echo.
pause
