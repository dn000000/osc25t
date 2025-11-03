"""Tests for AlertManager"""

import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock
from sysaudit.alert import AlertManager
from sysaudit.models import ComplianceIssue, Config


@pytest.fixture
def config():
    """Create test configuration"""
    return Config(
        repo_path='/tmp/test_repo',
        watch_paths=['/tmp/test'],
        webhook_url='http://example.com/webhook'
    )


@pytest.fixture
def config_no_webhook():
    """Create test configuration without webhook"""
    return Config(
        repo_path='/tmp/test_repo',
        watch_paths=['/tmp/test'],
        webhook_url=None
    )


@pytest.fixture
def high_severity_issue():
    """Create a high severity compliance issue"""
    return ComplianceIssue(
        severity='HIGH',
        rule='world-writable',
        path='/etc/passwd',
        description='Critical file is world-writable',
        recommendation='Remove write permissions for others',
        timestamp=datetime.now()
    )


@pytest.fixture
def medium_severity_issue():
    """Create a medium severity compliance issue"""
    return ComplianceIssue(
        severity='MEDIUM',
        rule='weak-permissions',
        path='/etc/config.conf',
        description='Configuration file has weak permissions',
        recommendation='Set permissions to 640',
        timestamp=datetime.now()
    )


@pytest.fixture
def low_severity_issue():
    """Create a low severity compliance issue"""
    return ComplianceIssue(
        severity='LOW',
        rule='info',
        path='/home/user/.bashrc',
        description='User configuration modified',
        recommendation='Review changes',
        timestamp=datetime.now()
    )


class TestAlertManagerInit:
    """Test AlertManager initialization"""
    
    def test_init_with_webhook(self, config):
        """Test initialization with webhook URL"""
        manager = AlertManager(config)
        assert manager.config == config
        assert manager.webhook_url == 'http://example.com/webhook'
    
    def test_init_without_webhook(self, config_no_webhook):
        """Test initialization without webhook URL"""
        manager = AlertManager(config_no_webhook)
        assert manager.config == config_no_webhook
        assert manager.webhook_url is None


class TestSeverityFiltering:
    """Test severity-based alert filtering"""
    
    def test_should_alert_high_with_high_threshold(self, config, high_severity_issue):
        """HIGH severity issue should trigger alert with HIGH threshold"""
        manager = AlertManager(config)
        assert manager._should_alert('HIGH', 'HIGH') is True
    
    def test_should_alert_medium_with_high_threshold(self, config):
        """MEDIUM severity issue should NOT trigger alert with HIGH threshold"""
        manager = AlertManager(config)
        assert manager._should_alert('MEDIUM', 'HIGH') is False
    
    def test_should_alert_low_with_high_threshold(self, config):
        """LOW severity issue should NOT trigger alert with HIGH threshold"""
        manager = AlertManager(config)
        assert manager._should_alert('LOW', 'HIGH') is False
    
    def test_should_alert_high_with_medium_threshold(self, config):
        """HIGH severity issue should trigger alert with MEDIUM threshold"""
        manager = AlertManager(config)
        assert manager._should_alert('HIGH', 'MEDIUM') is True
    
    def test_should_alert_medium_with_medium_threshold(self, config):
        """MEDIUM severity issue should trigger alert with MEDIUM threshold"""
        manager = AlertManager(config)
        assert manager._should_alert('MEDIUM', 'MEDIUM') is True
    
    def test_should_alert_low_with_medium_threshold(self, config):
        """LOW severity issue should NOT trigger alert with MEDIUM threshold"""
        manager = AlertManager(config)
        assert manager._should_alert('LOW', 'MEDIUM') is False
    
    def test_should_alert_all_with_low_threshold(self, config):
        """All severities should trigger alert with LOW threshold"""
        manager = AlertManager(config)
        assert manager._should_alert('HIGH', 'LOW') is True
        assert manager._should_alert('MEDIUM', 'LOW') is True
        assert manager._should_alert('LOW', 'LOW') is True


class TestJournaldLogging:
    """Test journald/syslog logging"""
    
    @patch('sysaudit.alert.manager.logger')
    def test_log_to_journal_when_available(self, mock_logger, config, high_severity_issue):
        """Test logging to journald when available"""
        # Mock systemd journal
        mock_journal = MagicMock()
        mock_journal.LOG_CRIT = 2
        mock_journal.LOG_WARNING = 4
        mock_journal.LOG_NOTICE = 5
        
        manager = AlertManager(config)
        manager._journal_available = True
        manager._journal = mock_journal
        
        manager._log_to_journal(high_severity_issue)
        
        # Verify journal.send was called
        mock_journal.send.assert_called_once()
        call_args = mock_journal.send.call_args
        
        # Check message
        assert 'SECURITY ALERT' in call_args[0][0]
        assert high_severity_issue.description in call_args[0][0]
        
        # Check keyword arguments
        kwargs = call_args[1]
        assert kwargs['PRIORITY'] == mock_journal.LOG_CRIT
        assert kwargs['SYSLOG_IDENTIFIER'] == 'sysaudit'
        assert kwargs['SEVERITY'] == 'HIGH'
        assert kwargs['RULE'] == 'world-writable'
        assert kwargs['PATH'] == '/etc/passwd'
    
    @patch('sysaudit.alert.manager.logger')
    def test_fallback_to_syslog(self, mock_logger, config, high_severity_issue):
        """Test fallback to syslog when journald not available"""
        # Mock syslog module (Unix-only) - need to mock the import
        mock_syslog = MagicMock()
        mock_syslog.LOG_CRIT = 2
        mock_syslog.LOG_WARNING = 4
        mock_syslog.LOG_NOTICE = 5
        mock_syslog.LOG_PID = 1
        mock_syslog.LOG_DAEMON = 3
        
        with patch.dict('sys.modules', {'syslog': mock_syslog}):
            manager = AlertManager(config)
            manager._journal_available = False
            manager._journal = None
            
            manager._log_to_journal(high_severity_issue)
            
            # Verify syslog was called
            mock_syslog.openlog.assert_called_once_with('sysaudit', mock_syslog.LOG_PID, mock_syslog.LOG_DAEMON)
            mock_syslog.syslog.assert_called_once()
            mock_syslog.closelog.assert_called_once()
            
            # Check message
            call_args = mock_syslog.syslog.call_args[0]
            assert 'SECURITY ALERT' in call_args[1]


class TestWebhookNotifications:
    """Test webhook notifications"""
    
    @patch('requests.post')
    def test_send_webhook_success(self, mock_post, config, high_severity_issue):
        """Test successful webhook sending"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        manager = AlertManager(config)
        manager._send_webhook(high_severity_issue)
        
        # Verify webhook was called
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        
        # Check URL
        assert call_args[0][0] == 'http://example.com/webhook'
        
        # Check payload
        payload = call_args[1]['json']
        assert payload['severity'] == 'HIGH'
        assert payload['rule'] == 'world-writable'
        assert payload['path'] == '/etc/passwd'
        assert payload['description'] == 'Critical file is world-writable'
        assert payload['recommendation'] == 'Remove write permissions for others'
        assert 'timestamp' in payload
        
        # Check headers
        assert call_args[1]['headers']['Content-Type'] == 'application/json'
        assert call_args[1]['timeout'] == 5
    
    @patch('requests.post')
    @patch('sysaudit.alert.manager.logger')
    def test_send_webhook_failure_does_not_raise(self, mock_logger, mock_post, 
                                                   config, high_severity_issue):
        """Test that webhook failures don't raise exceptions"""
        mock_post.side_effect = Exception("Network error")
        
        manager = AlertManager(config)
        
        # Should not raise exception
        manager._send_webhook(high_severity_issue)
        
        # Should log error
        mock_logger.error.assert_called()
    
    @patch('sysaudit.alert.manager.logger')
    def test_send_webhook_skipped_when_no_url(self, mock_logger, config_no_webhook, 
                                                high_severity_issue):
        """Test that webhook is skipped when URL not configured"""
        manager = AlertManager(config_no_webhook)
        manager._send_webhook(high_severity_issue)
        
        # Should not attempt to send
        # Just verify no errors occurred


class TestSendAlert:
    """Test main send_alert method"""
    
    @patch.object(AlertManager, '_send_webhook')
    @patch.object(AlertManager, '_log_to_journal')
    def test_send_alert_high_severity(self, mock_log, mock_webhook, config, high_severity_issue):
        """Test sending alert for high severity issue"""
        manager = AlertManager(config)
        manager.send_alert(high_severity_issue, min_severity='HIGH')
        
        # Both logging and webhook should be called
        mock_log.assert_called_once_with(high_severity_issue)
        mock_webhook.assert_called_once_with(high_severity_issue)
    
    @patch.object(AlertManager, '_send_webhook')
    @patch.object(AlertManager, '_log_to_journal')
    def test_send_alert_filtered_by_severity(self, mock_log, mock_webhook, 
                                              config, medium_severity_issue):
        """Test that alerts are filtered by severity threshold"""
        manager = AlertManager(config)
        manager.send_alert(medium_severity_issue, min_severity='HIGH')
        
        # Should not send alert for MEDIUM when threshold is HIGH
        mock_log.assert_not_called()
        mock_webhook.assert_not_called()
    
    @patch.object(AlertManager, '_send_webhook')
    @patch.object(AlertManager, '_log_to_journal')
    def test_send_alert_default_threshold(self, mock_log, mock_webhook, 
                                           config, high_severity_issue):
        """Test that default threshold is HIGH"""
        manager = AlertManager(config)
        manager.send_alert(high_severity_issue)  # No min_severity specified
        
        # Should send alert
        mock_log.assert_called_once()
        mock_webhook.assert_called_once()
    
    @patch.object(AlertManager, '_send_webhook')
    @patch.object(AlertManager, '_log_to_journal')
    def test_send_alert_medium_threshold(self, mock_log, mock_webhook, 
                                          config, medium_severity_issue):
        """Test sending alert with MEDIUM threshold"""
        manager = AlertManager(config)
        manager.send_alert(medium_severity_issue, min_severity='MEDIUM')
        
        # Should send alert for MEDIUM when threshold is MEDIUM
        mock_log.assert_called_once()
        mock_webhook.assert_called_once()


class TestCustomAlert:
    """Test custom alert functionality"""
    
    @patch.object(AlertManager, 'send_alert')
    def test_send_custom_alert(self, mock_send_alert, config):
        """Test sending custom alert"""
        manager = AlertManager(config)
        
        manager.send_custom_alert(
            severity='HIGH',
            title='custom-rule',
            description='Custom security issue detected',
            path='/etc/custom',
            recommendation='Fix the issue'
        )
        
        # Verify send_alert was called
        mock_send_alert.assert_called_once()
        
        # Check the issue that was created
        issue = mock_send_alert.call_args[0][0]
        assert issue.severity == 'HIGH'
        assert issue.rule == 'custom-rule'
        assert issue.path == '/etc/custom'
        assert issue.description == 'Custom security issue detected'
        assert issue.recommendation == 'Fix the issue'
    
    @patch.object(AlertManager, 'send_alert')
    def test_send_custom_alert_minimal(self, mock_send_alert, config):
        """Test sending custom alert with minimal parameters"""
        manager = AlertManager(config)
        
        manager.send_custom_alert(
            severity='MEDIUM',
            title='test-alert',
            description='Test description'
        )
        
        # Verify send_alert was called
        mock_send_alert.assert_called_once()
        
        # Check defaults were applied
        issue = mock_send_alert.call_args[0][0]
        assert issue.path == 'N/A'
        assert 'Review and take appropriate action' in issue.recommendation


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
