# Simple setup script for sysaudit project
# Installs all dependencies needed for development

$ErrorActionPreference = "Stop"

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "Sysaudit Setup Script" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "Found $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "Error: Python is not installed" -ForegroundColor Red
    Write-Host "Download from: https://www.python.org/downloads/" -ForegroundColor Yellow
    Write-Host "Make sure to check 'Add Python to PATH' during installation" -ForegroundColor Yellow
    exit 1
}

# Check pip
try {
    $pipVersion = pip --version 2>&1
    Write-Host "Found pip" -ForegroundColor Green
} catch {
    Write-Host "Error: pip is not installed" -ForegroundColor Red
    Write-Host "Install with: python -m ensurepip --upgrade" -ForegroundColor Yellow
    exit 1
}

Write-Host ""

# Install dependencies
Write-Host "Installing project dependencies..." -ForegroundColor Cyan
Write-Host ""

try {
    # Install package in editable mode with dev dependencies
    pip install -e .[dev]
    
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host "Setup Complete!" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Dependencies installed:" -ForegroundColor Cyan
    Write-Host "  - watchdog (file monitoring)"
    Write-Host "  - GitPython (git operations)"
    Write-Host "  - click (CLI framework)"
    Write-Host "  - PyYAML (config files)"
    Write-Host "  - requests (HTTP requests)"
    Write-Host "  - pytest (testing)"
    Write-Host "  - pytest-cov (coverage)"
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  - Run tests: python run_tests.py"
    Write-Host "  - Run all tests: pytest tests/"
    Write-Host "  - Check installation: sysaudit --version"
    Write-Host ""
} catch {
    Write-Host ""
    Write-Host "Error during installation: $_" -ForegroundColor Red
    Write-Host ""
    Write-Host "Try running as Administrator if you see permission errors" -ForegroundColor Yellow
    exit 1
}
