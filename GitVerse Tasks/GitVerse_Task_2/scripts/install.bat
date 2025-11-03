@echo off
echo Installing dependencies for GitConfig...
echo.
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo.
echo Installation complete!
echo.
echo To run demos:
echo   python full_demo.py
echo   python example_usage.py
echo.
echo To run tests:
echo   python test_gitconfig.py
echo   python test_http_api.py
echo.
echo To start a node:
echo   python gitconfig_node.py start --repo ./data/node1 --http-port 8080
