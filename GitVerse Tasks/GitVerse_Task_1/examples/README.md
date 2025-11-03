# Configuration Examples

This directory contains example configuration files for the System Audit tool.

## Files

### config.yaml
Full configuration file with all available options and detailed comments. Use this as a template for your production configuration.

**Location:** Copy to `/etc/sysaudit/config.yaml` or specify with `--config` flag

### config-minimal.yaml
Minimal configuration with only essential settings. Good starting point for quick setup.

### blacklist.txt
Default blacklist patterns for files that should be ignored during monitoring. Includes temporary files, logs, caches, and other commonly excluded patterns.

**Location:** Copy to `/etc/sysaudit/blacklist.txt` or specify in config file

## Usage

### Quick Start

1. Copy the minimal config:
```bash
sudo mkdir -p /etc/sysaudit
sudo cp examples/config-minimal.yaml /etc/sysaudit/config.yaml
sudo cp examples/blacklist.txt /etc/sysaudit/blacklist.txt
```

2. Edit the config to set your monitoring paths:
```bash
sudo nano /etc/sysaudit/config.yaml
```

3. Initialize the audit system:
```bash
sudo sysaudit init --repo /var/lib/sysaudit
```

4. Start monitoring:
```bash
sudo sysaudit monitor --config /etc/sysaudit/config.yaml
```

### Custom Configuration

For more advanced setups, use the full `config.yaml` as a template:

```bash
sudo cp examples/config.yaml /etc/sysaudit/config.yaml
```

Then customize:
- **monitoring.paths**: Add all directories you want to track
- **repository.gpg_sign**: Enable if you have GPG configured
- **compliance.auto_check**: Enable for automatic security checks
- **alerts.webhook_url**: Add your webhook endpoint for notifications

## Configuration Options

### Repository Section
- `path`: Where audit Git repository is stored
- `baseline`: Branch name for drift detection comparisons
- `gpg_sign`: Enable GPG commit signing (requires GPG setup)

### Monitoring Section
- `paths`: List of directories to monitor
- `blacklist_file`: Path to file with ignore patterns
- `whitelist_file`: Path to file with include-only patterns (optional)
- `batch_interval`: Seconds to wait before creating commit (default: 5)
- `batch_size`: Max events per batch (default: 10)

### Compliance Section
- `auto_check`: Run security checks automatically on changes

### Alerts Section
- `enabled`: Enable alert system
- `webhook_url`: HTTP endpoint for alert notifications

## Blacklist Patterns

The blacklist file supports glob patterns:
- `*.tmp` - matches all .tmp files
- `*.log.*` - matches rotated log files
- `/tmp/*` - matches everything in /tmp directory
- `__pycache__/*` - matches Python cache directories

Lines starting with `#` are comments and empty lines are ignored.

## CLI Overrides

Configuration file settings can be overridden via CLI arguments:

```bash
sysaudit monitor \
  --config /etc/sysaudit/config.yaml \
  --watch /etc \
  --watch /usr/local/bin \
  --repo /custom/repo/path
```

CLI arguments take precedence over config file settings.


## Example Scripts

This directory also contains example Python scripts demonstrating how to use the sysaudit library programmatically.

### filter_usage.py
Demonstrates the FilterManager for pattern-based file filtering:
- Loading blacklist/whitelist patterns
- Testing file paths against filters
- Using default ignore patterns

Run with:
```bash
python examples/filter_usage.py
```

### monitor_usage.py
Demonstrates the FileMonitor for real-time file system monitoring:
- Setting up file system watchers
- Event batching and filtering
- Process tracking for file changes

Run with:
```bash
python examples/monitor_usage.py
```

### git_usage.py
Demonstrates the GitManager for version control operations:
- Initializing Git repository
- Committing file changes with metadata
- Batch commits for multiple files
- Viewing commit history
- GPG signing configuration

Run with:
```bash
python examples/git_usage.py
```

This example creates temporary directories and demonstrates:
1. Repository initialization with baseline branch
2. Single file commits (create, modify)
3. Batch commits for multiple files
4. Commit history inspection
5. GPG signing status checks

### drift_usage.py
Demonstrates drift detection and severity scoring:
- Establishing a baseline state
- Making changes to files
- Detecting drift from baseline
- Severity scoring (HIGH/MEDIUM/LOW)
- Filtering changes by severity
- Custom severity patterns
- File history tracking
- Comparing files with baseline

Run with:
```bash
python examples/drift_usage.py
```

This example demonstrates:
1. Creating a baseline with initial files
2. Making various changes (add, modify, delete)
3. Detecting all changes from baseline
4. Automatic severity classification
5. Grouping changes by severity level
6. Using custom severity patterns
7. Viewing file change history
8. Comparing specific files with baseline

The example shows how critical system files (like /etc/sudoers) are automatically classified as HIGH severity, while user files are LOW severity.

### compliance_usage.py
Demonstrates the compliance checking system for security audits:
- Running compliance rules on files
- Detecting world-writable files
- Finding unexpected SUID/SGID binaries
- Checking weak permissions on sensitive files
- Generating reports in multiple formats (text, JSON, HTML)
- Scanning directories recursively
- Grouping issues by severity

Run with:
```bash
python examples/compliance_usage.py
```

This example demonstrates:
1. Creating test files with various security issues
2. Running compliance checks on specific files
3. Listing available compliance rules
4. Generating text reports for console output
5. Saving JSON reports for programmatic processing
6. Creating HTML reports for web viewing
7. Scanning entire directories recursively
8. Summarizing issues by severity level

The compliance checker includes rules for:
- **World-writable files**: Detects files in critical directories that are writable by all users
- **SUID/SGID binaries**: Finds unexpected setuid/setgid executables
- **Weak permissions**: Checks SSH keys, password files, and other sensitive files for proper permissions

### alert_usage.py
Demonstrates the AlertManager for security alert notifications:
- Sending alerts for compliance issues
- Severity-based filtering (HIGH/MEDIUM/LOW)
- Custom alert creation
- Webhook integration
- journald/syslog logging
- Multiple alert processing

Run with:
```bash
python examples/alert_usage.py
```

This example demonstrates:
1. Basic high-severity alert sending
2. Filtering alerts by severity threshold
3. Creating custom alerts with minimal or full details
4. Webhook integration for external notifications
5. Processing multiple alerts in sequence
6. Automatic logging to system journals

The AlertManager supports:
- **journald logging**: Native systemd journal integration on Linux
- **syslog fallback**: Automatic fallback to syslog on Unix systems
- **Webhook notifications**: HTTP POST to external endpoints with JSON payload
- **Severity filtering**: Only send alerts meeting minimum severity threshold
- **Custom alerts**: Create alerts for any security event, not just compliance issues

Alerts are automatically logged with appropriate priority levels:
- HIGH severity → LOG_CRIT (critical)
- MEDIUM severity → LOG_WARNING (warning)
- LOW severity → LOG_NOTICE (notice)

All examples are self-contained and use temporary directories for safe testing.
