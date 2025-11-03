# Security Guide

This document describes the security considerations, best practices, and security features of sysaudit.

## Overview

Sysaudit is designed with security as a primary concern. As a system auditing tool that monitors critical files and configurations, it must itself be secure and not introduce vulnerabilities.

## Security Features

### 1. Input Validation

All user inputs are validated to prevent injection attacks:

- **Path Traversal Prevention**: File paths are sanitized to prevent access outside monitored directories
- **Command Injection Prevention**: No shell commands are executed with user-provided input
- **Pattern Validation**: Filter patterns are validated before use
- **Configuration Validation**: All configuration values are validated on load

### 2. File Permission Handling

Sysaudit respects and enforces proper file permissions:

- **Repository Permissions**: Audit repository is created with restrictive permissions (0o755)
- **Config File Permissions**: Configuration files should be readable only by owner (0o600)
- **Sensitive File Detection**: Automatically detects world-writable and SUID/SGID files
- **Permission Preservation**: File metadata is preserved during sync operations

### 3. Privilege Management

Sysaudit follows the principle of least privilege:

- **User-Level Operation**: Most operations can run with regular user privileges
- **Root Only When Needed**: Root privileges only required for monitoring system directories
- **No Privilege Escalation**: Does not attempt to escalate privileges
- **Systemd Hardening**: Service file includes security hardening options

### 4. Data Protection

Audit data is protected from unauthorized access:

- **Repository Security**: Git repository stored with restrictive permissions
- **No Plaintext Secrets**: Does not store passwords or API keys in plaintext
- **GPG Signing**: Optional GPG signing for commit integrity
- **Audit Trail**: All operations are logged for accountability

### 5. Denial of Service Protection

Protections against resource exhaustion:

- **Event Batching**: Limits number of events processed at once
- **Buffer Limits**: Event buffers are bounded to prevent memory exhaustion
- **Pattern Complexity**: Pattern matching is optimized to prevent CPU exhaustion
- **File Size Limits**: Large files are handled gracefully

## Security Best Practices

### Installation Security

1. **Verify Installation Source**
   ```bash
   # Verify package integrity
   sha256sum sysaudit-*.tar.gz
   ```

2. **Install with Minimal Privileges**
   ```bash
   # Install as regular user when possible
   pip install --user sysaudit
   ```

3. **Secure Configuration Directory**
   ```bash
   # Create config directory with restrictive permissions
   sudo mkdir -p /etc/sysaudit
   sudo chmod 755 /etc/sysaudit
   ```

### Configuration Security

1. **Protect Configuration Files**
   ```bash
   # Set restrictive permissions on config files
   sudo chmod 600 /etc/sysaudit/config.yaml
   sudo chown root:root /etc/sysaudit/config.yaml
   ```

2. **Secure Repository Location**
   ```yaml
   repository:
     # Use dedicated directory with restricted access
     path: /var/lib/sysaudit
   ```

3. **Enable GPG Signing** (Optional but Recommended)
   ```yaml
   repository:
     gpg_sign: true
   ```

4. **Restrict Webhook URLs**
   ```yaml
   alerts:
     # Only use HTTPS URLs
     webhook_url: https://secure.example.com/webhook
   ```

### Runtime Security

1. **Run as Dedicated User**
   ```bash
   # Create dedicated user for sysaudit
   sudo useradd -r -s /bin/false sysaudit
   
   # Update service file to run as sysaudit user
   # (for non-system directory monitoring)
   ```

2. **Use Systemd Security Features**
   ```ini
   [Service]
   # Security hardening options
   NoNewPrivileges=true
   PrivateTmp=true
   ProtectSystem=strict
   ProtectHome=true
   ReadWritePaths=/var/lib/sysaudit
   ```

3. **Monitor System Logs**
   ```bash
   # Watch for security events
   journalctl -u sysaudit -f | grep -i "security\|error\|warning"
   ```

4. **Regular Security Audits**
   ```bash
   # Run compliance checks regularly
   sysaudit compliance-report --format json > compliance.json
   ```

### Network Security

1. **Webhook Security**
   - Always use HTTPS for webhook URLs
   - Validate SSL certificates
   - Use authentication tokens
   - Implement rate limiting on webhook endpoint

2. **Firewall Configuration**
   - Sysaudit does not open any network ports
   - Only outbound connections for webhooks (if configured)

### Repository Security

1. **Secure Repository Access**
   ```bash
   # Set restrictive permissions on repository
   sudo chmod 700 /var/lib/sysaudit
   sudo chown root:root /var/lib/sysaudit
   ```

2. **Regular Repository Maintenance**
   ```bash
   # Periodically verify repository integrity
   cd /var/lib/sysaudit
   git fsck --full
   ```

3. **Backup Repository Securely**
   ```bash
   # Backup with encryption
   tar czf - /var/lib/sysaudit | gpg -e -r admin@example.com > backup.tar.gz.gpg
   ```

## Compliance Checks

Sysaudit includes built-in compliance checks for common security issues:

### World-Writable Files

Detects files with world-writable permissions in critical directories:

```bash
sysaudit compliance-report --paths /etc /usr/local/bin
```

**Severity**: HIGH  
**Risk**: Unauthorized modification of system files  
**Remediation**: Remove world-write permission

### SUID/SGID Binaries

Detects unexpected SUID/SGID binaries:

```bash
sysaudit compliance-report --paths /usr/bin /usr/local/bin
```

**Severity**: HIGH  
**Risk**: Privilege escalation  
**Remediation**: Review necessity of SUID/SGID bit

### Weak Permissions

Detects sensitive files with weak permissions:

```bash
sysaudit compliance-report --paths /etc/ssh /etc/pam.d
```

**Severity**: MEDIUM to HIGH  
**Risk**: Unauthorized access to sensitive configuration  
**Remediation**: Set restrictive permissions (0600 or 0640)

## Threat Model

### Threats Mitigated

1. **Unauthorized File Modifications**
   - Detection: Real-time monitoring
   - Response: Immediate commit to audit trail
   - Recovery: Rollback capability

2. **Configuration Drift**
   - Detection: Drift detection against baseline
   - Response: Alerts for critical changes
   - Recovery: Rollback to known-good state

3. **Compliance Violations**
   - Detection: Automated compliance scanning
   - Response: Detailed reports with recommendations
   - Recovery: Remediation guidance

4. **Insider Threats**
   - Detection: Process tracking for file changes
   - Response: Audit trail with attribution
   - Recovery: Rollback and investigation

### Threats Not Mitigated

1. **Kernel-Level Attacks**
   - Sysaudit operates at user-space level
   - Cannot detect kernel rootkits
   - Recommendation: Use additional tools (AIDE, Tripwire)

2. **Real-Time Prevention**
   - Sysaudit is detective, not preventive
   - Cannot block malicious changes in real-time
   - Recommendation: Use mandatory access control (SELinux, AppArmor)

3. **Network-Based Attacks**
   - Does not monitor network traffic
   - Recommendation: Use network monitoring tools

4. **Memory-Based Attacks**
   - Does not monitor process memory
   - Recommendation: Use runtime security tools

## Vulnerability Reporting

If you discover a security vulnerability in sysaudit:

1. **Do Not** open a public issue
2. **Do** email security concerns to: [security contact]
3. **Include**:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested fix (if any)

We will respond within 48 hours and work with you to address the issue.

## Security Checklist

Use this checklist to ensure secure deployment:

- [ ] Configuration files have restrictive permissions (0600)
- [ ] Repository directory has restrictive permissions (0700)
- [ ] Service runs with minimal necessary privileges
- [ ] GPG signing is enabled (if required)
- [ ] Webhook URLs use HTTPS only
- [ ] Blacklist includes sensitive file patterns
- [ ] Regular compliance scans are scheduled
- [ ] System logs are monitored
- [ ] Repository backups are encrypted
- [ ] Security updates are applied promptly

## Security Updates

To stay informed about security updates:

1. Watch the project repository for security advisories
2. Subscribe to security mailing list (if available)
3. Regularly update to the latest version
4. Review changelog for security fixes

## Audit and Compliance

### Logging

All security-relevant events are logged:

- File changes with attribution
- Compliance violations
- Configuration changes
- Error conditions

### Audit Trail

The Git repository provides a complete audit trail:

```bash
# View audit history
cd /var/lib/sysaudit
git log --all --oneline

# View specific file history
git log --follow -- path/to/file

# View changes by time period
git log --since="2024-01-01" --until="2024-01-31"
```

### Compliance Reporting

Generate compliance reports for auditors:

```bash
# Generate comprehensive report
sysaudit compliance-report --format html --output compliance-report.html

# Generate JSON report for automation
sysaudit compliance-report --format json --output compliance-report.json
```

## Security Hardening

### Systemd Service Hardening

Add these options to `sysaudit.service`:

```ini
[Service]
# Prevent privilege escalation
NoNewPrivileges=true

# Isolate from other processes
PrivateTmp=true
PrivateDevices=true

# Restrict filesystem access
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/sysaudit

# Restrict capabilities
CapabilityBoundingSet=CAP_DAC_READ_SEARCH

# Restrict system calls
SystemCallFilter=@system-service
SystemCallErrorNumber=EPERM

# Restrict network access (if webhooks not used)
RestrictAddressFamilies=AF_UNIX
```

### SELinux Policy

If using SELinux, create a custom policy:

```bash
# Generate policy from audit logs
audit2allow -a -M sysaudit

# Install policy
semodule -i sysaudit.pp
```

### AppArmor Profile

If using AppArmor, create a profile:

```
# /etc/apparmor.d/usr.local.bin.sysaudit
#include <tunables/global>

/usr/local/bin/sysaudit {
  #include <abstractions/base>
  #include <abstractions/python>

  /var/lib/sysaudit/** rw,
  /etc/sysaudit/** r,
  
  # Monitored paths (adjust as needed)
  /etc/** r,
  /usr/local/bin/** r,
}
```

## Conclusion

Security is a shared responsibility. While sysaudit is designed with security in mind, proper configuration and deployment practices are essential for maintaining a secure system.

Follow the best practices outlined in this document, regularly review security settings, and stay informed about security updates to ensure your audit system remains secure.
