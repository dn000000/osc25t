# Configuration Guide

This document provides comprehensive documentation for all configuration options in the Git-based System Audit & Compliance Monitor.

## Table of Contents

1. [Configuration File Format](#configuration-file-format)
2. [Repository Configuration](#repository-configuration)
3. [Monitoring Configuration](#monitoring-configuration)
4. [Compliance Configuration](#compliance-configuration)
5. [Alert Configuration](#alert-configuration)
6. [CLI Argument Overrides](#cli-argument-overrides)
7. [Environment Variables](#environment-variables)
8. [Configuration Examples](#configuration-examples)
9. [Configuration Validation](#configuration-validation)

## Configuration File Format

The system uses YAML format for configuration files. The default location is `/etc/sysaudit/config.yaml`, but you can specify a custom path using the `--config` CLI argument.

### Basic Structure

```yaml
repository:
  # Repository settings
  
monitoring:
  # Monitoring settings
  
compliance:
  # Compliance checking settings
  
alerts:
  # Alert and notification settings
```

### Configuration File Locations

The system searches for configuration files in the following order:

1. Path specified with `--config` CLI argument
2. `/etc/sysaudit/config.yaml` (system-wide)
3. `~/.config/sysaudit/config.yaml` (user-specific)
4. `./config.yaml` (current directory)

## Repository Configuration

Controls Git repository settings for storing audit history.

### `repository.path`

**Type:** String (required)  
**Default:** None  
**Description:** Path to the Git repository where audit history is stored.

```yaml
repository:
  path: /var/lib/sysaudit
```

**Notes:**
- Must be an absolute path
- Directory will be created if it doesn't exist
- Requires write permissions
- Should be on a filesystem with sufficient space for audit history

**Examples:**
```yaml
# Standard system location
repository:
  path: /var/lib/sysaudit

# Custom location
repository:
  path: /opt/audit/repo

# User-specific location
repository:
  path: /home/admin/.sysaudit/repo
```

### `repository.baseline`

**Type:** String  
**Default:** `main`  
**Description:** Name of the baseline branch used for drift detection comparisons.

```yaml
repository:
  baseline: main
```

**Notes:**
- Branch is created during `init` command
- Used as reference point for `drift-check` command
- Can be changed to compare against different baselines
- Supports Git branch names, tags, or commit hashes

**Examples:**
```yaml
# Use main branch
repository:
  baseline: main

# Use production baseline
repository:
  baseline: production

# Use specific tag
repository:
  baseline: v1.0-baseline

# Use specific commit (not recommended for config file)
repository:
  baseline: abc123def456
```

### `repository.gpg_sign`

**Type:** Boolean  
**Default:** `false`  
**Description:** Enable GPG signing of all commits for cryptographic verification.

```yaml
repository:
  gpg_sign: true
```

**Notes:**
- Requires GPG key configured in Git
- Provides cryptographic proof of commit authenticity
- Useful for compliance and audit requirements
- Slightly slower commit operations

**Prerequisites:**
```bash
# Generate GPG key
gpg --gen-key

# Configure Git
git config --global user.signingkey YOUR_KEY_ID
git config --global commit.gpgsign true
```

**Examples:**
```yaml
# Enable GPG signing
repository:
  gpg_sign: true

# Disable GPG signing (default)
repository:
  gpg_sign: false
```

## Monitoring Configuration

Controls file system monitoring behavior.

### `monitoring.paths`

**Type:** List of Strings (required)  
**Default:** `[]`  
**Description:** List of directories to monitor for file changes.

```yaml
monitoring:
  paths:
    - /etc
    - /usr/local/bin
    - /root/.ssh
```

**Notes:**
- Each path is monitored recursively
- Must be absolute paths
- Paths must exist and be readable
- Can be overridden with `--watch` CLI argument
- Empty list means no monitoring (useful for manual snapshots only)

**Examples:**
```yaml
# Monitor critical system directories
monitoring:
  paths:
    - /etc
    - /usr/local/bin
    - /usr/local/sbin
    - /root/.ssh

# Monitor web application
monitoring:
  paths:
    - /var/www/html
    - /etc/nginx
    - /etc/php

# Monitor Docker configurations
monitoring:
  paths:
    - /etc/docker
    - /var/lib/docker/volumes
    - /etc/systemd/system/docker.service.d

# Single directory
monitoring:
  paths:
    - /opt/myapp
```

### `monitoring.blacklist_file`

**Type:** String  
**Default:** `null`  
**Description:** Path to file containing glob patterns for files to ignore.

```yaml
monitoring:
  blacklist_file: /etc/sysaudit/blacklist.txt
```

**Notes:**
- One pattern per line
- Supports glob patterns (`*`, `?`, `[]`)
- Lines starting with `#` are comments
- Empty lines are ignored
- Default patterns are always applied (*.tmp, *.swp, etc.)

**Blacklist File Format:**
```text
# Temporary files
*.tmp
*.swp
*~
*.bak

# Log files
*.log
*.log.*

# Python cache
__pycache__/*
*.pyc
*.pyo

# Git directories
.git/*

# System directories
/proc/*
/sys/*
/dev/*
```

**Examples:**
```yaml
# Standard location
monitoring:
  blacklist_file: /etc/sysaudit/blacklist.txt

# Custom location
monitoring:
  blacklist_file: /opt/myapp/audit-ignore.txt

# No blacklist (only default patterns)
monitoring:
  blacklist_file: null
```

### `monitoring.whitelist_file`

**Type:** String  
**Default:** `null`  
**Description:** Path to file containing glob patterns for files to include exclusively.

```yaml
monitoring:
  whitelist_file: /etc/sysaudit/whitelist.txt
```

**Notes:**
- When specified, ONLY files matching whitelist are monitored
- Blacklist is still applied to whitelisted files
- One pattern per line
- Supports glob patterns
- Useful for monitoring specific file types only

**Whitelist File Format:**
```text
# Only monitor configuration files
*.conf
*.config
*.yaml
*.yml
*.json

# Only monitor shell scripts
*.sh
*.bash
```

**Examples:**
```yaml
# Monitor only config files
monitoring:
  whitelist_file: /etc/sysaudit/whitelist.txt

# No whitelist (monitor all files)
monitoring:
  whitelist_file: null
```

### `monitoring.batch_interval`

**Type:** Integer (seconds)  
**Default:** `5`  
**Description:** Maximum time to wait before creating a commit for batched events.

```yaml
monitoring:
  batch_interval: 5
```

**Notes:**
- Events are batched to reduce commit frequency
- Commit is created when interval expires OR batch_size is reached
- Lower values = more frequent commits, more granular history
- Higher values = fewer commits, less granular history
- Minimum recommended: 1 second
- Maximum recommended: 60 seconds

**Examples:**
```yaml
# Quick commits (1 second)
monitoring:
  batch_interval: 1

# Standard batching (5 seconds)
monitoring:
  batch_interval: 5

# Longer batching (30 seconds)
monitoring:
  batch_interval: 30
```

### `monitoring.batch_size`

**Type:** Integer  
**Default:** `10`  
**Description:** Maximum number of events to batch before creating a commit.

```yaml
monitoring:
  batch_size: 10
```

**Notes:**
- Commit is created when batch_size is reached OR batch_interval expires
- Lower values = more commits, more granular history
- Higher values = fewer commits, less granular history
- Minimum recommended: 1
- Maximum recommended: 100

**Examples:**
```yaml
# Small batches
monitoring:
  batch_size: 5

# Standard batches
monitoring:
  batch_size: 10

# Large batches
monitoring:
  batch_size: 50
```

## Compliance Configuration

Controls security compliance checking behavior.

### `compliance.auto_check`

**Type:** Boolean  
**Default:** `false`  
**Description:** Automatically run compliance checks on file changes.

```yaml
compliance:
  auto_check: true
```

**Notes:**
- When enabled, compliance checks run automatically after each commit
- Alerts are sent for HIGH severity issues
- May impact performance on high-change systems
- Recommended for security-critical systems

**Examples:**
```yaml
# Enable automatic compliance checking
compliance:
  auto_check: true

# Disable automatic checking (manual only)
compliance:
  auto_check: false
```

### `compliance.rules`

**Type:** List of Strings  
**Default:** All available rules  
**Description:** List of compliance rules to enable.

```yaml
compliance:
  rules:
    - world-writable
    - suid-sgid
    - weak-permissions
```

**Available Rules:**

| Rule Name | Description | Severity |
|-----------|-------------|----------|
| `world-writable` | Detects files writable by all users in critical directories | HIGH |
| `suid-sgid` | Finds unexpected SUID/SGID binaries | HIGH |
| `weak-permissions` | Checks SSH keys, password files for proper permissions | HIGH/MEDIUM |

**Notes:**
- If not specified, all rules are enabled
- Rules can be selectively disabled by omitting them
- Custom rules can be added by extending the ComplianceRule class

**Examples:**
```yaml
# All rules (default)
compliance:
  rules:
    - world-writable
    - suid-sgid
    - weak-permissions

# Only check for world-writable files
compliance:
  rules:
    - world-writable

# Only SUID/SGID checks
compliance:
  rules:
    - suid-sgid
```

### `compliance.scan_depth`

**Type:** Integer  
**Default:** `null` (unlimited)  
**Description:** Maximum directory depth for compliance scanning.

```yaml
compliance:
  scan_depth: 5
```

**Notes:**
- Limits how deep into directory trees compliance scans go
- Useful for performance on large filesystems
- `null` or `0` means unlimited depth
- Depth is relative to each monitored path

**Examples:**
```yaml
# Unlimited depth (default)
compliance:
  scan_depth: null

# Limit to 3 levels deep
compliance:
  scan_depth: 3

# Only scan top level
compliance:
  scan_depth: 1
```

## Alert Configuration

Controls alert and notification behavior.

### `alerts.enabled`

**Type:** Boolean  
**Default:** `true`  
**Description:** Enable or disable the alert system.

```yaml
alerts:
  enabled: true
```

**Notes:**
- When disabled, no alerts are sent (logging still occurs)
- Useful for testing or low-priority monitoring

**Examples:**
```yaml
# Enable alerts
alerts:
  enabled: true

# Disable alerts
alerts:
  enabled: false
```

### `alerts.webhook_url`

**Type:** String  
**Default:** `null`  
**Description:** HTTP endpoint for sending alert notifications via webhook.

```yaml
alerts:
  webhook_url: https://alerts.example.com/webhook
```

**Notes:**
- Alerts are sent as HTTP POST with JSON payload
- Timeout is 5 seconds
- Failures don't block monitoring
- Supports HTTPS with certificate validation

**Webhook Payload Format:**
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

**Examples:**
```yaml
# Slack webhook
alerts:
  webhook_url: https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Custom webhook
alerts:
  webhook_url: https://siem.example.com/api/events

# Microsoft Teams webhook
alerts:
  webhook_url: https://outlook.office.com/webhook/YOUR/WEBHOOK/URL

# No webhook
alerts:
  webhook_url: null
```

### `alerts.journal_priority`

**Type:** String  
**Default:** `CRIT`  
**Description:** Syslog/journald priority level for HIGH severity alerts.

```yaml
alerts:
  journal_priority: CRIT
```

**Valid Values:**
- `EMERG` - System is unusable
- `ALERT` - Action must be taken immediately
- `CRIT` - Critical conditions
- `ERR` - Error conditions
- `WARNING` - Warning conditions
- `NOTICE` - Normal but significant condition
- `INFO` - Informational messages
- `DEBUG` - Debug-level messages

**Notes:**
- Only affects HIGH severity alerts
- MEDIUM alerts use WARNING priority
- LOW alerts use NOTICE priority

**Examples:**
```yaml
# Critical priority (default)
alerts:
  journal_priority: CRIT

# Alert priority
alerts:
  journal_priority: ALERT

# Warning priority
alerts:
  journal_priority: WARNING
```

### `alerts.min_severity`

**Type:** String  
**Default:** `HIGH`  
**Description:** Minimum severity level for sending alerts.

```yaml
alerts:
  min_severity: MEDIUM
```

**Valid Values:**
- `HIGH` - Only HIGH severity alerts
- `MEDIUM` - MEDIUM and HIGH severity alerts
- `LOW` - All alerts (HIGH, MEDIUM, LOW)

**Notes:**
- Filters which alerts are sent
- Lower severity issues are still logged
- Useful for reducing alert fatigue

**Examples:**
```yaml
# Only critical alerts
alerts:
  min_severity: HIGH

# Medium and high alerts
alerts:
  min_severity: MEDIUM

# All alerts
alerts:
  min_severity: LOW
```

## CLI Argument Overrides

CLI arguments take precedence over configuration file settings.

### Common Overrides

```bash
# Override repository path
sysaudit monitor --repo /custom/repo/path

# Override watch paths
sysaudit monitor --watch /etc --watch /usr/local/bin

# Override config file location
sysaudit monitor --config /custom/config.yaml

# Override baseline
sysaudit drift-check --baseline production

# Override blacklist
sysaudit monitor --blacklist /custom/blacklist.txt
```

### Priority Order

1. CLI arguments (highest priority)
2. Configuration file
3. Default values (lowest priority)

## Environment Variables

The system supports the following environment variables:

### `SYSAUDIT_CONFIG`

**Description:** Default configuration file path  
**Default:** `/etc/sysaudit/config.yaml`

```bash
export SYSAUDIT_CONFIG=/opt/sysaudit/config.yaml
sysaudit monitor
```

### `SYSAUDIT_REPO`

**Description:** Default repository path  
**Default:** None (must be specified)

```bash
export SYSAUDIT_REPO=/var/lib/sysaudit
sysaudit monitor --watch /etc
```

### `SYSAUDIT_LOG_LEVEL`

**Description:** Logging verbosity  
**Default:** `INFO`  
**Valid Values:** `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL`

```bash
export SYSAUDIT_LOG_LEVEL=DEBUG
sysaudit monitor
```

## Configuration Examples

### Minimal Configuration

Bare minimum for basic monitoring:

```yaml
repository:
  path: /var/lib/sysaudit

monitoring:
  paths:
    - /etc
```

### Standard Configuration

Recommended for most deployments:

```yaml
repository:
  path: /var/lib/sysaudit
  baseline: main
  gpg_sign: false

monitoring:
  paths:
    - /etc
    - /usr/local/bin
    - /root/.ssh
  blacklist_file: /etc/sysaudit/blacklist.txt
  batch_interval: 5
  batch_size: 10

compliance:
  auto_check: false
  rules:
    - world-writable
    - suid-sgid
    - weak-permissions

alerts:
  enabled: true
  webhook_url: null
  min_severity: HIGH
```

### High-Security Configuration

For security-critical systems:

```yaml
repository:
  path: /var/lib/sysaudit
  baseline: production
  gpg_sign: true  # Cryptographic verification

monitoring:
  paths:
    - /etc
    - /usr/local/bin
    - /usr/local/sbin
    - /root/.ssh
    - /var/www
  blacklist_file: /etc/sysaudit/blacklist.txt
  batch_interval: 1  # Quick commits
  batch_size: 5

compliance:
  auto_check: true  # Automatic security checks
  rules:
    - world-writable
    - suid-sgid
    - weak-permissions

alerts:
  enabled: true
  webhook_url: https://siem.example.com/api/events
  journal_priority: ALERT
  min_severity: MEDIUM  # Alert on medium and high
```

### Development/Testing Configuration

For development environments:

```yaml
repository:
  path: /tmp/sysaudit-dev
  baseline: dev
  gpg_sign: false

monitoring:
  paths:
    - /opt/myapp
  blacklist_file: /tmp/blacklist.txt
  batch_interval: 10
  batch_size: 20

compliance:
  auto_check: false
  rules:
    - world-writable

alerts:
  enabled: false  # No alerts in dev
```

### Multi-Environment Configuration

Using environment-specific configs:

```yaml
# /etc/sysaudit/config-production.yaml
repository:
  path: /var/lib/sysaudit-prod
  baseline: production
  gpg_sign: true

monitoring:
  paths:
    - /etc
    - /usr/local/bin
  batch_interval: 5
  batch_size: 10

compliance:
  auto_check: true

alerts:
  enabled: true
  webhook_url: https://alerts.example.com/prod
  min_severity: HIGH
```

```yaml
# /etc/sysaudit/config-staging.yaml
repository:
  path: /var/lib/sysaudit-staging
  baseline: staging
  gpg_sign: false

monitoring:
  paths:
    - /etc
    - /usr/local/bin
  batch_interval: 10
  batch_size: 20

compliance:
  auto_check: false

alerts:
  enabled: true
  webhook_url: https://alerts.example.com/staging
  min_severity: MEDIUM
```

Usage:
```bash
# Production
sudo sysaudit monitor --config /etc/sysaudit/config-production.yaml

# Staging
sudo sysaudit monitor --config /etc/sysaudit/config-staging.yaml
```

## Configuration Validation

### Validate Configuration File

```bash
# Check YAML syntax
python3 -c "import yaml; yaml.safe_load(open('/etc/sysaudit/config.yaml'))"

# Validate with sysaudit
sysaudit validate-config --config /etc/sysaudit/config.yaml
```

### Common Configuration Errors

#### Invalid YAML Syntax

```yaml
# WRONG - missing space after colon
repository:
  path:/var/lib/sysaudit

# CORRECT
repository:
  path: /var/lib/sysaudit
```

#### Invalid Path

```yaml
# WRONG - relative path
monitoring:
  paths:
    - etc/config

# CORRECT - absolute path
monitoring:
  paths:
    - /etc/config
```

#### Invalid Type

```yaml
# WRONG - string instead of boolean
compliance:
  auto_check: "true"

# CORRECT
compliance:
  auto_check: true
```

#### Missing Required Fields

```yaml
# WRONG - missing repository.path
repository:
  baseline: main

# CORRECT
repository:
  path: /var/lib/sysaudit
  baseline: main
```

### Configuration Testing

Test configuration before deploying:

```bash
# Dry-run with new config
sysaudit monitor --config /tmp/new-config.yaml --dry-run

# Test for 60 seconds then stop
timeout 60 sysaudit monitor --config /tmp/new-config.yaml

# Check logs for errors
journalctl -u sysaudit -n 100
```

## Best Practices

1. **Version Control**: Keep configuration files in version control
2. **Comments**: Document why specific settings are chosen
3. **Environment-Specific**: Use separate configs for dev/staging/prod
4. **Validation**: Always validate before deploying
5. **Backup**: Backup configuration files regularly
6. **Security**: Restrict config file permissions (600 or 640)
7. **Documentation**: Document custom settings and deviations from defaults
8. **Testing**: Test configuration changes in non-production first

## Additional Resources

- [Usage Examples](USAGE_EXAMPLES.md) - Common workflows and scenarios
- [CLI Reference](CLI_REFERENCE.md) - Command-line interface documentation
- [Systemd Service](SYSTEMD_SERVICE.md) - Service configuration
- [Examples Directory](../examples/) - Sample configuration files
