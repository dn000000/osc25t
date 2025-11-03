# Usage Examples and Common Workflows

This document provides practical examples and common workflows for using the Git-based System Audit & Compliance Monitor.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Basic Monitoring Workflows](#basic-monitoring-workflows)
3. [Drift Detection Scenarios](#drift-detection-scenarios)
4. [Compliance Checking](#compliance-checking)
5. [Rollback Operations](#rollback-operations)
6. [Advanced Workflows](#advanced-workflows)
7. [Troubleshooting](#troubleshooting)

## Quick Start

### Initial Setup

```bash
# Install the system
sudo ./install.sh

# Create configuration directory
sudo mkdir -p /etc/sysaudit

# Copy example configuration
sudo cp examples/config-minimal.yaml /etc/sysaudit/config.yaml
sudo cp examples/blacklist.txt /etc/sysaudit/blacklist.txt

# Initialize the audit repository
sudo sysaudit init --repo /var/lib/sysaudit --baseline main

# Start monitoring
sudo sysaudit monitor --config /etc/sysaudit/config.yaml
```

### First Snapshot

```bash
# Create a manual snapshot of current system state
sudo sysaudit snapshot --message "Initial system baseline"
```

## Basic Monitoring Workflows

### Scenario 1: Monitor Critical System Directories

Monitor `/etc`, `/usr/local/bin`, and `/root/.ssh` for any changes:

```bash
# Start monitoring with specific paths
sudo sysaudit monitor \
  --watch /etc \
  --watch /usr/local/bin \
  --watch /root/.ssh \
  --repo /var/lib/sysaudit
```

**What happens:**
- All file changes in these directories are detected within 1 second
- Changes are automatically committed to Git with metadata
- Process information is captured when possible
- Events are batched (5 seconds or 10 events)

### Scenario 2: Monitor with Custom Filters

Monitor `/var/www` but ignore log files and temporary files:

```bash
# Create custom blacklist
cat > /tmp/web-blacklist.txt << EOF
*.log
*.log.*
*.tmp
*.cache
__pycache__/*
*.pyc
.git/*
EOF

# Start monitoring with custom blacklist
sudo sysaudit monitor \
  --watch /var/www \
  --repo /var/lib/sysaudit \
  --blacklist /tmp/web-blacklist.txt
```

### Scenario 3: Run as Systemd Service

For continuous monitoring that survives reboots:

```bash
# Copy service file
sudo cp sysaudit.service /etc/systemd/system/

# Edit service to set your paths
sudo nano /etc/systemd/system/sysaudit.service

# Enable and start service
sudo systemctl daemon-reload
sudo systemctl enable sysaudit
sudo systemctl start sysaudit

# Check status
sudo systemctl status sysaudit

# View logs
sudo journalctl -u sysaudit -f
```

## Drift Detection Scenarios

### Scenario 1: Daily Configuration Audit

Check for any changes from the baseline each morning:

```bash
# Check drift from main baseline
sudo sysaudit drift-check --baseline main

# Example output:
# Drift Report - Baseline: main
# ================================
# 
# HIGH Severity Changes:
#   [MODIFIED] /etc/sudoers
#   [ADDED] /etc/ssh/sshd_config.d/custom.conf
# 
# MEDIUM Severity Changes:
#   [MODIFIED] /etc/nginx/nginx.conf
#   [DELETED] /usr/local/bin/old-script.sh
# 
# Total: 4 changes (2 HIGH, 2 MEDIUM, 0 LOW)
```

### Scenario 2: Filter by Severity

Only show critical changes:

```bash
# Show only HIGH severity changes
sudo sysaudit drift-check --baseline main --severity HIGH

# Show HIGH and MEDIUM severity changes
sudo sysaudit drift-check --baseline main --severity MEDIUM
```

### Scenario 3: Compare with Specific Point in Time

Compare current state with a specific commit:

```bash
# List recent commits
cd /var/lib/sysaudit
git log --oneline -10

# Check drift from specific commit
sudo sysaudit drift-check --baseline abc123def

# Or use a tag
git tag -a "pre-update" -m "Before system update"
sudo sysaudit drift-check --baseline pre-update
```

### Scenario 4: Automated Daily Drift Reports

Create a cron job for daily drift detection:

```bash
# Create script
sudo tee /usr/local/bin/daily-drift-check.sh << 'EOF'
#!/bin/bash
REPORT_FILE="/var/log/sysaudit/drift-$(date +%Y%m%d).txt"
mkdir -p /var/log/sysaudit

sysaudit drift-check --baseline main > "$REPORT_FILE"

# Send email if HIGH severity changes found
if grep -q "HIGH Severity Changes:" "$REPORT_FILE"; then
    mail -s "ALERT: High severity system changes detected" admin@example.com < "$REPORT_FILE"
fi
EOF

sudo chmod +x /usr/local/bin/daily-drift-check.sh

# Add to crontab (run at 6 AM daily)
sudo crontab -e
# Add line:
# 0 6 * * * /usr/local/bin/daily-drift-check.sh
```

## Compliance Checking

### Scenario 1: Weekly Security Audit

Run comprehensive compliance checks weekly:

```bash
# Generate text report to console
sudo sysaudit compliance-report --format text

# Save JSON report for processing
sudo sysaudit compliance-report \
  --format json \
  --output /var/log/sysaudit/compliance-$(date +%Y%m%d).json

# Generate HTML report for viewing
sudo sysaudit compliance-report \
  --format html \
  --output /var/www/html/reports/compliance.html
```

### Scenario 2: Post-Installation Security Check

After installing new software, verify no security issues were introduced:

```bash
# Create snapshot before installation
sudo sysaudit snapshot --message "Before installing package X"

# Install software
sudo apt install some-package

# Run compliance check
sudo sysaudit compliance-report --format text

# Check what changed
sudo sysaudit drift-check --baseline main
```

### Scenario 3: Automated Compliance Monitoring

Enable automatic compliance checking in config:

```yaml
# /etc/sysaudit/config.yaml
compliance:
  auto_check: true
  rules:
    - world-writable
    - suid-sgid
    - weak-permissions

alerts:
  enabled: true
  webhook_url: https://alerts.example.com/webhook
```

```bash
# Restart monitoring with auto-compliance
sudo systemctl restart sysaudit

# Now compliance checks run automatically on file changes
# Alerts are sent for HIGH severity issues
```

### Scenario 4: Custom Compliance Rules

Check specific directories for security issues:

```python
# custom_compliance_check.py
from sysaudit.compliance.checker import ComplianceChecker
from sysaudit.config import Config

config = Config(
    repo_path="/var/lib/sysaudit",
    watch_paths=["/opt/custom-app", "/var/lib/custom-app"]
)

checker = ComplianceChecker(config)

# Scan specific paths
issues = checker.scan_directory("/opt/custom-app")

# Filter HIGH severity
high_issues = [i for i in issues if i.severity == "HIGH"]

if high_issues:
    print(f"ALERT: {len(high_issues)} high severity issues found!")
    for issue in high_issues:
        print(f"  - {issue.path}: {issue.description}")
```

## Rollback Operations

### Scenario 1: Undo Accidental Configuration Change

Someone accidentally modified `/etc/ssh/sshd_config`:

```bash
# Check what changed
sudo sysaudit drift-check --baseline main

# View commit history for the file
cd /var/lib/sysaudit
git log --oneline -- etc/ssh/sshd_config

# Preview rollback (dry-run)
sudo sysaudit rollback \
  --to-commit abc123 \
  --path /etc/ssh/sshd_config \
  --dry-run

# Perform rollback
sudo sysaudit rollback \
  --to-commit abc123 \
  --path /etc/ssh/sshd_config

# Backup is automatically created at:
# /etc/ssh/sshd_config.backup.1234567890

# Restart service
sudo systemctl restart sshd
```

### Scenario 2: Rollback Multiple Files After Failed Update

System update broke configuration:

```bash
# Find commit before update
cd /var/lib/sysaudit
git log --oneline --since="2 hours ago"

# Identify the "before update" commit
BEFORE_UPDATE="abc123"

# Check what changed
sudo sysaudit drift-check --baseline $BEFORE_UPDATE

# Rollback each affected file
sudo sysaudit rollback --to-commit $BEFORE_UPDATE --path /etc/nginx/nginx.conf
sudo sysaudit rollback --to-commit $BEFORE_UPDATE --path /etc/php/php.ini

# Or use git directly for bulk rollback
cd /var/lib/sysaudit
sudo git checkout $BEFORE_UPDATE -- etc/nginx/ etc/php/

# Copy files back to system
sudo rsync -av etc/nginx/ /etc/nginx/
sudo rsync -av etc/php/ /etc/php/
```

### Scenario 3: Investigate and Rollback Suspicious Changes

Suspicious file modification detected:

```bash
# Check recent changes
sudo sysaudit drift-check --baseline main --severity HIGH

# Investigate specific file
cd /var/lib/sysaudit
git log -p -- etc/sudoers

# View commit details including process info
git show abc123

# If unauthorized, rollback
sudo sysaudit rollback \
  --to-commit <previous-good-commit> \
  --path /etc/sudoers

# Create incident report
sudo sysaudit compliance-report --format json --output /tmp/incident-report.json
```

## Advanced Workflows

### Scenario 1: Multi-Environment Baseline Management

Maintain separate baselines for dev, staging, and production:

```bash
# Initialize with environment-specific baseline
sudo sysaudit init --repo /var/lib/sysaudit --baseline production

# Create environment snapshots
sudo sysaudit snapshot --message "Production baseline - 2024-01-15"
cd /var/lib/sysaudit
git tag -a "prod-2024-01-15" -m "Production baseline"

# Later, compare with baseline
sudo sysaudit drift-check --baseline prod-2024-01-15
```

### Scenario 2: GPG-Signed Commits for Audit Trail

Enable cryptographic verification of all changes:

```bash
# Setup GPG key
gpg --gen-key
gpg --list-keys

# Configure git
git config --global user.signingkey YOUR_KEY_ID
git config --global commit.gpgsign true

# Enable in sysaudit config
cat >> /etc/sysaudit/config.yaml << EOF
repository:
  gpg_sign: true
EOF

# All commits are now GPG signed
sudo systemctl restart sysaudit

# Verify signatures
cd /var/lib/sysaudit
git log --show-signature
```

### Scenario 3: Integration with SIEM

Send alerts to SIEM system via webhook:

```yaml
# /etc/sysaudit/config.yaml
alerts:
  enabled: true
  webhook_url: https://siem.example.com/api/events
```

Webhook payload format:
```json
{
  "severity": "HIGH",
  "rule": "world-writable",
  "path": "/etc/sensitive-file",
  "description": "File is world-writable (mode: 0o666)",
  "timestamp": "2024-01-15T10:30:00Z",
  "recommendation": "Remove write permission for others: chmod o-w"
}
```

### Scenario 4: Monitoring Docker Container Configurations

Monitor Docker-related configurations:

```bash
# Monitor Docker configs
sudo sysaudit monitor \
  --watch /etc/docker \
  --watch /var/lib/docker/volumes \
  --watch /etc/systemd/system/docker.service.d \
  --repo /var/lib/sysaudit-docker
```

### Scenario 5: Pre/Post Change Validation

Validate system state before and after maintenance:

```bash
#!/bin/bash
# maintenance-wrapper.sh

# Pre-change snapshot
echo "Creating pre-change snapshot..."
sudo sysaudit snapshot --message "Before maintenance: $1"

# Run maintenance
echo "Running maintenance..."
"$@"

# Post-change compliance check
echo "Running post-change compliance check..."
sudo sysaudit compliance-report --format text

# Check drift
echo "Checking drift..."
sudo sysaudit drift-check --baseline main

# Create post-change snapshot
sudo sysaudit snapshot --message "After maintenance: $1"
```

Usage:
```bash
./maintenance-wrapper.sh "Update nginx config" sudo nano /etc/nginx/nginx.conf
```

## Troubleshooting

### Issue: Too Many Events Being Generated

**Problem:** System is creating too many commits for temporary files.

**Solution:** Adjust blacklist patterns:

```bash
# Add more patterns to blacklist
cat >> /etc/sysaudit/blacklist.txt << EOF
*.cache
*.pid
*.sock
/var/run/*
/var/lock/*
EOF

# Restart monitoring
sudo systemctl restart sysaudit
```

### Issue: Missing Process Information

**Problem:** Commits don't show which process made changes.

**Solution:** Process tracking requires root privileges and may not work for all file systems:

```bash
# Ensure running as root
sudo sysaudit monitor ...

# Check if /proc is accessible
ls -la /proc/self

# Some filesystems (NFS, FUSE) may not support process tracking
```

### Issue: Git Repository Growing Too Large

**Problem:** Audit repository consuming too much disk space.

**Solution:** Implement retention policy:

```bash
# Archive old commits
cd /var/lib/sysaudit
git tag -a "archive-2023" -m "Archive point for 2023"

# Create shallow clone for active monitoring
cd /var/lib
git clone --depth 100 sysaudit sysaudit-active
mv sysaudit sysaudit-archive
mv sysaudit-active sysaudit

# Or use git gc to compress
cd /var/lib/sysaudit
git gc --aggressive --prune=now
```

### Issue: Service Not Starting

**Problem:** Systemd service fails to start.

**Solution:** Check logs and permissions:

```bash
# Check service status
sudo systemctl status sysaudit

# View detailed logs
sudo journalctl -u sysaudit -n 50

# Check config file syntax
python3 -c "import yaml; yaml.safe_load(open('/etc/sysaudit/config.yaml'))"

# Verify repository exists
ls -la /var/lib/sysaudit

# Check permissions
sudo chown -R root:root /var/lib/sysaudit
sudo chmod 755 /var/lib/sysaudit
```

### Issue: Webhook Alerts Not Sending

**Problem:** Alerts not reaching webhook endpoint.

**Solution:** Test webhook connectivity:

```bash
# Test webhook manually
curl -X POST https://your-webhook-url.com/endpoint \
  -H "Content-Type: application/json" \
  -d '{"test": "message"}'

# Check sysaudit logs for webhook errors
sudo journalctl -u sysaudit | grep -i webhook

# Verify webhook URL in config
grep webhook_url /etc/sysaudit/config.yaml

# Test with Python
python3 << EOF
from sysaudit.alert.manager import AlertManager
from sysaudit.models import ComplianceIssue
from sysaudit.config import Config
from datetime import datetime

config = Config(
    repo_path="/var/lib/sysaudit",
    watch_paths=["/etc"],
    webhook_url="https://your-webhook-url.com/endpoint"
)

manager = AlertManager(config)
issue = ComplianceIssue(
    severity="HIGH",
    rule="test",
    path="/test",
    description="Test alert",
    recommendation="None",
    timestamp=datetime.now()
)

manager.send_alert(issue)
print("Alert sent!")
EOF
```

### Issue: Compliance Checks Taking Too Long

**Problem:** Compliance reports are slow on large directories.

**Solution:** Optimize scanning:

```bash
# Scan specific directories instead of entire filesystem
sudo sysaudit compliance-report --paths /etc /usr/local/bin

# Or use programmatic API with filters
python3 << EOF
from sysaudit.compliance.checker import ComplianceChecker
from sysaudit.config import Config

config = Config(
    repo_path="/var/lib/sysaudit",
    watch_paths=["/etc"]  # Only scan /etc
)

checker = ComplianceChecker(config)
issues = checker.scan_directory("/etc", max_depth=3)  # Limit depth
print(f"Found {len(issues)} issues")
EOF
```

## Best Practices

1. **Regular Baselines**: Create tagged baselines before major changes
2. **Test Rollbacks**: Always use `--dry-run` first
3. **Monitor Logs**: Regularly check `journalctl -u sysaudit`
4. **Backup Repository**: Backup `/var/lib/sysaudit` regularly
5. **Review Filters**: Periodically review blacklist to avoid noise
6. **Compliance Schedule**: Run compliance checks on a regular schedule
7. **Alert Tuning**: Adjust severity thresholds to avoid alert fatigue
8. **Documentation**: Document your baseline and any manual changes

## Additional Resources

- [CLI Reference](CLI_REFERENCE.md) - Complete command-line interface documentation
- [Configuration Guide](CONFIGURATION.md) - Detailed configuration options
- [Systemd Service](SYSTEMD_SERVICE.md) - Service setup and management
- [Examples Directory](../examples/) - Code examples and sample configs
