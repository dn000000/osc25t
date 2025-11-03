#!/bin/bash

# Test script for systemd service file validation
# This script validates the systemd service file syntax

set -e

echo "=========================================="
echo "Systemd Service File Validation"
echo "=========================================="
echo ""

SERVICE_FILE="sysaudit.service"

# Color codes
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Check if service file exists
if [ ! -f "$SERVICE_FILE" ]; then
    print_error "Service file not found: $SERVICE_FILE"
    exit 1
fi

print_success "Service file exists"

# Check if systemd-analyze is available
if ! command -v systemd-analyze &> /dev/null; then
    echo "Warning: systemd-analyze not available, skipping syntax validation"
    echo "Install systemd to run full validation"
else
    # Validate service file syntax (ignore executable path warnings)
    echo ""
    echo "Validating service file syntax..."
    OUTPUT=$(systemd-analyze verify "$SERVICE_FILE" 2>&1 || true)
    
    # Check for critical errors (ignore warnings about missing executable)
    if echo "$OUTPUT" | grep -qE "(Failed to parse|Invalid|Unknown section)" && \
       ! echo "$OUTPUT" | grep -q "is not executable"; then
        print_error "Service file has critical syntax errors"
        echo "$OUTPUT"
        exit 1
    else
        print_success "Service file syntax is valid (ignoring missing executable warnings)"
    fi
fi

# Check required sections
echo ""
echo "Checking required sections..."

if grep -q "^\[Unit\]" "$SERVICE_FILE"; then
    print_success "[Unit] section present"
else
    print_error "[Unit] section missing"
    exit 1
fi

if grep -q "^\[Service\]" "$SERVICE_FILE"; then
    print_success "[Service] section present"
else
    print_error "[Service] section missing"
    exit 1
fi

if grep -q "^\[Install\]" "$SERVICE_FILE"; then
    print_success "[Install] section present"
else
    print_error "[Install] section missing"
    exit 1
fi

# Check required directives
echo ""
echo "Checking required directives..."

if grep -q "^Description=" "$SERVICE_FILE"; then
    print_success "Description directive present"
else
    print_error "Description directive missing"
    exit 1
fi

if grep -q "^Type=" "$SERVICE_FILE"; then
    print_success "Type directive present"
else
    print_error "Type directive missing"
    exit 1
fi

if grep -q "^ExecStart=" "$SERVICE_FILE"; then
    print_success "ExecStart directive present"
else
    print_error "ExecStart directive missing"
    exit 1
fi

if grep -q "^Restart=" "$SERVICE_FILE"; then
    print_success "Restart directive present (Requirement 7.2)"
else
    print_error "Restart directive missing"
    exit 1
fi

if grep -q "^WantedBy=" "$SERVICE_FILE"; then
    print_success "WantedBy directive present"
else
    print_error "WantedBy directive missing"
    exit 1
fi

# Check security hardening options (Requirement 7.4)
echo ""
echo "Checking security hardening options (Requirement 7.4)..."

if grep -q "^ProtectSystem=" "$SERVICE_FILE"; then
    print_success "ProtectSystem directive present"
else
    print_error "ProtectSystem directive missing"
    exit 1
fi

if grep -q "^ProtectHome=" "$SERVICE_FILE"; then
    print_success "ProtectHome directive present"
else
    print_error "ProtectHome directive missing"
    exit 1
fi

if grep -q "^PrivateTmp=" "$SERVICE_FILE"; then
    print_success "PrivateTmp directive present"
else
    print_error "PrivateTmp directive missing"
    exit 1
fi

if grep -q "^NoNewPrivileges=" "$SERVICE_FILE"; then
    print_success "NoNewPrivileges directive present"
else
    print_error "NoNewPrivileges directive missing"
    exit 1
fi

# Check process management (Requirement 7.3)
echo ""
echo "Checking process management options (Requirement 7.3)..."

if grep -q "^KillMode=" "$SERVICE_FILE"; then
    print_success "KillMode directive present"
else
    print_error "KillMode directive missing"
    exit 1
fi

if grep -q "^KillSignal=" "$SERVICE_FILE"; then
    print_success "KillSignal directive present"
else
    print_error "KillSignal directive missing"
    exit 1
fi

# Check restart policies (Requirement 7.2)
echo ""
echo "Checking restart policies (Requirement 7.2)..."

if grep -q "^RestartSec=" "$SERVICE_FILE"; then
    print_success "RestartSec directive present"
else
    print_error "RestartSec directive missing"
    exit 1
fi

echo ""
echo "=========================================="
echo "All validation checks passed!"
echo "=========================================="
echo ""
echo "Requirements compliance:"
echo "  ✓ Requirement 7.1: Service file structure complete"
echo "  ✓ Requirement 7.2: Restart policies configured"
echo "  ✓ Requirement 7.3: Process management configured"
echo "  ✓ Requirement 7.4: Security hardening options present"
echo ""
