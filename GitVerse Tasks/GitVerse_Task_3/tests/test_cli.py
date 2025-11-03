"""
Integration tests for CLI interface.
Tests the command-line interface commands and their interactions with the daemon.
"""

import json
import os
import tempfile
import subprocess
import pytest
from unittest.mock import Mock, patch, MagicMock

from gitproc.cli import CLI, DaemonClient
from gitproc.config import Config


class TestCLIInit:
    """Test the init command."""
    
    def test_init_creates_repository_structure(self):
        """Test that init command creates all necessary directories and files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = os.path.join(tmpdir, "services")
            config_path = os.path.join(tmpdir, "config.json")
            
            # Run init command
            cli = CLI()
            exit_code = cli.execute([
                'init',
                '--repo', repo_path,
                '--config', config_path
            ])
            
            # Verify success
            assert exit_code == 0
            
            # Verify repository directory created
            assert os.path.exists(repo_path)
            assert os.path.isdir(repo_path)
            
            # Verify Git repository initialized
            git_dir = os.path.join(repo_path, '.git')
            assert os.path.exists(git_dir)
            assert os.path.isdir(git_dir)
            
            # Verify config file created
            assert os.path.exists(config_path)
            
            # Verify config contents
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            
            assert config_data['repo_path'] == repo_path
            assert config_data['branch'] == 'main'
            assert 'socket_path' in config_data
            assert 'state_file' in config_data
            assert 'log_dir' in config_data
    
    def test_init_with_existing_git_repo(self):
        """Test that init command handles existing Git repository gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = os.path.join(tmpdir, "services")
            config_path = os.path.join(tmpdir, "config.json")
            
            # Create directory and initialize Git manually
            os.makedirs(repo_path)
            subprocess.run(['git', 'init'], cwd=repo_path, capture_output=True)
            
            # Run init command
            cli = CLI()
            exit_code = cli.execute([
                'init',
                '--repo', repo_path,
                '--config', config_path
            ])
            
            # Should succeed even with existing repo
            assert exit_code == 0
            assert os.path.exists(config_path)
    
    def test_init_creates_necessary_directories(self):
        """Test that init command creates log and state directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo_path = os.path.join(tmpdir, "services")
            config_path = os.path.join(tmpdir, "config.json")
            
            # Run init command
            cli = CLI()
            exit_code = cli.execute([
                'init',
                '--repo', repo_path,
                '--config', config_path
            ])
            
            assert exit_code == 0
            
            # Load config to check directories
            config = Config.load(config_path)
            
            # Verify directories were created
            assert os.path.exists(config.log_dir)
            assert os.path.isdir(config.log_dir)
            
            state_dir = os.path.dirname(config.state_file)
            assert os.path.exists(state_dir)
            assert os.path.isdir(state_dir)


class TestCLIServiceManagement:
    """Test service management commands (start, stop, status) with mocked daemon."""
    
    @patch('gitproc.cli.DaemonClient')
    def test_start_command(self, mock_client_class):
        """Test starting a service via CLI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            
            # Create config
            config = Config(
                repo_path=os.path.join(tmpdir, "services"),
                socket_path=os.path.join(tmpdir, "gitproc.sock")
            )
            config.save(config_path)
            
            # Mock daemon client response
            mock_client = Mock()
            mock_client.send_command.return_value = {
                'success': True,
                'message': 'Service test-service started'
            }
            mock_client_class.return_value = mock_client
            
            # Run start command
            cli = CLI()
            exit_code = cli.execute([
                'start',
                'test-service',
                '--config', config_path
            ])
            
            assert exit_code == 0
            mock_client.send_command.assert_called_once_with({
                'action': 'start',
                'name': 'test-service'
            })
    
    @patch('gitproc.cli.DaemonClient')
    def test_stop_command(self, mock_client_class):
        """Test stopping a service via CLI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            
            # Create config
            config = Config(
                repo_path=os.path.join(tmpdir, "services"),
                socket_path=os.path.join(tmpdir, "gitproc.sock")
            )
            config.save(config_path)
            
            # Mock daemon client response
            mock_client = Mock()
            mock_client.send_command.return_value = {
                'success': True,
                'message': 'Service test-service stopped'
            }
            mock_client_class.return_value = mock_client
            
            # Run stop command
            cli = CLI()
            exit_code = cli.execute([
                'stop',
                'test-service',
                '--config', config_path
            ])
            
            assert exit_code == 0
            mock_client.send_command.assert_called_once_with({
                'action': 'stop',
                'name': 'test-service'
            })
    
    @patch('gitproc.cli.DaemonClient')
    def test_status_command(self, mock_client_class):
        """Test getting service status via CLI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            
            # Create config
            config = Config(
                repo_path=os.path.join(tmpdir, "services"),
                socket_path=os.path.join(tmpdir, "gitproc.sock")
            )
            config.save(config_path)
            
            # Mock daemon client response
            mock_client = Mock()
            mock_client.send_command.return_value = {
                'success': True,
                'state': {
                    'name': 'test-service',
                    'status': 'running',
                    'pid': 12345,
                    'start_time': 1234567890.0,
                    'restart_count': 0,
                    'last_exit_code': None
                }
            }
            mock_client_class.return_value = mock_client
            
            # Run status command
            cli = CLI()
            exit_code = cli.execute([
                'status',
                'test-service',
                '--config', config_path
            ])
            
            assert exit_code == 0
            mock_client.send_command.assert_called_once_with({
                'action': 'status',
                'name': 'test-service'
            })
    
    @patch('gitproc.cli.DaemonClient')
    def test_start_nonexistent_service(self, mock_client_class):
        """Test starting a service that doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            
            # Create config
            config = Config(
                repo_path=os.path.join(tmpdir, "services"),
                socket_path=os.path.join(tmpdir, "gitproc.sock")
            )
            config.save(config_path)
            
            # Mock daemon client error response
            mock_client = Mock()
            mock_client.send_command.return_value = {
                'success': False,
                'error': 'Service nonexistent-service not found'
            }
            mock_client_class.return_value = mock_client
            
            # Run start command
            cli = CLI()
            exit_code = cli.execute([
                'start',
                'nonexistent-service',
                '--config', config_path
            ])
            
            # Should fail
            assert exit_code != 0


class TestCLILogs:
    """Test the logs command with mocked daemon."""
    
    @patch('gitproc.cli.DaemonClient')
    def test_logs_command(self, mock_client_class):
        """Test viewing service logs via CLI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            
            # Create config
            config = Config(
                repo_path=os.path.join(tmpdir, "services"),
                socket_path=os.path.join(tmpdir, "gitproc.sock")
            )
            config.save(config_path)
            
            # Mock daemon client response
            mock_client = Mock()
            mock_client.send_command.return_value = {
                'success': True,
                'logs': 'Test log output\nAnother log line\n'
            }
            mock_client_class.return_value = mock_client
            
            # Run logs command
            cli = CLI()
            exit_code = cli.execute([
                'logs',
                'log-service',
                '--config', config_path
            ])
            
            assert exit_code == 0
            mock_client.send_command.assert_called_once_with({
                'action': 'logs',
                'name': 'log-service',
                'lines': None
            })
    
    @patch('gitproc.cli.DaemonClient')
    def test_logs_with_lines_option(self, mock_client_class):
        """Test logs command with --lines option."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            
            # Create config
            config = Config(
                repo_path=os.path.join(tmpdir, "services"),
                socket_path=os.path.join(tmpdir, "gitproc.sock")
            )
            config.save(config_path)
            
            # Mock daemon client response
            mock_client = Mock()
            mock_client.send_command.return_value = {
                'success': True,
                'logs': 'Last 10 lines of logs\n'
            }
            mock_client_class.return_value = mock_client
            
            # Run logs command with line limit
            cli = CLI()
            exit_code = cli.execute([
                'logs',
                'log-service',
                '--lines', '10',
                '--config', config_path
            ])
            
            assert exit_code == 0
            mock_client.send_command.assert_called_once_with({
                'action': 'logs',
                'name': 'log-service',
                'lines': 10
            })


class TestCLIList:
    """Test the list command with mocked daemon."""
    
    @patch('gitproc.cli.DaemonClient')
    def test_list_command(self, mock_client_class):
        """Test listing all services via CLI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            
            # Create config
            config = Config(
                repo_path=os.path.join(tmpdir, "services"),
                socket_path=os.path.join(tmpdir, "gitproc.sock")
            )
            config.save(config_path)
            
            # Mock daemon client response
            mock_client = Mock()
            mock_client.send_command.return_value = {
                'success': True,
                'services': [
                    {'name': 'service-0', 'status': 'stopped', 'pid': None, 'restart_count': 0},
                    {'name': 'service-1', 'status': 'running', 'pid': 12345, 'restart_count': 0},
                    {'name': 'service-2', 'status': 'stopped', 'pid': None, 'restart_count': 2}
                ]
            }
            mock_client_class.return_value = mock_client
            
            # Run list command
            cli = CLI()
            exit_code = cli.execute([
                'list',
                '--config', config_path
            ])
            
            assert exit_code == 0
            mock_client.send_command.assert_called_once_with({
                'action': 'list'
            })
    
    @patch('gitproc.cli.DaemonClient')
    def test_list_with_no_services(self, mock_client_class):
        """Test list command when no services are registered."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            
            # Create config
            config = Config(
                repo_path=os.path.join(tmpdir, "services"),
                socket_path=os.path.join(tmpdir, "gitproc.sock")
            )
            config.save(config_path)
            
            # Mock daemon client response with empty services
            mock_client = Mock()
            mock_client.send_command.return_value = {
                'success': True,
                'services': []
            }
            mock_client_class.return_value = mock_client
            
            # Run list command
            cli = CLI()
            exit_code = cli.execute([
                'list',
                '--config', config_path
            ])
            
            assert exit_code == 0


class TestCLIRollback:
    """Test the rollback command with mocked daemon."""
    
    @patch('gitproc.cli.DaemonClient')
    def test_rollback_command(self, mock_client_class):
        """Test rolling back to a previous commit via CLI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            
            # Create config
            config = Config(
                repo_path=os.path.join(tmpdir, "services"),
                socket_path=os.path.join(tmpdir, "gitproc.sock")
            )
            config.save(config_path)
            
            # Mock daemon client response
            mock_client = Mock()
            mock_client.send_command.return_value = {
                'success': True,
                'message': 'Rolled back to commit abc123',
                'affected_services': ['rollback-service'],
                'restarted_services': ['rollback-service']
            }
            mock_client_class.return_value = mock_client
            
            # Run rollback command
            cli = CLI()
            exit_code = cli.execute([
                'rollback',
                'abc123',
                '--config', config_path
            ])
            
            assert exit_code == 0
            mock_client.send_command.assert_called_once_with({
                'action': 'rollback',
                'commit': 'abc123'
            })
    
    @patch('gitproc.cli.DaemonClient')
    def test_rollback_invalid_commit(self, mock_client_class):
        """Test rollback with invalid commit hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            
            # Create config
            config = Config(
                repo_path=os.path.join(tmpdir, "services"),
                socket_path=os.path.join(tmpdir, "gitproc.sock")
            )
            config.save(config_path)
            
            # Mock daemon client error response
            mock_client = Mock()
            mock_client.send_command.return_value = {
                'success': False,
                'error': 'Invalid commit hash: invalid_commit_hash'
            }
            mock_client_class.return_value = mock_client
            
            # Run rollback command
            cli = CLI()
            exit_code = cli.execute([
                'rollback',
                'invalid_commit_hash',
                '--config', config_path
            ])
            
            # Should fail
            assert exit_code != 0


class TestCLISync:
    """Test the sync command with mocked daemon."""
    
    @patch('gitproc.cli.DaemonClient')
    def test_sync_command(self, mock_client_class):
        """Test manually triggering Git sync via CLI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            
            # Create config
            config = Config(
                repo_path=os.path.join(tmpdir, "services"),
                socket_path=os.path.join(tmpdir, "gitproc.sock")
            )
            config.save(config_path)
            
            # Mock daemon client response
            mock_client = Mock()
            mock_client.send_command.return_value = {
                'success': True,
                'message': 'Git sync completed'
            }
            mock_client_class.return_value = mock_client
            
            # Run sync command
            cli = CLI()
            exit_code = cli.execute([
                'sync',
                '--config', config_path
            ])
            
            assert exit_code == 0
            mock_client.send_command.assert_called_once_with({
                'action': 'sync'
            })


class TestCLIRestart:
    """Test the restart command with mocked daemon."""
    
    @patch('gitproc.cli.DaemonClient')
    def test_restart_command(self, mock_client_class):
        """Test restarting a service via CLI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "config.json")
            
            # Create config
            config = Config(
                repo_path=os.path.join(tmpdir, "services"),
                socket_path=os.path.join(tmpdir, "gitproc.sock")
            )
            config.save(config_path)
            
            # Mock daemon client response
            mock_client = Mock()
            mock_client.send_command.return_value = {
                'success': True,
                'message': 'Service test-service restarted'
            }
            mock_client_class.return_value = mock_client
            
            # Run restart command
            cli = CLI()
            exit_code = cli.execute([
                'restart',
                'test-service',
                '--config', config_path
            ])
            
            assert exit_code == 0
            mock_client.send_command.assert_called_once_with({
                'action': 'restart',
                'name': 'test-service'
            })
