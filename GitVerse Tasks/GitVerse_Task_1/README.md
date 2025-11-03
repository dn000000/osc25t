# Git-based System Audit & Compliance Monitor

A Python-based system for continuous monitoring of critical system files, automatic versioning in Git, drift detection, and compliance checking. Designed for system administrators and security professionals who need to track and audit changes to critical system configurations.

## Features

- **Real-time File Monitoring**: Track changes to critical system files using inotify/watchdog
- **Automatic Git Versioning**: All changes are automatically committed to a Git repository with metadata
- **Drift Detection**: Compare current system state against a baseline with severity scoring
- **Compliance Checking**: Automated security compliance checks (world-writable files, SUID/SGID binaries, weak permissions)
- **Rollback Capability**: Restore files to previous versions from Git history with safety backups
- **Alert System**: Notifications via journald and webhooks for critical issues
- **Process Tracking**: Identify which process made changes to files
- **Event Batching**: Intelligent batching to reduce commit noise
- **Flexible Filtering**: Whitelist/blacklist patterns with glob support
- **Systemd Integration**: Run as a system service with automatic restart and security hardening

## Use Cases

- **Configuration Management**: Track all changes to system configuration files
- **Security Auditing**: Detect unauthorized modifications to critical files
- **Compliance Monitoring**: Ensure systems meet security policies (PCI-DSS, HIPAA, etc.)
- **Incident Response**: Quickly identify what changed and when during security incidents
- **Change Tracking**: Maintain complete audit trail of system modifications
- **Disaster Recovery**: Rollback files to known-good states

## Requirements

- Python 3.8 or higher
- Git 2.0 or higher
- Linux operating system (uses inotify for file monitoring)
- Root privileges (for monitoring system files)

## Docker Testing Pipeline

Проект включает полный Docker пайплайн для сборки и тестирования:

```bash
# Быстрый запуск всех тестов
./scripts/run-docker-tests.sh  # Linux/macOS
.\scripts\run-docker-tests.ps1  # Windows

# Или через docker-compose
docker-compose up --abort-on-container-exit
```

**Документация:**
- [Быстрый старт](QUICK_START_DOCKER.md) - запуск за 30 секунд
- [Полная документация](README_DOCKER.md) - детальное описание
- [Примеры использования](DOCKER_EXAMPLES.md) - практические сценарии

**Что тестируется:**
- ✅ Unit тесты - отдельные компоненты
- ✅ Integration тесты - взаимодействие компонентов
- ✅ Compliance тесты - требования безопасности
- ✅ E2E тесты - реальные пользовательские сценарии

**CI/CD:** GitHub Actions автоматически запускает все тесты при push и PR.

## Installation

### Quick Install (Recommended)

The installation script automatically checks dependencies, installs the package, and sets up configuration:

```bash
# Clone or download the repository
git clone https://github.com/sysaudit/sysaudit.git
cd sysaudit

# Run installation script
chmod +x install.sh
sudo ./install.sh
```

The script will:
- ✓ Check for required dependencies (git, python3, pip3)
- ✓ Verify Python version (3.8+)
- ✓ Install the sysaudit package and all dependencies
- ✓ Create configuration directories (`/etc/sysaudit`, `/var/lib/sysaudit`)
- ✓ Generate example configuration files
- ✓ Install systemd service (when run as root)
- ✓ Verify CLI command availability

### Manual Install

If you prefer manual installation:

```bash
# Install Python package and dependencies
pip3 install -e .

# Create configuration directories
sudo mkdir -p /etc/sysaudit
sudo mkdir -p /var/lib/sysaudit

# Create example configuration
sudo cp examples/config.yaml /etc/sysaudit/config.yaml.example
sudo cp examples/blacklist.txt /etc/sysaudit/blacklist.txt

# Copy and enable systemd service (optional)
sudo cp sysaudit.service /etc/systemd/system/
sudo systemctl daemon-reload
```

### Verify Installation

```bash
# Check that sysaudit command is available
sysaudit --help

# Check version
sysaudit --version
```

## Quick Start

### 1. Initialize the System

```bash
# Initialize Git repository and configuration
sudo sysaudit init --repo /var/lib/sysaudit/repo

# Copy and edit configuration
sudo cp /etc/sysaudit/config.yaml.example /etc/sysaudit/config.yaml
sudo nano /etc/sysaudit/config.yaml
```

### 2. Start Monitoring

```bash
# Start monitoring with configuration file
sudo sysaudit monitor --config /etc/sysaudit/config.yaml

# Or use systemd service for continuous monitoring
sudo systemctl enable sysaudit
sudo systemctl start sysaudit
```

### 3. Check System Status

```bash
# Check for drift from baseline
sudo sysaudit drift-check --baseline main --config /etc/sysaudit/config.yaml

# Generate compliance report
sudo sysaudit compliance-report --config /etc/sysaudit/config.yaml
```

## Usage Examples

For comprehensive usage examples and common workflows, see [Usage Examples Guide](docs/USAGE_EXAMPLES.md).

### Initialize the Audit System

```bash
# Basic initialization
sudo sysaudit init --repo /var/lib/sysaudit/repo

# Initialize with custom baseline branch
sudo sysaudit init --repo /var/lib/sysaudit/repo --baseline production
```

### Start Monitoring

```bash
# Monitor specific paths
sudo sysaudit monitor --watch /etc --watch /usr/local/bin --repo /var/lib/sysaudit/repo

# Monitor with configuration file
sudo sysaudit monitor --config /etc/sysaudit/config.yaml

# Run as daemon (background process)
sudo sysaudit monitor --daemon --config /etc/sysaudit/config.yaml
```

### Create Manual Snapshots

```bash
# Create snapshot before system changes
sudo sysaudit snapshot -m "Pre-upgrade snapshot" --config /etc/sysaudit/config.yaml

# Snapshot specific paths
sudo sysaudit snapshot -m "Backup SSH config" --repo /var/lib/sysaudit/repo --paths /etc/ssh
```

### Check for Drift

```bash
# Compare with baseline (main branch)
sudo sysaudit drift-check --baseline main --config /etc/sysaudit/config.yaml

# Filter by severity level
sudo sysaudit drift-check --baseline main --severity HIGH --config /etc/sysaudit/config.yaml

# Check specific repository
sudo sysaudit drift-check --baseline main --repo /var/lib/sysaudit/repo
```

### Generate Compliance Reports

```bash
# Text format to stdout (default)
sudo sysaudit compliance-report --config /etc/sysaudit/config.yaml

# JSON format to file
sudo sysaudit compliance-report --format json --output /tmp/compliance-report.json --paths /etc

# HTML format for web viewing
sudo sysaudit compliance-report --format html --output /var/www/html/compliance.html --paths /etc /usr/local/bin
```

### Rollback Files

```bash
# Dry run first (recommended)
sudo sysaudit rollback --to-commit abc123 --path /etc/ssh/sshd_config --dry-run --repo /var/lib/sysaudit/repo

# Actual rollback (creates backup automatically)
sudo sysaudit rollback --to-commit abc123 --path /etc/ssh/sshd_config --repo /var/lib/sysaudit/repo

# Rollback to 5 commits ago
sudo sysaudit rollback --to-commit HEAD~5 --path /etc/config.conf --repo /var/lib/sysaudit/repo
```

### View Examples

```bash
# Show comprehensive usage examples
sysaudit examples
```

## Configuration

The main configuration file is located at `/etc/sysaudit/config.yaml`. After installation, copy the example and customize it:

```bash
sudo cp /etc/sysaudit/config.yaml.example /etc/sysaudit/config.yaml
sudo nano /etc/sysaudit/config.yaml
```

For comprehensive configuration documentation, see [Configuration Guide](docs/CONFIGURATION.md).

### Configuration File

### Configuration Options

```yaml
# Repository settings
repository:
  path: /var/lib/sysaudit/repo          # Git repository path
  baseline: main                         # Baseline branch for drift detection
  gpg_sign: false                        # Enable GPG signing of commits

# Monitoring settings
monitoring:
  paths:                                 # Paths to monitor (can specify multiple)
    - /etc
    - /usr/local/bin
    - /usr/local/etc
  blacklist_file: /etc/sysaudit/blacklist.txt  # Patterns to ignore
  whitelist_file: null                   # If set, only monitor whitelisted files
  batch_interval: 5                      # Seconds to wait before batching events
  batch_size: 10                         # Number of events to batch together

# Compliance checking
compliance:
  auto_check: false                      # Run compliance checks on file changes
  rules:                                 # Enabled compliance rules
    - world-writable                     # Detect world-writable files
    - suid-sgid                          # Detect unexpected SUID/SGID binaries
    - weak-permissions                   # Detect weak permissions on sensitive files

# Alert settings
alerts:
  enabled: true                          # Enable alert system
  webhook_url: null                      # Webhook URL for notifications (optional)
  journal_priority: CRIT                 # journald priority level (CRIT, ERR, WARNING)
```

### Blacklist Patterns

The blacklist file (`/etc/sysaudit/blacklist.txt`) uses glob patterns to ignore files:

```
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

# System directories
/tmp/*
/var/tmp/*
/var/log/*
/var/cache/*
```

### Whitelist Patterns

If you want to monitor only specific files, create a whitelist file:

```yaml
monitoring:
  whitelist_file: /etc/sysaudit/whitelist.txt
```

Example whitelist:
```
/etc/ssh/*
/etc/sudoers
/etc/passwd
/etc/shadow
/etc/pam.d/*
```

### Configuration Priority

Configuration can be specified in multiple ways (in order of precedence):

1. **CLI arguments** (highest priority)
2. **Configuration file** (`--config` option)
3. **Default values** (lowest priority)

Example:
```bash
# Config file specifies /etc, but CLI overrides it
sudo sysaudit monitor --config /etc/sysaudit/config.yaml --watch /usr/local/bin
```

## Systemd Service

For continuous monitoring, sysaudit can run as a systemd service with automatic restart and security hardening.

### Installation

The systemd service is automatically installed when running `install.sh` as root. For manual installation:

```bash
sudo cp sysaudit.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/sysaudit.service
sudo systemctl daemon-reload
```

### Service Management

```bash
# Enable auto-start on boot
sudo systemctl enable sysaudit

# Start the service
sudo systemctl start sysaudit

# Check status
sudo systemctl status sysaudit

# Stop the service
sudo systemctl stop sysaudit

# Restart the service
sudo systemctl restart sysaudit

# Disable auto-start
sudo systemctl disable sysaudit
```

### Viewing Logs

```bash
# View recent logs
sudo journalctl -u sysaudit

# Follow logs in real-time
sudo journalctl -u sysaudit -f

# View logs since boot
sudo journalctl -u sysaudit -b

# View only errors
sudo journalctl -u sysaudit -p err
```

### Service Features

The systemd service includes:

- **Automatic Restart**: Restarts on failure with 10-second delay
- **Security Hardening**: Filesystem protections, capability restrictions, system call filtering
- **Process Management**: Proper signal handling, no zombie processes
- **Resource Limits**: Memory and CPU limits to prevent resource exhaustion
- **Graceful Shutdown**: 30-second timeout for clean shutdown

### Configuration

The service uses the configuration file at `/etc/sysaudit/config.yaml`. After editing the config, restart the service:

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
# - Repository not initialized: sudo sysaudit init --repo /var/lib/sysaudit/repo
# - Config file missing: Check /etc/sysaudit/config.yaml exists
# - Invalid paths: Verify monitored paths exist
```

**Service keeps restarting:**
```bash
# Test configuration manually
sudo sysaudit monitor --config /etc/sysaudit/config.yaml

# View restart history
sudo systemctl status sysaudit
```

For detailed systemd documentation, see [docs/SYSTEMD_SERVICE.md](docs/SYSTEMD_SERVICE.md).

## Architecture

### Components

- **CLI Interface** (`sysaudit/cli.py`): Command-line interface using Click
- **Core Engine** (`sysaudit/core/engine.py`): Orchestrates all subsystems
- **File Monitor** (`sysaudit/monitor/`): Watches file system changes using watchdog
- **Git Manager** (`sysaudit/git/`): Manages Git operations, commits, and history
- **Compliance Checker** (`sysaudit/compliance/`): Security compliance rules and reporting
- **Alert Manager** (`sysaudit/alert/`): Notification system for critical issues
- **Configuration** (`sysaudit/config.py`): Configuration management

### Data Flow

```
File Change → Event Filter → Event Batcher → Git Commit → Compliance Check → Alert (if needed)
```

## Advanced Usage

### Process Tracking

Sysaudit attempts to identify which process made changes to files:

```bash
# View commit messages to see process information
cd /var/lib/sysaudit/repo
git log --oneline
git show <commit-hash>
```

Commit messages include:
- File path and change type
- Timestamp (ISO8601 format)
- Process name and PID (when available)

### GPG Signing

Enable GPG signing for commit integrity:

```yaml
repository:
  gpg_sign: true
```

Ensure GPG is configured:
```bash
git config --global user.signingkey <key-id>
```

### Webhook Notifications

Configure webhook for external integrations:

```yaml
alerts:
  enabled: true
  webhook_url: https://your-webhook-endpoint.com/alerts
```

Webhook payload format:
```json
{
  "severity": "HIGH",
  "rule": "world-writable",
  "path": "/etc/sensitive-file",
  "description": "File is world-writable",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Severity Scoring

Files are automatically scored by severity:

- **HIGH**: Critical system files (`/etc/sudoers`, `/etc/shadow`, `/etc/ssh/sshd_config`, etc.)
- **MEDIUM**: System directories (`/etc/*`, `/usr/bin/*`, `/usr/local/bin/*`)
- **LOW**: Other monitored files

### Compliance Rules

Built-in compliance rules:

1. **world-writable**: Detects files with world-writable permissions in critical directories
2. **suid-sgid**: Detects unexpected SUID/SGID binaries
3. **weak-permissions**: Detects weak permissions on sensitive files (SSH keys, etc.)

## Examples

See the `examples/` directory for detailed usage examples:

- `examples/monitor_usage.py`: File monitoring examples
- `examples/git_usage.py`: Git operations examples
- `examples/drift_usage.py`: Drift detection examples
- `examples/compliance_usage.py`: Compliance checking examples
- `examples/rollback_usage.py`: Rollback examples
- `examples/alert_usage.py`: Alert system examples
- `examples/cli_usage.py`: CLI usage examples

## Documentation

- [CLI Reference](docs/CLI_REFERENCE.md): Complete CLI command reference
- [Configuration Guide](docs/CONFIGURATION.md): Comprehensive configuration documentation
- [Usage Examples](docs/USAGE_EXAMPLES.md): Common workflows and practical scenarios
- [Systemd Service](docs/SYSTEMD_SERVICE.md): Detailed systemd service documentation
- [Examples README](examples/README.md): Overview of example scripts and code samples
- [Testing Guide](TESTING.md): Testing documentation and guidelines

## Troubleshooting

### Command not found

```bash
# Reinstall package
pip3 install -e .

# Check if ~/.local/bin is in PATH
echo $PATH | grep -q "$HOME/.local/bin" || echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
```

### Permission denied

Most operations require root privileges:
```bash
sudo sysaudit <command>
```

### Repository not initialized

```bash
sudo sysaudit init --repo /var/lib/sysaudit/repo
```

### Verbose output for debugging

```bash
# Enable verbose mode
sysaudit -v <command>

# Or use environment variable
SYSAUDIT_VERBOSE=1 sysaudit <command>
```

### High resource usage

If monitoring too many files:
1. Add more patterns to blacklist file
2. Reduce monitored paths in config
3. Increase batch_interval to reduce commit frequency

## Development

### Install development dependencies

```bash
pip3 install -e ".[dev]"
```

### Run tests

The project includes a comprehensive test suite with a custom test runner:

```bash
# Run all tests
python run_tests.py

# Run with coverage report
python run_tests.py --coverage

# Run only unit tests
python run_tests.py --unit

# Run only integration tests
python run_tests.py --integration

# Run specific test file
python run_tests.py tests/test_filter.py

# Skip slow tests
python run_tests.py --fast

# Run with verbose output
python run_tests.py --verbose
```

Using Make (if available):
```bash
make test              # Run all tests
make test-coverage     # Run with coverage
make test-unit         # Run unit tests only
make test-html         # Generate HTML coverage report
```

Using pytest directly:
```bash
pytest                                    # Run all tests
pytest --cov=sysaudit                    # Run with coverage
pytest tests/test_file_monitor.py        # Run specific file
pytest -v                                 # Verbose output
```

For detailed testing documentation, see [TESTING.md](TESTING.md).

### Code formatting

```bash
# Format code
black sysaudit/

# Check formatting
black --check sysaudit/

# Lint code
flake8 sysaudit/

# Type checking
mypy sysaudit/
```

Using Make:
```bash
make format    # Format code
make lint      # Run linting
make check     # Run all checks (lint + test)
```

### Project Structure

```
sysaudit/
├── sysaudit/           # Main package
│   ├── cli.py          # CLI interface
│   ├── config.py       # Configuration management
│   ├── models.py       # Data models
│   ├── core/           # Core engine
│   ├── monitor/        # File monitoring
│   ├── git/            # Git operations
│   ├── compliance/     # Compliance checking
│   └── alert/          # Alert system
├── tests/              # Test suite
├── examples/           # Usage examples
├── docs/               # Documentation
├── install.sh          # Installation script
├── sysaudit.service    # Systemd service file
└── pyproject.toml      # Package configuration
```

## Security Considerations

- **Run as root**: Required to monitor system files, but be aware of security implications
- **Repository security**: Protect the audit repository with appropriate permissions
- **GPG signing**: Enable for commit integrity verification
- **Webhook security**: Use HTTPS and authentication for webhook endpoints
- **Systemd hardening**: Service includes security restrictions (see systemd service file)

## Performance

- **Event batching**: Reduces Git commit overhead by batching events
- **Efficient filtering**: Blacklist/whitelist applied before processing
- **Lazy compliance**: Compliance checks run on-demand, not on every change
- **Resource limits**: Systemd service includes memory and CPU limits

## License

MIT License - see LICENSE file for details

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with tests
4. Run tests and linting
5. Submit a pull request

## Support

- **Issues**: Report bugs and request features on GitHub Issues
- **Documentation**: See `docs/` directory for detailed documentation
- **Examples**: Check `examples/` directory for usage examples