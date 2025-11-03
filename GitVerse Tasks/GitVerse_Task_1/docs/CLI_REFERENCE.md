# SysAudit CLI Reference

## Overview

The `sysaudit` command-line interface provides comprehensive tools for monitoring file system changes, tracking them in Git, and performing compliance checks.

## Installation

```bash
pip install -e .
```

After installation, the `sysaudit` command will be available system-wide.

## Global Options

```
--version, -V       Show version and exit
--verbose, -v       Enable verbose output
--help             Show help message
```

Environment variables:
- `SYSAUDIT_VERBOSE`: Enable verbose mode (1, true, yes)

## Commands

### init

Initialize the audit system with a Git repository and configuration.

```bash
sysaudit init --repo PATH [OPTIONS]
```

**Options:**
- `--repo PATH` (required): Path to audit repository
- `--baseline TEXT`: Baseline branch name (default: main)
- `--config-dir PATH`: Configuration directory (default: /etc/sysaudit)

**Example:**
```bash
sudo sysaudit init --repo /var/lib/sysaudit --baseline main
```

### monitor

Start monitoring file system changes in real-time.

```bash
sysaudit monitor [OPTIONS]
```

**Options:**
- `--watch PATH`: Paths to monitor (can be specified multiple times)
- `--daemon`: Run as daemon in background
- `--config PATH`: Path to configuration file
- `--repo PATH`: Path to audit repository (overrides config)

**Examples:**
```bash
# Using config file
sudo sysaudit monitor --config /etc/sysaudit/config.yaml

# Using CLI arguments
sudo sysaudit monitor --watch /etc --watch /usr/local/bin --repo /var/lib/sysaudit

# Daemon mode
sudo sysaudit monitor --daemon --config /etc/sysaudit/config.yaml
```

### snapshot

Create a manual snapshot of the current state.

```bash
sysaudit snapshot -m MESSAGE [OPTIONS]
```

**Options:**
- `-m, --message TEXT` (required): Snapshot commit message
- `--config PATH`: Path to configuration file
- `--repo PATH`: Path to audit repository (overrides config)
- `--paths PATH`: Specific paths to snapshot (can be specified multiple times)

**Examples:**
```bash
# Snapshot with config
sudo sysaudit snapshot -m "Before system upgrade" --config /etc/sysaudit/config.yaml

# Snapshot specific paths
sudo sysaudit snapshot -m "Manual backup" --repo /var/lib/sysaudit --paths /etc
```

### drift-check

Check for drift from baseline state.

```bash
sysaudit drift-check [OPTIONS]
```

**Options:**
- `--baseline TEXT`: Baseline branch/commit to compare against (default: main)
- `--severity [HIGH|MEDIUM|LOW]`: Filter by severity level
- `--config PATH`: Path to configuration file
- `--repo PATH`: Path to audit repository (overrides config)

**Examples:**
```bash
# Check all drift
sudo sysaudit drift-check --baseline main --repo /var/lib/sysaudit

# Check high severity only
sudo sysaudit drift-check --baseline main --severity HIGH --repo /var/lib/sysaudit

# Using config file
sudo sysaudit drift-check --config /etc/sysaudit/config.yaml
```

**Output:**
- Color-coded by severity (RED=HIGH, YELLOW=MEDIUM, GREEN=LOW)
- Shows change type: + (added), - (deleted), M (modified)
- Summary statistics by severity level

### compliance-report

Generate compliance security report.

```bash
sysaudit compliance-report [OPTIONS]
```

**Options:**
- `--format [text|html|json]`: Report format (default: text)
- `-o, --output PATH`: Output file (default: stdout)
- `--config PATH`: Path to configuration file
- `--paths PATH`: Specific paths to check (can be specified multiple times)

**Examples:**
```bash
# Text report to stdout
sudo sysaudit compliance-report --config /etc/sysaudit/config.yaml

# JSON report to file
sudo sysaudit compliance-report --format json --output report.json --paths /etc

# HTML report
sudo sysaudit compliance-report --format html --output report.html --paths /etc /usr/local/bin
```

**Exit Codes:**
- 0: No issues or only LOW/MEDIUM severity
- 1: HIGH severity issues found

### rollback

Rollback a file to a previous version from Git history.

```bash
sysaudit rollback --to-commit COMMIT --path PATH [OPTIONS]
```

**Options:**
- `--to-commit TEXT` (required): Target commit hash or reference
- `--path PATH` (required): File path to rollback
- `--dry-run`: Show what would be done without making changes
- `--config PATH`: Path to configuration file
- `--repo PATH`: Path to audit repository (overrides config)

**Examples:**
```bash
# Dry run first
sudo sysaudit rollback --to-commit abc123 --path /etc/config.conf --dry-run --repo /var/lib/sysaudit

# Actual rollback
sudo sysaudit rollback --to-commit abc123 --path /etc/config.conf --repo /var/lib/sysaudit

# Rollback to 5 commits ago
sudo sysaudit rollback --to-commit HEAD~5 --path /etc/ssh/sshd_config --repo /var/lib/sysaudit
```

**Safety:**
- Creates backup of current version before rollback
- Validates commit and file existence
- Dry-run mode available for testing

### examples

Show usage examples and common workflows.

```bash
sysaudit examples
```

Displays comprehensive examples of all commands and typical workflows.

## Typical Workflow

### 1. Initial Setup

```bash
# Initialize repository
sudo sysaudit init --repo /var/lib/sysaudit

# Edit configuration
sudo nano /etc/sysaudit/config.yaml

# Create initial snapshot
sudo sysaudit snapshot -m "Initial baseline" --config /etc/sysaudit/config.yaml
```

### 2. Continuous Monitoring

```bash
# Start monitoring (foreground)
sudo sysaudit monitor --config /etc/sysaudit/config.yaml

# Or as systemd service
sudo systemctl start sysaudit
sudo systemctl enable sysaudit
```

### 3. Regular Checks

```bash
# Check for drift
sudo sysaudit drift-check --baseline main --config /etc/sysaudit/config.yaml

# Run compliance checks
sudo sysaudit compliance-report --config /etc/sysaudit/config.yaml
```

### 4. Incident Response

```bash
# Check high severity changes
sudo sysaudit drift-check --severity HIGH --config /etc/sysaudit/config.yaml

# Rollback if needed
sudo sysaudit rollback --to-commit <commit> --path <file> --config /etc/sysaudit/config.yaml
```

## Configuration File

Example `/etc/sysaudit/config.yaml`:

```yaml
repository:
  path: /var/lib/sysaudit
  baseline: main
  gpg_sign: false

monitoring:
  paths:
    - /etc
    - /usr/local/bin
  blacklist_file: /etc/sysaudit/blacklist.txt
  whitelist_file: null
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
  journal_priority: CRIT
```

## Exit Codes

- `0`: Success
- `1`: Error or HIGH severity issues found (compliance-report)
- `130`: Interrupted by user (Ctrl+C)

## Error Handling

The CLI provides user-friendly error messages:

- **Permission denied**: Suggests running with sudo
- **File not found**: Shows which file/directory is missing
- **Repository not initialized**: Suggests running `sysaudit init`
- **Verbose mode**: Use `-v` or `SYSAUDIT_VERBOSE=1` for detailed tracebacks

## Tips

1. **Always use sudo**: Most operations require root privileges to access system files
2. **Test with dry-run**: Use `--dry-run` with rollback to preview changes
3. **Use config files**: Easier than specifying all options via CLI
4. **Check drift regularly**: Schedule periodic drift checks via cron
5. **Monitor compliance**: Run compliance reports before and after system changes

## Getting Help

```bash
# General help
sysaudit --help

# Command-specific help
sysaudit <command> --help

# Show examples
sysaudit examples
```

## Troubleshooting

### Command not found
```bash
# Reinstall package
pip install -e .
```

### Permission denied
```bash
# Run with sudo
sudo sysaudit <command>
```

### Repository not initialized
```bash
# Initialize first
sudo sysaudit init --repo /var/lib/sysaudit
```

### Verbose output for debugging
```bash
# Enable verbose mode
sysaudit -v <command>
# or
SYSAUDIT_VERBOSE=1 sysaudit <command>
```

## Systemd Service

For continuous monitoring, sysaudit can run as a systemd service.

### Installation

The systemd service is automatically installed when running `install.sh` as root:

```bash
sudo ./install.sh
```

Or manually:

```bash
sudo cp sysaudit.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/sysaudit.service
sudo systemctl daemon-reload
```

### Service Management

```bash
# Start the service
sudo systemctl start sysaudit

# Stop the service
sudo systemctl stop sysaudit

# Restart the service
sudo systemctl restart sysaudit

# Enable auto-start on boot
sudo systemctl enable sysaudit

# Disable auto-start
sudo systemctl disable sysaudit

# Check service status
sudo systemctl status sysaudit
```

### Viewing Logs

```bash
# View recent logs
sudo journalctl -u sysaudit

# Follow logs in real-time
sudo journalctl -u sysaudit -f

# View logs since boot
sudo journalctl -u sysaudit -b

# View logs with priority filter
sudo journalctl -u sysaudit -p err
```

### Service Features

The systemd service includes:

1. **Automatic Restart** (Requirement 7.2)
   - Restarts on failure
   - 10 second delay between restarts
   - Rate limiting to prevent restart loops

2. **Process Management** (Requirement 7.3)
   - Proper signal handling (SIGTERM for graceful shutdown)
   - No zombie processes
   - 30 second timeout for shutdown

3. **Security Hardening** (Requirement 7.4)
   - Filesystem protections (ProtectSystem=strict)
   - Private temporary directory
   - Capability restrictions
   - System call filtering
   - Resource limits

### Configuration

The service uses the configuration file at `/etc/sysaudit/config.yaml`. Edit this file to configure monitoring paths and options:

```bash
sudo nano /etc/sysaudit/config.yaml
sudo systemctl restart sysaudit
```

### Troubleshooting

**Service fails to start:**
```bash
# Check status and logs
sudo systemctl status sysaudit
sudo journalctl -u sysaudit -n 50

# Common issues:
# - Repository not initialized: sudo sysaudit init --repo /var/lib/sysaudit
# - Config file missing: Check /etc/sysaudit/config.yaml exists
# - Invalid paths: Verify monitored paths exist
```

**Service keeps restarting:**
```bash
# Check for configuration errors
sudo sysaudit monitor --config /etc/sysaudit/config.yaml

# View restart history
sudo systemctl status sysaudit
```

**High resource usage:**
```bash
# Check resource usage
systemctl show sysaudit | grep -E "(Memory|CPU|Tasks)"

# Reduce monitored paths or add more blacklist patterns
sudo nano /etc/sysaudit/config.yaml
```

For detailed systemd documentation, see [SYSTEMD_SERVICE.md](SYSTEMD_SERVICE.md).
