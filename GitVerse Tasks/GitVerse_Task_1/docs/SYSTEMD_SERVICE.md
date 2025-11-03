# Systemd Service Integration

This document describes how to install and manage the sysaudit systemd service for continuous monitoring.

## Installation

### 1. Install the Service File

Copy the service file to the systemd directory:

```bash
sudo cp sysaudit.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/sysaudit.service
```

### 2. Initialize the Audit System

Before starting the service, initialize the audit repository:

```bash
sudo sysaudit init --repo /var/lib/sysaudit --baseline main
```

### 3. Configure the Service

Edit the configuration file at `/etc/sysaudit/config.yaml`:

```bash
sudo nano /etc/sysaudit/config.yaml
```

Example configuration:

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

### 4. Reload Systemd

Reload systemd to recognize the new service:

```bash
sudo systemctl daemon-reload
```

## Service Management

### Start the Service

```bash
sudo systemctl start sysaudit
```

### Stop the Service

```bash
sudo systemctl stop sysaudit
```

### Restart the Service

```bash
sudo systemctl restart sysaudit
```

### Enable Auto-start on Boot

```bash
sudo systemctl enable sysaudit
```

### Disable Auto-start

```bash
sudo systemctl disable sysaudit
```

### Check Service Status

```bash
sudo systemctl status sysaudit
```

Expected output when running:
```
● sysaudit.service - Git-based System Audit & Compliance Monitor
     Loaded: loaded (/etc/systemd/system/sysaudit.service; enabled; vendor preset: enabled)
     Active: active (running) since Sat 2025-10-25 10:00:00 UTC; 5min ago
       Docs: https://github.com/yourusername/sysaudit
   Main PID: 12345 (sysaudit)
      Tasks: 3 (limit: 256)
     Memory: 45.2M
        CPU: 1.234s
     CGroup: /system.slice/sysaudit.service
             └─12345 /usr/bin/python3 /usr/local/bin/sysaudit monitor --config /etc/sysaudit/config.yaml --daemon
```

## Viewing Logs

### View Recent Logs

```bash
sudo journalctl -u sysaudit
```

### Follow Logs in Real-time

```bash
sudo journalctl -u sysaudit -f
```

### View Logs Since Boot

```bash
sudo journalctl -u sysaudit -b
```

### View Logs with Priority Filter

```bash
# Only critical and error messages
sudo journalctl -u sysaudit -p err

# All messages including info
sudo journalctl -u sysaudit -p info
```

## Service Features

### Restart Policies (Requirement 7.2)

The service is configured to automatically restart on failure:
- **Restart**: `on-failure` - Restarts only when the process exits with an error
- **RestartSec**: `10s` - Waits 10 seconds before restarting
- **StartLimitInterval**: `300s` - Monitors restart frequency over 5 minutes
- **StartLimitBurst**: `5` - Allows up to 5 restarts within the interval

This ensures the service remains running even if temporary issues occur.

### Process Management (Requirement 7.3)

The service properly manages processes to prevent zombie processes:
- **KillMode**: `mixed` - Sends SIGTERM to main process, SIGKILL to remaining processes
- **KillSignal**: `SIGTERM` - Graceful shutdown signal
- **TimeoutStopSec**: `30s` - Allows 30 seconds for graceful shutdown

### Security Hardening (Requirement 7.4)

The service includes multiple security hardening options:

#### Filesystem Protections
- **ProtectSystem**: `strict` - Makes most of the filesystem read-only
- **ProtectHome**: `true` - Makes home directories inaccessible
- **ReadWritePaths**: Allows writing only to necessary directories
- **ReadOnlyPaths**: Explicitly marks monitored paths as read-only

#### Privilege Restrictions
- **NoNewPrivileges**: `false` - Required for file monitoring capabilities
- **PrivateTmp**: `true` - Uses private /tmp directory
- **PrivateDevices**: `false` - Needs access to devices for monitoring

#### Namespace Isolation
- **ProtectKernelTunables**: `true` - Prevents kernel parameter changes
- **ProtectKernelModules**: `true` - Prevents kernel module loading
- **ProtectControlGroups**: `true` - Protects cgroup filesystem

#### Capability Restrictions
- **CapabilityBoundingSet**: Limited to necessary capabilities
  - `CAP_DAC_READ_SEARCH` - Read files bypassing permissions
  - `CAP_FOWNER` - Bypass file ownership checks
  - `CAP_CHOWN` - Change file ownership
  - `CAP_FSETID` - Set file capabilities

#### Resource Limits
- **LimitNOFILE**: `65536` - Maximum open files
- **LimitNPROC**: `512` - Maximum processes
- **TasksMax**: `256` - Maximum tasks

## Troubleshooting

### Service Fails to Start

1. Check the service status:
   ```bash
   sudo systemctl status sysaudit
   ```

2. View detailed logs:
   ```bash
   sudo journalctl -u sysaudit -n 50
   ```

3. Common issues:
   - **Repository not initialized**: Run `sudo sysaudit init --repo /var/lib/sysaudit`
   - **Configuration file missing**: Ensure `/etc/sysaudit/config.yaml` exists
   - **Permission issues**: Verify the service runs as root
   - **Invalid paths**: Check that monitored paths exist

### Service Keeps Restarting

If the service restarts repeatedly:

1. Check for configuration errors:
   ```bash
   sudo sysaudit monitor --config /etc/sysaudit/config.yaml
   ```

2. Verify monitored paths exist:
   ```bash
   cat /etc/sysaudit/config.yaml | grep -A 5 "paths:"
   ```

3. Check system resources:
   ```bash
   systemctl show sysaudit | grep -E "(Memory|CPU|Tasks)"
   ```

### High Resource Usage

If the service uses too much CPU or memory:

1. Reduce monitored paths in configuration
2. Add more patterns to blacklist file
3. Increase batch interval in configuration
4. Check for rapid file changes in monitored directories

### Permission Denied Errors

If you see permission errors in logs:

1. Verify the service runs as root:
   ```bash
   systemctl show sysaudit | grep User
   ```

2. Check ReadWritePaths in service file:
   ```bash
   grep ReadWritePaths /etc/systemd/system/sysaudit.service
   ```

3. Add necessary paths to ReadWritePaths if needed

## Testing the Service

### Manual Test Before Enabling

1. Start the service manually:
   ```bash
   sudo systemctl start sysaudit
   ```

2. Check status immediately:
   ```bash
   sudo systemctl status sysaudit
   ```

3. Monitor logs for 1-2 minutes:
   ```bash
   sudo journalctl -u sysaudit -f
   ```

4. Create a test file in a monitored directory:
   ```bash
   sudo touch /etc/test-sysaudit.txt
   ```

5. Verify the change was detected in logs

6. Stop the service:
   ```bash
   sudo systemctl stop sysaudit
   ```

### Verify No Zombie Processes (Requirement 7.3)

After running for 5+ minutes:

```bash
# Check for zombie processes
ps aux | grep -i defunct | grep sysaudit

# Should return no results
```

### Verify Service Restarts on Failure

1. Find the main process ID:
   ```bash
   systemctl show sysaudit | grep MainPID
   ```

2. Kill the process:
   ```bash
   sudo kill -9 <PID>
   ```

3. Wait 10 seconds and check status:
   ```bash
   sudo systemctl status sysaudit
   ```

4. Service should be running again with a new PID

## Integration with Other Tools

### Monitoring with Prometheus

The service logs to journald, which can be scraped by Prometheus using the systemd exporter.

### Alerting with Alertmanager

Configure webhook_url in config.yaml to send alerts to Alertmanager.

### Log Aggregation

Logs can be forwarded to centralized logging systems:
- Elasticsearch via journald
- Splunk via journald forwarder
- Graylog via syslog

## Uninstallation

To remove the service:

```bash
# Stop and disable the service
sudo systemctl stop sysaudit
sudo systemctl disable sysaudit

# Remove the service file
sudo rm /etc/systemd/system/sysaudit.service

# Reload systemd
sudo systemctl daemon-reload

# Optionally remove data and configuration
sudo rm -rf /var/lib/sysaudit
sudo rm -rf /etc/sysaudit
```

## Requirements Compliance

This systemd service implementation satisfies the following requirements:

- **Requirement 7.1**: Service file enables starting with `systemctl start`
- **Requirement 7.2**: Service runs continuously without crashes via restart policies
- **Requirement 7.3**: Proper process management prevents zombie processes
- **Requirement 7.4**: Status shows "active (running)" when operational

## Additional Resources

- [systemd.service man page](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [systemd.exec man page](https://www.freedesktop.org/software/systemd/man/systemd.exec.html)
- [systemd security hardening](https://www.freedesktop.org/software/systemd/man/systemd.exec.html#Security)
