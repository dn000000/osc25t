# GitProc - Git-backed Process Manager

A systemd-like process manager that stores service configurations in a Git repository, providing version control, rollback capabilities, and distributed service management.

## Features

### Core Features
- **Git-based Configuration**: Store service unit files in a Git repository with full version history
- **Process Lifecycle Management**: Start, stop, restart, and monitor services
- **Automatic Restart**: Configure services to restart automatically on failure
- **Process Isolation**: Run services in isolated PID namespaces (Linux)
- **Resource Limits**: Control CPU and memory usage with cgroups
- **Graceful Shutdown**: SIGTERM with fallback to SIGKILL after timeout
- **Output Capture**: Capture and view service stdout/stderr logs

### Advanced Features
- **Auto-Sync**: Automatically detect Git changes and apply configuration updates
- **Configuration Rollback**: Revert to previous configurations using Git commits
- **Service Dependencies**: Define startup order with `After` directives
- **HTTP Health Checks**: Automatically restart unhealthy services
- **Privilege Dropping**: Run services as non-root users for security
- **Daemon Mode**: Background process for continuous monitoring

## Requirements

- Python 3.8 or higher
- Git 2.0 or higher
- Linux kernel 3.8+ (for full feature support including PID namespaces and cgroups)
- Root privileges (for namespace and cgroup operations)

## Installation

### Linux/Unix

```bash
# Clone the repository
git clone <repository-url>
cd gitproc

# Run the setup script
chmod +x setup.sh
./setup.sh

# Verify installation
python3 -m gitproc.cli --help
```

### Windows

```cmd
REM Clone the repository
git clone <repository-url>
cd gitproc

REM Run the setup script
setup.bat

REM Verify installation
python -m gitproc.cli --help
```

**Note**: Windows has limited support. PID namespace isolation and cgroups are not available on Windows.

## Quick Start

### 1. Initialize a Service Repository

```bash
# Create and initialize a Git repository for services
python3 -m gitproc.cli init --repo /etc/gitproc/services
```

This creates the directory structure and initializes a Git repository.

### 2. Create a Service Unit File

Create a file `/etc/gitproc/services/my-app.service`:

```ini
[Service]
ExecStart=/usr/bin/python3 -m http.server 8080
Restart=always
User=nobody
Environment=PORT=8080
```

Commit the file to Git:

```bash
cd /etc/gitproc/services
git add my-app.service
git commit -m "Add my-app service"
```

### 3. Start the Daemon

```bash
# Start the daemon in the background
python3 -m gitproc.cli daemon --watch-branch main
```

The daemon will monitor the Git repository and manage all services.

### 4. Manage Services

```bash
# Start a service
python3 -m gitproc.cli start my-app

# Check service status
python3 -m gitproc.cli status my-app

# View service logs
python3 -m gitproc.cli logs my-app

# Stop a service
python3 -m gitproc.cli stop my-app

# Restart a service
python3 -m gitproc.cli restart my-app

# List all services
python3 -m gitproc.cli list
```

## Command Reference

### `init`
Initialize a new Git repository for service management.

```bash
python3 -m gitproc.cli init --repo <path>
```

**Options:**
- `--repo`: Path to create the service repository (required)

### `daemon`
Start the background daemon process.

```bash
python3 -m gitproc.cli daemon [--watch-branch <branch>]
```

**Options:**
- `--watch-branch`: Git branch to monitor (default: main)

### `start`
Start a service.

```bash
python3 -m gitproc.cli start <service-name>
```

### `stop`
Stop a running service.

```bash
python3 -m gitproc.cli stop <service-name>
```

### `restart`
Restart a service (stop then start).

```bash
python3 -m gitproc.cli restart <service-name>
```

### `status`
Display the status of a service.

```bash
python3 -m gitproc.cli status <service-name>
```

**Output includes:**
- Service name
- Current status (running/stopped/failed)
- Process ID (if running)
- Start time
- Restart count
- Last exit code

### `logs`
View service output logs.

```bash
python3 -m gitproc.cli logs <service-name> [--follow] [--lines <n>]
```

**Options:**
- `--follow`, `-f`: Stream logs in real-time
- `--lines`, `-n`: Number of lines to display (default: all)

### `list`
List all available services.

```bash
python3 -m gitproc.cli list
```

### `rollback`
Rollback service configurations to a previous Git commit.

```bash
python3 -m gitproc.cli rollback <commit-hash>
```

### `sync`
Manually trigger Git synchronization.

```bash
python3 -m gitproc.cli sync
```

## Unit File Format

Unit files use an INI-style format similar to systemd. They must have a `.service` extension and contain a `[Service]` section.

### Supported Directives

#### Required Directives

- **ExecStart**: Command to execute (required)
  ```ini
  ExecStart=/usr/bin/python3 /app/server.py
  ```

#### Optional Directives

- **Restart**: Restart policy
  - `always`: Always restart on exit
  - `on-failure`: Restart only on non-zero exit
  - `no`: Never restart (default)
  ```ini
  Restart=always
  ```

- **User**: User to run the service as
  ```ini
  User=nobody
  ```

- **Environment**: Environment variables (can be specified multiple times)
  ```ini
  Environment=PORT=8080
  Environment=DEBUG=true
  ```

- **MemoryLimit**: Maximum memory usage
  ```ini
  MemoryLimit=100M
  MemoryLimit=1G
  ```

- **CPUQuota**: CPU usage limit as percentage
  ```ini
  CPUQuota=50%
  ```

- **HealthCheckURL**: HTTP endpoint for health checks
  ```ini
  HealthCheckURL=http://localhost:8080/health
  ```

- **HealthCheckInterval**: Health check interval in seconds (default: 30)
  ```ini
  HealthCheckInterval=60
  ```

- **After**: Service dependencies (start after these services)
  ```ini
  After=database.service
  After=network.service
  ```

### Example Unit Files

See the `examples/` directory for complete examples:
- `simple-http-server.service` - Basic Python HTTP server
- `nginx.service` - Web server with resource limits
- `app-with-healthcheck.service` - Application with health monitoring
- `dependent-services.service` - Services with dependencies

## Configuration

GitProc uses a configuration file located at `~/.gitproc/config.json` (or specified via `--config`).

### Default Configuration

```json
{
  "repo_path": "/etc/gitproc/services",
  "branch": "main",
  "socket_path": "/var/run/gitproc.sock",
  "state_file": "/var/lib/gitproc/state.json",
  "log_dir": "/var/log/gitproc",
  "cgroup_root": "/sys/fs/cgroup/gitproc"
}
```

### Configuration Options

- **repo_path**: Path to the Git repository containing service unit files
- **branch**: Git branch to monitor for changes
- **socket_path**: Unix socket path for daemon communication
- **state_file**: Path to persist service state
- **log_dir**: Directory for service logs
- **cgroup_root**: Root directory for cgroups

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI Interface                        │
│  (gitproc init/daemon/start/stop/status/logs/rollback)     │
└────────────────────────┬────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                      Daemon Process                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Git Monitor  │  │Health Monitor│  │Process Monitor│     │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘     │
│         │                  │                  │              │
│         └──────────────────┴──────────────────┘              │
│                            │                                 │
│                            ▼                                 │
│         ┌──────────────────────────────────┐                │
│         │      State Manager               │                │
│         │  (Service Registry & State)      │                │
│         └──────────────┬───────────────────┘                │
│                        │                                     │
└────────────────────────┼─────────────────────────────────────┘
                         │
         ┌───────────────┼───────────────┐
         │               │               │
         ▼               ▼               ▼
┌────────────────┐ ┌──────────┐ ┌──────────────┐
│ Process Manager│ │Git Repo  │ │Resource Ctrl │
│ (spawn/kill)   │ │Integration│ │  (cgroups)   │
└────────────────┘ └──────────┘ └──────────────┘
         │
         ▼
┌────────────────────────────────────┐
│  Isolated Processes (PID namespace)│
│  ┌──────┐  ┌──────┐  ┌──────┐    │
│  │Svc A │  │Svc B │  │Svc C │    │
│  └──────┘  └──────┘  └──────┘    │
└────────────────────────────────────┘
```

## Troubleshooting

### Daemon won't start

**Problem**: Daemon fails to start or exits immediately.

**Solutions**:
- Check if another daemon instance is running: `ps aux | grep gitproc`
- Verify the socket path is not in use: `ls -la /var/run/gitproc.sock`
- Check daemon logs: `cat /var/log/gitproc/daemon.log`
- Ensure you have root privileges for namespace/cgroup operations

### Service won't start

**Problem**: Service fails to start or immediately exits.

**Solutions**:
- Check service status: `python3 -m gitproc.cli status <service>`
- View service logs: `python3 -m gitproc.cli logs <service>`
- Verify the ExecStart command is correct and executable
- Check file permissions on the executable
- Ensure dependencies (After directive) are satisfied

### Permission denied errors

**Problem**: Permission errors when starting services or creating cgroups.

**Solutions**:
- Run daemon with root privileges: `sudo python3 -m gitproc.cli daemon`
- Check cgroup mount point: `mount | grep cgroup`
- Verify user exists if using User directive: `id <username>`
- Check file permissions in the service repository

### Git sync not working

**Problem**: Changes to unit files are not detected.

**Solutions**:
- Verify changes are committed: `cd /etc/gitproc/services && git log`
- Check daemon is monitoring correct branch: `python3 -m gitproc.cli daemon --watch-branch main`
- Manually trigger sync: `python3 -m gitproc.cli sync`
- Check daemon logs for Git errors

### Resource limits not applied

**Problem**: Memory or CPU limits are not enforced.

**Solutions**:
- Verify cgroups v2 is available: `mount | grep cgroup2`
- Check cgroup directory exists: `ls -la /sys/fs/cgroup/gitproc`
- Ensure daemon has permissions to create cgroups (requires root)
- Check service logs for cgroup creation errors

### Health checks failing

**Problem**: Service is restarted repeatedly due to health check failures.

**Solutions**:
- Verify the health check URL is correct and accessible
- Check if service is actually listening on the specified port: `netstat -tlnp | grep <port>`
- Increase HealthCheckInterval to give service more time to start
- Check service logs for application errors
- Test health endpoint manually: `curl http://localhost:8080/health`

### Process becomes zombie

**Problem**: Stopped processes remain as zombies.

**Solutions**:
- Restart the daemon to clean up zombie processes
- Check if SIGCHLD handler is working correctly
- Verify process is properly terminated with SIGKILL if needed

### Cannot connect to daemon

**Problem**: CLI commands fail with "Cannot connect to daemon" error.

**Solutions**:
- Verify daemon is running: `ps aux | grep gitproc`
- Check socket file exists: `ls -la /var/run/gitproc.sock`
- Verify socket permissions allow your user to connect
- Check if socket path in config matches daemon socket path

## Documentation

📖 **[Documentation Index](DOCS_INDEX.md)** - Complete navigation guide to all documentation

## Testing

Run the test suite to verify installation:

```bash
# Run all tests
./run_tests.sh

# Run specific test file
pytest tests/test_cli.py

# Run with coverage
pytest --cov=gitproc tests/

# Run in Docker (Linux environment)
./run_tests_docker.sh
```

For detailed testing information, see [Testing Guide](docs/TESTING.md).

## Support

For issues and questions:
- Check the troubleshooting section above
- Review the example unit files in `examples/`
- Check service logs: `python3 -m gitproc.cli logs <service>`
- Check daemon logs: `/var/log/gitproc/daemon.log`
