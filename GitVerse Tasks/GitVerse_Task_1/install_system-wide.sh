#!/bin/bash

# Git-based System Audit & Compliance Monitor - Installation Script
# This script checks dependencies and installs the sysaudit package

set -e

echo "=========================================="
echo "System Audit Installation Script"
echo "=========================================="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored messages
print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}!${NC} $1"
}

print_info() {
    echo -e "  $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    print_warning "This script should be run as root for system-wide installation"
    print_info "Run with: sudo ./install.sh"
    echo ""
fi

# Check for required system utilities
echo "Checking system dependencies..."
echo ""

# Check for git
if command -v git &> /dev/null; then
    GIT_VERSION=$(git --version | awk '{print $3}')
    print_success "git found (version $GIT_VERSION)"
else
    print_error "git is not installed"
    print_info "Install with: sudo apt-get install git (Debian/Ubuntu)"
    print_info "            or: sudo yum install git (RHEL/CentOS)"
    exit 1
fi

# Check for python3
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version | awk '{print $2}')
    print_success "python3 found (version $PYTHON_VERSION)"
    
    # Check Python version is >= 3.8
    PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
    PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
    
    if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
        print_error "Python 3.8 or higher is required (found $PYTHON_VERSION)"
        exit 1
    fi
else
    print_error "python3 is not installed"
    print_info "Install with: sudo apt-get install python3 python3-pip (Debian/Ubuntu)"
    print_info "            or: sudo yum install python3 python3-pip (RHEL/CentOS)"
    exit 1
fi

# Check for pip3
if command -v pip3 &> /dev/null; then
    print_success "pip3 found"
else
    print_error "pip3 is not installed"
    print_info "Install with: sudo apt-get install python3-pip (Debian/Ubuntu)"
    print_info "            or: sudo yum install python3-pip (RHEL/CentOS)"
    exit 1
fi

echo ""
echo "All system dependencies satisfied!"
echo ""

# Install Python package and dependencies
echo "Installing sysaudit package and dependencies..."
echo ""

if pip3 install -e . ; then
    print_success "Package installed successfully"
else
    print_error "Package installation failed"
    exit 1
fi

echo ""

# Create configuration directories
echo "Setting up configuration directories..."
echo ""

CONFIG_DIR="/etc/sysaudit"
DATA_DIR="/var/lib/sysaudit"

if [ "$EUID" -eq 0 ]; then
    # Running as root, create system directories
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$DATA_DIR"
    print_success "Created $CONFIG_DIR"
    print_success "Created $DATA_DIR"
else
    # Not root, create user directories
    CONFIG_DIR="$HOME/.config/sysaudit"
    DATA_DIR="$HOME/.local/share/sysaudit"
    mkdir -p "$CONFIG_DIR"
    mkdir -p "$DATA_DIR"
    print_success "Created $CONFIG_DIR"
    print_success "Created $DATA_DIR"
fi

echo ""

# Copy example configuration files
echo "Creating example configuration files..."
echo ""

# Create example config.yaml
cat > "$CONFIG_DIR/config.yaml.example" << 'EOF'
# System Audit Configuration File

repository:
  path: /var/lib/sysaudit/repo
  baseline: main
  gpg_sign: false

monitoring:
  paths:
    - /etc
    - /usr/local/bin
  blacklist_file: /etc/sysaudit/blacklist.txt
  whitelist_file: null
  batch_interval: 5  # seconds
  batch_size: 10

compliance:
  auto_check: true
  rules:
    - world-writable
    - suid-sgid
    - weak-permissions

alerts:
  enabled: true
  webhook_url: null
  journal_priority: CRIT
EOF

print_success "Created $CONFIG_DIR/config.yaml.example"

# Create example blacklist.txt
cat > "$CONFIG_DIR/blacklist.txt" << 'EOF'
# Blacklist patterns for file monitoring
# One pattern per line, supports glob patterns

# Temporary files
*.tmp
*.swp
*~
*.bak

# Log files
*.log
*.log.*

# Python cache
*.pyc
__pycache__/*
*.pyo

# Editor files
.*.sw?
*~
.DS_Store

# Git directory
.git/*

# System temporary directories
/tmp/*
/var/tmp/*
/var/log/*

# Package manager cache
/var/cache/*
EOF

print_success "Created $CONFIG_DIR/blacklist.txt"

echo ""

# Verify CLI command is available
echo "Verifying installation..."
echo ""

if command -v sysaudit &> /dev/null; then
    print_success "sysaudit command is available"
    echo ""
    print_info "Run 'sysaudit --help' to see available commands"
else
    print_warning "sysaudit command not found in PATH"
    print_info "You may need to add ~/.local/bin to your PATH"
    print_info "Add this to your ~/.bashrc or ~/.profile:"
    print_info "  export PATH=\"\$HOME/.local/bin:\$PATH\""
fi

echo ""

# Install systemd service (only if running as root)
if [ "$EUID" -eq 0 ]; then
    echo "Installing systemd service..."
    echo ""
    
    if [ -f "sysaudit.service" ]; then
        cp sysaudit.service /etc/systemd/system/
        chmod 644 /etc/systemd/system/sysaudit.service
        systemctl daemon-reload
        print_success "Systemd service installed"
        print_info "Enable with: systemctl enable sysaudit"
        print_info "Start with: systemctl start sysaudit"
    else
        print_warning "sysaudit.service file not found, skipping systemd installation"
        print_info "Copy manually: sudo cp sysaudit.service /etc/systemd/system/"
    fi
    echo ""
fi

echo "=========================================="
echo "Installation Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Copy example config: cp $CONFIG_DIR/config.yaml.example $CONFIG_DIR/config.yaml"
echo "  2. Edit configuration: nano $CONFIG_DIR/config.yaml"
echo "  3. Initialize repository: sysaudit init --repo $DATA_DIR/repo"
echo "  4. Start monitoring: sysaudit monitor --config $CONFIG_DIR/config.yaml"
echo ""

if [ "$EUID" -eq 0 ]; then
    echo "Systemd service:"
    echo "  - Enable: systemctl enable sysaudit"
    echo "  - Start: systemctl start sysaudit"
    echo "  - Status: systemctl status sysaudit"
    echo "  - Logs: journalctl -u sysaudit -f"
    echo ""
    echo "See docs/SYSTEMD_SERVICE.md for detailed systemd documentation."
else
    echo "For systemd service installation, run this script with sudo."
fi
echo ""
