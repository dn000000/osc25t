@echo off
echo ========================================
echo GitConfig Demo
echo ========================================
echo.

echo Cleaning up old data...
if exist demo_data rmdir /s /q demo_data
if exist example_data rmdir /s /q example_data
mkdir demo_data

echo.
echo === Creating bare repository (remote) ===
git init --bare demo_data\bare.git

echo.
echo === Running example scenarios ===
python example_usage.py

echo.
echo === Running tests ===
python test_gitconfig.py

echo.
echo Demo complete!
echo.
echo To start HTTP nodes manually:
echo   Node 1: python gitconfig_node.py start --repo demo_data\node1 --http-port 8080
echo   Node 2: python gitconfig_node.py start --repo demo_data\node2 --http-port 8081 --remote demo_data\node1
echo.
echo To use CLI:
echo   python gitconfig_cli.py set /test/key value --repo demo_data\node1
echo   python gitconfig_cli.py get /test/key --http http://localhost:8080
