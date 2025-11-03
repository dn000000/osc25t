"""Alert management system for critical security issues"""

import logging
from typing import Optional
from datetime import datetime

from ..models import ComplianceIssue, Config


logger = logging.getLogger(__name__)


class AlertManager:
    """
    Manages alerts for critical security issues.
    
    Supports:
    - journald logging for system integration
    - Webhook notifications for external systems
    - Severity-based filtering
    """
    
    def __init__(self, config: Config):
        """
        Initialize AlertManager.
        
        Args:
            config: System configuration containing webhook URL and other settings
        """
        self.config = config
        self.webhook_url = config.webhook_url
        
        # Try to import systemd journal, but don't fail if not available
        self._journal_available = False
        try:
            from systemd import journal
            self._journal = journal
            self._journal_available = True
            logger.info("systemd journal support enabled")
        except ImportError:
            logger.warning("systemd journal not available, falling back to syslog")
            self._journal = None
    
    def send_alert(self, issue: ComplianceIssue, min_severity: str = 'HIGH') -> None:
        """
        Send alert for a compliance issue if it meets severity threshold.
        
        Args:
            issue: ComplianceIssue to alert on
            min_severity: Minimum severity level to trigger alert ('HIGH', 'MEDIUM', 'LOW')
                         Default is 'HIGH' - only alert on high severity issues
        
        Requirements: 13.1, 13.2, 13.3, 13.4
        """
        # Filter by severity level
        if not self._should_alert(issue.severity, min_severity):
            logger.debug(f"Skipping alert for {issue.severity} severity issue (threshold: {min_severity})")
            return
        
        logger.info(f"Sending alert for {issue.severity} severity issue: {issue.rule} at {issue.path}")
        
        # Log to journald or syslog
        self._log_to_journal(issue)
        
        # Send webhook if configured
        if self.webhook_url:
            self._send_webhook(issue)
    
    def _should_alert(self, issue_severity: str, min_severity: str) -> bool:
        """
        Check if issue severity meets minimum threshold.
        
        Args:
            issue_severity: Severity of the issue
            min_severity: Minimum severity threshold
            
        Returns:
            True if alert should be sent, False otherwise
        """
        severity_levels = {'LOW': 1, 'MEDIUM': 2, 'HIGH': 3}
        
        issue_level = severity_levels.get(issue_severity, 0)
        min_level = severity_levels.get(min_severity, 3)
        
        return issue_level >= min_level
    
    def _log_to_journal(self, issue: ComplianceIssue) -> None:
        """
        Log alert to systemd journal with appropriate priority.
        
        Falls back to syslog if systemd journal is not available.
        
        Args:
            issue: ComplianceIssue to log
            
        Requirements: 13.1, 13.2
        """
        message = f"SECURITY ALERT: {issue.description}"
        
        if self._journal_available and self._journal:
            # Log to systemd journal
            try:
                # Map severity to journal priority
                priority_map = {
                    'HIGH': self._journal.LOG_CRIT,
                    'MEDIUM': self._journal.LOG_WARNING,
                    'LOW': self._journal.LOG_NOTICE,
                }
                priority = priority_map.get(issue.severity, self._journal.LOG_WARNING)
                
                self._journal.send(
                    message,
                    PRIORITY=priority,
                    SYSLOG_IDENTIFIER='sysaudit',
                    SEVERITY=issue.severity,
                    RULE=issue.rule,
                    PATH=issue.path,
                    RECOMMENDATION=issue.recommendation,
                    TIMESTAMP=issue.timestamp.isoformat(),
                )
                logger.debug(f"Logged to journald with priority {priority}")
            except Exception as e:
                logger.error(f"Failed to log to journald: {e}")
                self._log_to_syslog(message, issue.severity)
        else:
            # Fallback to syslog
            self._log_to_syslog(message, issue.severity)
    
    def _log_to_syslog(self, message: str, severity: str) -> None:
        """
        Fallback logging to syslog.
        
        Args:
            message: Message to log
            severity: Severity level
        """
        try:
            import syslog
            
            # Map severity to syslog priority
            priority_map = {
                'HIGH': syslog.LOG_CRIT,
                'MEDIUM': syslog.LOG_WARNING,
                'LOW': syslog.LOG_NOTICE,
            }
            priority = priority_map.get(severity, syslog.LOG_WARNING)
            
            syslog.openlog('sysaudit', syslog.LOG_PID, syslog.LOG_DAEMON)
            syslog.syslog(priority, message)
            syslog.closelog()
            
            logger.debug(f"Logged to syslog with priority {priority}")
        except Exception as e:
            logger.error(f"Failed to log to syslog: {e}")
    
    def _send_webhook(self, issue: ComplianceIssue) -> None:
        """
        Send webhook notification for alert.
        
        Does not raise exceptions - logs errors instead to avoid
        disrupting the main monitoring flow.
        
        Args:
            issue: ComplianceIssue to send
            
        Requirements: 13.3
        """
        if not self.webhook_url:
            return
        
        try:
            import requests
            
            payload = {
                'severity': issue.severity,
                'rule': issue.rule,
                'path': issue.path,
                'description': issue.description,
                'recommendation': issue.recommendation,
                'timestamp': issue.timestamp.isoformat(),
            }
            
            logger.debug(f"Sending webhook to {self.webhook_url}")
            
            response = requests.post(
                self.webhook_url,
                json=payload,
                timeout=5,
                headers={'Content-Type': 'application/json'}
            )
            
            if response.status_code >= 200 and response.status_code < 300:
                logger.info(f"Webhook sent successfully (status: {response.status_code})")
            else:
                logger.warning(f"Webhook returned non-success status: {response.status_code}")
                
        except ImportError:
            logger.error("requests library not available for webhook notifications")
        except Exception as e:
            # Don't fail on webhook errors - just log them
            logger.error(f"Failed to send webhook: {e}")
    
    def send_custom_alert(
        self,
        severity: str,
        title: str,
        description: str,
        path: Optional[str] = None,
        recommendation: Optional[str] = None
    ) -> None:
        """
        Send a custom alert (not from a compliance issue).
        
        Args:
            severity: Alert severity ('HIGH', 'MEDIUM', 'LOW')
            title: Short title/rule name for the alert
            description: Detailed description
            path: Optional file path related to alert
            recommendation: Optional recommendation text
        """
        # Create a temporary ComplianceIssue for consistency
        issue = ComplianceIssue(
            severity=severity,
            rule=title,
            path=path or 'N/A',
            description=description,
            recommendation=recommendation or 'Review and take appropriate action',
            timestamp=datetime.now()
        )
        
        self.send_alert(issue)
