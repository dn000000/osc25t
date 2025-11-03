#!/bin/bash
set -e

echo "Installing RPM Dependency Graph System..."
echo ""

# Check Python version
echo "Checking Python version..."
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    echo "Error: Python 3.8 or higher is required (found $PYTHON_VERSION)"
    exit 1
fi

echo "Python $PYTHON_VERSION detected ✓"
echo ""

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
echo "Virtual environment created ✓"
echo ""

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip --quiet

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt --quiet

if [ $? -eq 0 ]; then
    echo "Core dependencies installed ✓"
else
    echo "Error: Failed to install core dependencies"
    exit 1
fi

# Try to install RPM library (optional)
echo ""
echo "Checking for RPM library support..."
if command -v rpm &> /dev/null; then
    echo "RPM command found in system"
    echo "Attempting to install Python RPM bindings..."
    
    # Try to install rpm-py-installer
    pip install rpm-py-installer==1.1.0 --quiet 2>/dev/null
    
    if [ $? -eq 0 ]; then
        echo "RPM Python library installed ✓"
        echo "RPM parsing will use native library (faster)"
    else
        echo "Warning: RPM Python library installation failed"
        echo "This is normal if system RPM development packages are not installed"
        echo "The application will use manual RPM parsing (slower but functional)"
    fi
else
    echo "RPM command not found in system"
    echo "The application will use manual RPM parsing (slower but functional)"
fi
echo ""

# Create necessary directories
echo "Creating directory structure..."
mkdir -p data/cache
mkdir -p data/logs
mkdir -p static/css
mkdir -p static/js
mkdir -p templates
echo "Directory structure created ✓"
echo ""

echo "=========================================="
echo "✓ Installation complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "Option 1: Use the run script (recommended)"
echo "  ./run.sh <repository-url>"
echo ""
echo "Option 2: Manual execution"
echo "  1. Activate the virtual environment:"
echo "     source venv/bin/activate"
echo ""
echo "  2. Build dependency graphs:"
echo "     python -m src.main --repo-url <repository-url>"
echo ""
echo "  3. Start the web server:"
echo "     python -m src.server"
echo ""
echo "  4. Open your browser to:"
echo "     http://localhost:5000"
echo ""
echo "For more options, run:"
echo "  python -m src.main --help"
echo ""
