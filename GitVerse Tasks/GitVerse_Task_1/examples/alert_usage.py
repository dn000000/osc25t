#!/usr/bin/env python3
"""
Example usage of the AlertManager for sending security alerts.

This demonstrates:
1. Basic alert sending for compliance issues
2. Severity-based filtering
3. Custom alerts
4. Webhook integration
"""

import sys
import os
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sysaudit.alert import AlertManager
from sysaudit.models import ComplianceIssue, Config


def example_basic_alert():
    """Example 1: Send a basic high-severity alert"""
    print("=" * 60)
    print("Example 1: Basic High-Severity Alert")
    print("=" * 60)
    
    # Create configuration
    config = Config(
        repo_path='/tmp/sysaudit_demo',
        watch_paths=['/tmp/test'],
        webhook_url=None  # No webhook for this example
    )
    
    # Create alert manager
    alert_manager = AlertManager(config)
    
    # Create a high-severity compliance issue
    issue = ComplianceIssue(
        severity='HIGH',
        rule='world-writable',
        path='/etc/passwd',
        description='Critical system file /etc/passwd is world-writable',
        recommendation='Remove write permissions: chmod o-w /etc/passwd',
        timestamp=datetime.now()
    )
    
    # Send alert (will log to journald/syslog)
    print(f"\nSending HIGH severity alert for: {issue.path}")
    alert_manager.send_alert(issue)
    print("Alert sent successfully!")
    print(f"  Rule: {issue.rule}")
    print(f"  Severity: {issue.severity}")
    print(f"  Description: {issue.description}")


def example_severity_filtering():
    """Example 2: Demonstrate severity-based filtering"""
    print("\n" + "=" * 60)
    print("Example 2: Severity-Based Filtering")
    print("=" * 60)
    
    config = Config(
        repo_path='/tmp/sysaudit_demo',
        watch_paths=['/tmp/test']
    )
    
    alert_manager = AlertManager(config)
    
    # Create issues of different severities
    high_issue = ComplianceIssue(
        severity='HIGH',
        rule='suid-binary',
        path='/usr/bin/suspicious',
        description='Unexpected SUID binary detected',
        recommendation='Review and remove SUID bit if not needed'
    )
    
    medium_issue = ComplianceIssue(
        severity='MEDIUM',
        rule='weak-permissions',
        path='/etc/config.conf',
        description='Configuration file has weak permissions',
        recommendation='Set permissions to 640'
    )
    
    low_issue = ComplianceIssue(
        severity='LOW',
        rule='info',
        path='/home/user/.bashrc',
        description='User configuration file modified',
        recommendation='Review changes'
    )
    
    # Send alerts with HIGH threshold (default)
    print("\nSending alerts with HIGH threshold (default):")
    print("  HIGH issue - should send:", end=" ")
    alert_manager.send_alert(high_issue, min_severity='HIGH')
    print("✓")
    
    print("  MEDIUM issue - should NOT send:", end=" ")
    alert_manager.send_alert(medium_issue, min_severity='HIGH')
    print("✓ (filtered)")
    
    print("  LOW issue - should NOT send:", end=" ")
    alert_manager.send_alert(low_issue, min_severity='HIGH')
    print("✓ (filtered)")
    
    # Send alerts with MEDIUM threshold
    print("\nSending alerts with MEDIUM threshold:")
    print("  HIGH issue - should send:", end=" ")
    alert_manager.send_alert(high_issue, min_severity='MEDIUM')
    print("✓")
    
    print("  MEDIUM issue - should send:", end=" ")
    alert_manager.send_alert(medium_issue, min_severity='MEDIUM')
    print("✓")
    
    print("  LOW issue - should NOT send:", end=" ")
    alert_manager.send_alert(low_issue, min_severity='MEDIUM')
    print("✓ (filtered)")
    
    # Send alerts with LOW threshold (all alerts)
    print("\nSending alerts with LOW threshold (all alerts):")
    print("  HIGH issue - should send:", end=" ")
    alert_manager.send_alert(high_issue, min_severity='LOW')
    print("✓")
    
    print("  MEDIUM issue - should send:", end=" ")
    alert_manager.send_alert(medium_issue, min_severity='LOW')
    print("✓")
    
    print("  LOW issue - should send:", end=" ")
    alert_manager.send_alert(low_issue, min_severity='LOW')
    print("✓")


def example_custom_alert():
    """Example 3: Send custom alerts"""
    print("\n" + "=" * 60)
    print("Example 3: Custom Alerts")
    print("=" * 60)
    
    config = Config(
        repo_path='/tmp/sysaudit_demo',
        watch_paths=['/tmp/test']
    )
    
    alert_manager = AlertManager(config)
    
    # Send custom alert with all parameters
    print("\nSending custom alert with full details:")
    alert_manager.send_custom_alert(
        severity='HIGH',
        title='unauthorized-access',
        description='Multiple failed login attempts detected from suspicious IP',
        path='/var/log/auth.log',
        recommendation='Review logs and consider blocking IP address'
    )
    print("✓ Custom alert sent")
    
    # Send custom alert with minimal parameters
    print("\nSending custom alert with minimal details:")
    alert_manager.send_custom_alert(
        severity='MEDIUM',
        title='disk-space-warning',
        description='Disk space usage above 80% threshold'
    )
    print("✓ Minimal custom alert sent")


def example_webhook_integration():
    """Example 4: Webhook integration"""
    print("\n" + "=" * 60)
    print("Example 4: Webhook Integration")
    print("=" * 60)
    
    # Configure with webhook URL
    config = Config(
        repo_path='/tmp/sysaudit_demo',
        watch_paths=['/tmp/test'],
        webhook_url='https://hooks.example.com/alerts'  # Example webhook
    )
    
    alert_manager = AlertManager(config)
    
    issue = ComplianceIssue(
        severity='HIGH',
        rule='critical-file-modified',
        path='/etc/sudoers',
        description='Critical sudoers file has been modified',
        recommendation='Review changes immediately and verify legitimacy'
    )
    
    print(f"\nSending alert with webhook to: {config.webhook_url}")
    print("(Note: This will fail if the webhook URL is not real)")
    alert_manager.send_alert(issue)
    print("Alert processing completed (check logs for webhook status)")


def example_multiple_alerts():
    """Example 5: Sending multiple alerts in sequence"""
    print("\n" + "=" * 60)
    print("Example 5: Multiple Alerts in Sequence")
    print("=" * 60)
    
    config = Config(
        repo_path='/tmp/sysaudit_demo',
        watch_paths=['/tmp/test']
    )
    
    alert_manager = AlertManager(config)
    
    # Simulate multiple security issues detected
    issues = [
        ComplianceIssue(
            severity='HIGH',
            rule='world-writable',
            path='/etc/shadow',
            description='Password file is world-writable',
            recommendation='Fix permissions immediately: chmod 600 /etc/shadow'
        ),
        ComplianceIssue(
            severity='HIGH',
            rule='suid-binary',
            path='/tmp/suspicious_binary',
            description='SUID binary found in /tmp directory',
            recommendation='Remove file and investigate: rm /tmp/suspicious_binary'
        ),
        ComplianceIssue(
            severity='MEDIUM',
            rule='weak-ssh-config',
            path='/etc/ssh/sshd_config',
            description='SSH configuration allows password authentication',
            recommendation='Disable password auth and use key-based authentication'
        ),
    ]
    
    print(f"\nProcessing {len(issues)} security issues:")
    for i, issue in enumerate(issues, 1):
        print(f"\n  {i}. {issue.rule} ({issue.severity})")
        print(f"     Path: {issue.path}")
        print(f"     Description: {issue.description}")
        alert_manager.send_alert(issue)
        print(f"     ✓ Alert sent")
    
    print(f"\nAll {len(issues)} alerts processed successfully!")


def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print("AlertManager Usage Examples")
    print("=" * 60)
    print("\nThese examples demonstrate the AlertManager functionality.")
    print("Alerts will be logged to journald (Linux) or syslog (Unix).")
    print("On Windows, logging may fall back to standard logging.")
    print()
    
    try:
        example_basic_alert()
        example_severity_filtering()
        example_custom_alert()
        example_webhook_integration()
        example_multiple_alerts()
        
        print("\n" + "=" * 60)
        print("All examples completed successfully!")
        print("=" * 60)
        print("\nNote: Check system logs for actual alert messages:")
        print("  - Linux: journalctl -t sysaudit")
        print("  - Unix: tail -f /var/log/syslog | grep sysaudit")
        print()
        
    except Exception as e:
        print(f"\nError running examples: {e}")
        import traceback
        traceback.print_exc()
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
