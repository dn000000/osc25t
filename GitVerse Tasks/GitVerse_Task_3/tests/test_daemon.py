"""
Integration tests for Daemon class.
Tests daemon startup, service management, automatic restart, Git sync, and shutdown.
"""

import os
import sys
import time
import json
import socket
import tempfile
import threading
import pytest
from pathlib import Path

from gitproc.config import Config
from gitproc.daemon import Daemon
from gitproc.git_integration import GitIntegration


# Skip tests on Windows that require Unix-specific features
SKIP_ON_WINDOWS = pytest.mark.skipif(
    sys.platform == "win32",
    reason="Test requires Unix-specific features"
)


@pytest.fixture
def test_config():
    """Create a test configuration with temporary directories."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config = Config(
            repo_path=os.path.join(tmpdir, "services"),
            branch="main",
            socket_path=os.path.join(tmpdir, "gitproc.sock"),
            state_file=os.path.join(tmpdir, "state.json"),
            log_dir=os.path.join(tmpdir, "logs"),
            cgroup_root=os.path.join(tmpdir, "cgroup")
        )
        config.ensure_directories()
        
        # Initialize Git repository
        git_integration = GitIntegration(config.repo_path, config.branch)
        git_integration.init_repo()
        
        yield config


@pytest.fixture
def daemon_instance(test_config):
    """Create a daemon instance for testing."""
    daemon = Daemon(test_config)
    yield daemon
    
    # Cleanup: ensure daemon is stopped
    if daemon.running:
        daemon.running = False
        if daemon.server_socket:
            try:
                daemon.server_socket.close()
            except:
                pass


def create_test_unit_file(repo_path: str, name: str, exec_start: str, **kwargs) -> str:
    """
    Helper to create a test unit file.
    
    Args:
        repo_path: Path to Git repository
        name: Service name (without .service extension)
        exec_start: Command to execute
        **kwargs: Additional unit file directives
        
    Returns:
        Path to created unit file
    """
    unit_path = os.path.join(repo_path, f"{name}.service")
    
    content = "[Service]\n"
    content += f"ExecStart={exec_start}\n"
    
    if 'restart' in kwargs:
        content += f"Restart={kwargs['restart']}\n"
    if 'user' in kwargs:
        content += f"User={kwargs['user']}\n"
    if 'health_check_url' in kwargs:
        content += f"HealthCheckURL={kwargs['health_check_url']}\n"
    if 'health_check_interval' in kwargs:
        content += f"HealthCheckInterval={kwargs['health_check_interval']}\n"
    if 'after' in kwargs:
        for dep in kwargs['after']:
            content += f"After={dep}\n"
    
    with open(unit_path, 'w') as f:
        f.write(content)
    
    return unit_path


def send_daemon_command(socket_path: str, command: dict, timeout: float = 5.0) -> dict:
    """
    Send a command to the daemon via Unix socket.
    
    Args:
        socket_path: Path to Unix socket
        command: Command dictionary
        timeout: Socket timeout in seconds
        
    Returns:
        Response dictionary
    """
    client_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    client_socket.settimeout(timeout)
    
    try:
        client_socket.connect(socket_path)
        
        # Send command
        command_json = json.dumps(command)
        client_socket.sendall(command_json.encode('utf-8'))
        
        # Receive response
        response_data = b""
        while True:
            chunk = client_socket.recv(4096)
            if not chunk:
                break
            response_data += chunk
            try:
                response = json.loads(response_data.decode('utf-8'))
                return response
            except json.JSONDecodeError:
                continue
        
        return json.loads(response_data.decode('utf-8'))
    finally:
        client_socket.close()


class TestDaemonStartupAndInitialization:
    """Tests for daemon startup and initialization."""
    
    @SKIP_ON_WINDOWS
    def test_daemon_initialization(self, daemon_instance, test_config):
        """Test that daemon initializes all components correctly."""
        assert daemon_instance.config == test_config
        assert daemon_instance.state_manager is not None
        assert daemon_instance.process_manager is not None
        assert daemon_instance.git_integration is not None
        assert daemon_instance.health_monitor is not None
        assert daemon_instance.dependency_resolver is not None
        assert daemon_instance.running is False
    
    @SKIP_ON_WINDOWS
    def test_daemon_startup_loads_unit_files(self, test_config):
        """Test that daemon loads unit files on startup."""
        # Create test unit files
        create_test_unit_file(test_config.repo_path, "test-app", "/bin/sleep 10")
        create_test_unit_file(test_config.repo_path, "test-web", "/bin/sleep 10")
        
        # Commit the files
        git_integration = GitIntegration(test_config.repo_path, test_config.branch)
        git_integration.repo.index.add(["test-app.service", "test-web.service"])
        git_integration.repo.index.commit("Add test services")
        
        # Create daemon and start in thread
        daemon = Daemon(test_config)
        
        # Run daemon in background thread
        daemon_thread = threading.Thread(target=daemon.run, daemon=True)
        daemon_thread.start()
        
        try:
            # Wait for daemon to start
            time.sleep(2)
            
            # Verify unit files were loaded
            assert "test-app" in daemon.unit_files
            assert "test-web" in daemon.unit_files
            
            # Verify services were registered
            assert daemon.state_manager.get_state("test-app") is not None
            assert daemon.state_manager.get_state("test-web") is not None
            
        finally:
            daemon.running = False
            time.sleep(0.5)
    
    @SKIP_ON_WINDOWS
    def test_daemon_creates_unix_socket(self, test_config):
        """Test that daemon creates Unix socket for CLI communication."""
        daemon = Daemon(test_config)
        
        # Run daemon in background thread
        daemon_thread = threading.Thread(target=daemon.run, daemon=True)
        daemon_thread.start()
        
        try:
            # Wait for daemon to start
            time.sleep(2)
            
            # Verify socket exists
            assert os.path.exists(test_config.socket_path)
            
            # Verify we can connect to it
            test_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            test_socket.connect(test_config.socket_path)
            test_socket.close()
            
        finally:
            daemon.running = False
            time.sleep(0.5)


class TestServiceManagement:
    """Tests for service start and stop via daemon."""
    
    @SKIP_ON_WINDOWS
    def test_start_service_via_daemon(self, test_config):
        """Test starting a service through daemon command."""
        # Create test unit file
        create_test_unit_file(test_config.repo_path, "test-service", "/bin/sleep 30")
        
        # Commit the file
        git_integration = GitIntegration(test_config.repo_path, test_config.branch)
        git_integration.repo.index.add(["test-service.service"])
        git_integration.repo.index.commit("Add test service")
        
        # Start daemon
        daemon = Daemon(test_config)
        daemon_thread = threading.Thread(target=daemon.run, daemon=True)
        daemon_thread.start()
        
        try:
            # Wait for daemon to start
            time.sleep(2)
            
            # Send start command
            response = send_daemon_command(
                test_config.socket_path,
                {"action": "start", "name": "test-service"}
            )
            
            assert response["success"] is True
            
            # Verify service is running
            time.sleep(1)
            state = daemon.state_manager.get_state("test-service")
            assert state is not None
            assert state.status == "running"
            assert state.pid is not None
            assert state.pid > 0
            
        finally:
            daemon.running = False
            time.sleep(0.5)
    
    @SKIP_ON_WINDOWS
    def test_stop_service_via_daemon(self, test_config):
        """Test stopping a service through daemon command."""
        # Create test unit file
        create_test_unit_file(test_config.repo_path, "test-service", "/bin/sleep 30")
        
        # Commit the file
        git_integration = GitIntegration(test_config.repo_path, test_config.branch)
        git_integration.repo.index.add(["test-service.service"])
        git_integration.repo.index.commit("Add test service")
        
        # Start daemon
        daemon = Daemon(test_config)
        daemon_thread = threading.Thread(target=daemon.run, daemon=True)
        daemon_thread.start()
        
        try:
            # Wait for daemon to start
            time.sleep(2)
            
            # Start the service
            response = send_daemon_command(
                test_config.socket_path,
                {"action": "start", "name": "test-service"}
            )
            assert response["success"] is True
            time.sleep(1)
            
            # Stop the service
            response = send_daemon_command(
                test_config.socket_path,
                {"action": "stop", "name": "test-service"}
            )
            
            assert response["success"] is True
            
            # Verify service is stopped
            time.sleep(1)
            state = daemon.state_manager.get_state("test-service")
            assert state is not None
            assert state.status == "stopped"
            assert state.pid is None
            
        finally:
            daemon.running = False
            time.sleep(0.5)
    
    @SKIP_ON_WINDOWS
    def test_get_service_status_via_daemon(self, test_config):
        """Test getting service status through daemon command."""
        # Create test unit file
        create_test_unit_file(test_config.repo_path, "test-service", "/bin/sleep 30")
        
        # Commit the file
        git_integration = GitIntegration(test_config.repo_path, test_config.branch)
        git_integration.repo.index.add(["test-service.service"])
        git_integration.repo.index.commit("Add test service")
        
        # Start daemon
        daemon = Daemon(test_config)
        daemon_thread = threading.Thread(target=daemon.run, daemon=True)
        daemon_thread.start()
        
        try:
            # Wait for daemon to start
            time.sleep(2)
            
            # Start the service
            send_daemon_command(
                test_config.socket_path,
                {"action": "start", "name": "test-service"}
            )
            time.sleep(1)
            
            # Get status
            response = send_daemon_command(
                test_config.socket_path,
                {"action": "status", "name": "test-service"}
            )
            
            assert response["success"] is True
            assert "state" in response
            assert response["state"]["name"] == "test-service"
            assert response["state"]["status"] == "running"
            assert response["state"]["pid"] is not None
            
        finally:
            daemon.running = False
            time.sleep(0.5)
    
    @SKIP_ON_WINDOWS
    def test_list_services_via_daemon(self, test_config):
        """Test listing all services through daemon command."""
        # Create multiple test unit files
        create_test_unit_file(test_config.repo_path, "service1", "/bin/sleep 30")
        create_test_unit_file(test_config.repo_path, "service2", "/bin/sleep 30")
        
        # Commit the files
        git_integration = GitIntegration(test_config.repo_path, test_config.branch)
        git_integration.repo.index.add(["service1.service", "service2.service"])
        git_integration.repo.index.commit("Add test services")
        
        # Start daemon
        daemon = Daemon(test_config)
        daemon_thread = threading.Thread(target=daemon.run, daemon=True)
        daemon_thread.start()
        
        try:
            # Wait for daemon to start
            time.sleep(2)
            
            # List services
            response = send_daemon_command(
                test_config.socket_path,
                {"action": "list"}
            )
            
            assert response["success"] is True
            assert "services" in response
            assert len(response["services"]) == 2
            
            service_names = [s["name"] for s in response["services"]]
            assert "service1" in service_names
            assert "service2" in service_names
            
        finally:
            daemon.running = False
            time.sleep(0.5)


class TestAutomaticRestart:
    """Tests for automatic process restart on crash."""
    
    @SKIP_ON_WINDOWS
    def test_automatic_restart_on_crash(self, test_config):
        """Test that service restarts automatically when it crashes."""
        # Create a script that exits immediately
        script_path = os.path.join(test_config.repo_path, "crash_script.sh")
        with open(script_path, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("echo 'Starting...'\n")
            f.write("sleep 1\n")
            f.write("echo 'Exiting...'\n")
            f.write("exit 1\n")
        os.chmod(script_path, 0o755)
        
        # Create unit file with Restart=always
        create_test_unit_file(
            test_config.repo_path,
            "crash-service",
            script_path,
            restart="always"
        )
        
        # Commit the files
        git_integration = GitIntegration(test_config.repo_path, test_config.branch)
        git_integration.repo.index.add(["crash-service.service", "crash_script.sh"])
        git_integration.repo.index.commit("Add crash service")
        
        # Start daemon
        daemon = Daemon(test_config)
        daemon_thread = threading.Thread(target=daemon.run, daemon=True)
        daemon_thread.start()
        
        try:
            # Wait for daemon to start
            time.sleep(2)
            
            # Start the service
            response = send_daemon_command(
                test_config.socket_path,
                {"action": "start", "name": "crash-service"}
            )
            assert response["success"] is True
            
            # Get initial PID
            time.sleep(0.5)
            initial_state = daemon.state_manager.get_state("crash-service")
            initial_pid = initial_state.pid
            
            # Wait for process to crash and restart
            # The script sleeps 1s then exits, monitor checks every 0.2s, restart takes ~0.5s
            time.sleep(4)
            
            # Verify service was restarted
            new_state = daemon.state_manager.get_state("crash-service")
            assert new_state.status == "running"
            assert new_state.restart_count > 0, f"Expected restart_count > 0, got {new_state.restart_count}. PID: {new_state.pid}, initial PID: {initial_pid}"
            assert new_state.pid != initial_pid  # New PID after restart
            
        finally:
            daemon.running = False
            time.sleep(0.5)
    
    @SKIP_ON_WINDOWS
    def test_no_restart_when_restart_no(self, test_config):
        """Test that service does not restart when Restart=no."""
        # Create a script that exits immediately
        script_path = os.path.join(test_config.repo_path, "exit_script.sh")
        with open(script_path, 'w') as f:
            f.write("#!/bin/bash\n")
            f.write("echo 'Exiting...'\n")
            f.write("exit 0\n")
        os.chmod(script_path, 0o755)
        
        # Create unit file with Restart=no
        create_test_unit_file(
            test_config.repo_path,
            "exit-service",
            script_path,
            restart="no"
        )
        
        # Commit the files
        git_integration = GitIntegration(test_config.repo_path, test_config.branch)
        git_integration.repo.index.add(["exit-service.service", "exit_script.sh"])
        git_integration.repo.index.commit("Add exit service")
        
        # Start daemon
        daemon = Daemon(test_config)
        daemon_thread = threading.Thread(target=daemon.run, daemon=True)
        daemon_thread.start()
        
        try:
            # Wait for daemon to start
            time.sleep(2)
            
            # Start the service
            response = send_daemon_command(
                test_config.socket_path,
                {"action": "start", "name": "exit-service"}
            )
            assert response["success"] is True
            
            # Wait for process to exit
            # Give more time for the process to exit and be detected
            time.sleep(3)
            
            # Verify service is stopped and not restarted
            state = daemon.state_manager.get_state("exit-service")
            assert state.status == "stopped", f"Expected status 'stopped', got '{state.status}'"
            assert state.restart_count == 0, f"Expected restart_count 0, got {state.restart_count}"
            assert state.pid is None, f"Expected pid None, got {state.pid}"
            
        finally:
            daemon.running = False
            time.sleep(0.5)


class TestGitSync:
    """Tests for Git synchronization triggering service restart."""
    
    @SKIP_ON_WINDOWS
    def test_git_sync_restarts_modified_service(self, test_config):
        """Test that modifying a unit file triggers service restart."""
        # Create initial unit file
        unit_path = create_test_unit_file(
            test_config.repo_path,
            "sync-service",
            "/bin/sleep 30"
        )
        
        # Commit the file
        git_integration = GitIntegration(test_config.repo_path, test_config.branch)
        git_integration.repo.index.add(["sync-service.service"])
        git_integration.repo.index.commit("Add sync service")
        
        # Start daemon
        daemon = Daemon(test_config)
        daemon_thread = threading.Thread(target=daemon.run, daemon=True)
        daemon_thread.start()
        
        try:
            # Wait for daemon to start
            time.sleep(2)
            
            # Start the service
            response = send_daemon_command(
                test_config.socket_path,
                {"action": "start", "name": "sync-service"}
            )
            assert response["success"] is True
            time.sleep(1)
            
            # Get initial PID
            initial_state = daemon.state_manager.get_state("sync-service")
            initial_pid = initial_state.pid
            
            # Modify the unit file
            with open(unit_path, 'w') as f:
                f.write("[Service]\n")
                f.write("ExecStart=/bin/sleep 60\n")  # Changed command
            
            # Commit the change
            git_integration.repo.index.add(["sync-service.service"])
            git_integration.repo.index.commit("Update sync service")
            
            # Trigger manual sync
            response = send_daemon_command(
                test_config.socket_path,
                {"action": "sync"}
            )
            assert response["success"] is True
            
            # Wait for restart
            time.sleep(2)
            
            # Verify service was restarted with new PID
            new_state = daemon.state_manager.get_state("sync-service")
            assert new_state.status == "running"
            assert new_state.pid != initial_pid
            
        finally:
            daemon.running = False
            time.sleep(0.5)
    
    @SKIP_ON_WINDOWS
    def test_git_sync_adds_new_service(self, test_config):
        """Test that adding a new unit file makes it available."""
        # Start daemon with no services
        daemon = Daemon(test_config)
        daemon_thread = threading.Thread(target=daemon.run, daemon=True)
        daemon_thread.start()
        
        try:
            # Wait for daemon to start
            time.sleep(2)
            
            # Verify no services initially
            response = send_daemon_command(
                test_config.socket_path,
                {"action": "list"}
            )
            initial_count = len(response["services"])
            
            # Add new unit file
            create_test_unit_file(
                test_config.repo_path,
                "new-service",
                "/bin/sleep 30"
            )
            
            # Commit the file
            git_integration = GitIntegration(test_config.repo_path, test_config.branch)
            git_integration.repo.index.add(["new-service.service"])
            git_integration.repo.index.commit("Add new service")
            
            # Trigger sync
            response = send_daemon_command(
                test_config.socket_path,
                {"action": "sync"}
            )
            assert response["success"] is True
            
            # Wait for sync to complete
            time.sleep(1)
            
            # Verify new service is available
            response = send_daemon_command(
                test_config.socket_path,
                {"action": "list"}
            )
            assert len(response["services"]) == initial_count + 1
            
            service_names = [s["name"] for s in response["services"]]
            assert "new-service" in service_names
            
        finally:
            daemon.running = False
            time.sleep(0.5)
    
    @SKIP_ON_WINDOWS
    def test_git_sync_removes_deleted_service(self, test_config):
        """Test that deleting a unit file stops and removes the service."""
        # Create unit file
        unit_path = create_test_unit_file(
            test_config.repo_path,
            "delete-service",
            "/bin/sleep 30"
        )
        
        # Commit the file
        git_integration = GitIntegration(test_config.repo_path, test_config.branch)
        git_integration.repo.index.add(["delete-service.service"])
        git_integration.repo.index.commit("Add delete service")
        
        # Start daemon
        daemon = Daemon(test_config)
        daemon_thread = threading.Thread(target=daemon.run, daemon=True)
        daemon_thread.start()
        
        try:
            # Wait for daemon to start
            time.sleep(2)
            
            # Start the service
            response = send_daemon_command(
                test_config.socket_path,
                {"action": "start", "name": "delete-service"}
            )
            assert response["success"] is True
            time.sleep(1)
            
            # Verify service is running
            state = daemon.state_manager.get_state("delete-service")
            assert state.status == "running"
            
            # Delete the unit file
            os.unlink(unit_path)
            git_integration.repo.index.remove(["delete-service.service"])
            git_integration.repo.index.commit("Remove delete service")
            
            # Trigger sync
            response = send_daemon_command(
                test_config.socket_path,
                {"action": "sync"}
            )
            assert response["success"] is True
            
            # Wait for sync to complete
            time.sleep(2)
            
            # Verify service is stopped
            state = daemon.state_manager.get_state("delete-service")
            assert state.status == "stopped"
            
            # Verify service is no longer in unit files
            assert "delete-service" not in daemon.unit_files
            
        finally:
            daemon.running = False
            time.sleep(0.5)


class TestDaemonShutdown:
    """Tests for daemon graceful shutdown."""
    
    @SKIP_ON_WINDOWS
    def test_daemon_shutdown_stops_all_services(self, test_config):
        """Test that daemon shutdown stops all running services."""
        # Create test unit files
        create_test_unit_file(test_config.repo_path, "service1", "/bin/sleep 60")
        create_test_unit_file(test_config.repo_path, "service2", "/bin/sleep 60")
        
        # Commit the files
        git_integration = GitIntegration(test_config.repo_path, test_config.branch)
        git_integration.repo.index.add(["service1.service", "service2.service"])
        git_integration.repo.index.commit("Add test services")
        
        # Start daemon
        daemon = Daemon(test_config)
        daemon_thread = threading.Thread(target=daemon.run, daemon=True)
        daemon_thread.start()
        
        try:
            # Wait for daemon to start
            time.sleep(2)
            
            # Start both services
            send_daemon_command(
                test_config.socket_path,
                {"action": "start", "name": "service1"}
            )
            send_daemon_command(
                test_config.socket_path,
                {"action": "start", "name": "service2"}
            )
            time.sleep(1)
            
            # Verify both services are running
            state1 = daemon.state_manager.get_state("service1")
            state2 = daemon.state_manager.get_state("service2")
            assert state1.status == "running"
            assert state2.status == "running"
            pid1 = state1.pid
            pid2 = state2.pid
            
            # Trigger shutdown
            daemon.running = False
            # Wait longer for shutdown to complete (process monitor, health monitor, git monitor threads)
            time.sleep(3)
            
            # Verify both services are stopped
            state1 = daemon.state_manager.get_state("service1")
            state2 = daemon.state_manager.get_state("service2")
            assert state1.status == "stopped", f"Service1 status: {state1.status}"
            assert state2.status == "stopped", f"Service2 status: {state2.status}"
            
            # Verify processes are no longer running
            assert not daemon.process_manager.is_running(pid1), f"Process {pid1} still running"
            assert not daemon.process_manager.is_running(pid2), f"Process {pid2} still running"
            
        finally:
            daemon.running = False
            time.sleep(0.5)
    
    @SKIP_ON_WINDOWS
    def test_daemon_shutdown_saves_state(self, test_config):
        """Test that daemon saves state on shutdown."""
        # Create test unit file
        create_test_unit_file(test_config.repo_path, "test-service", "/bin/sleep 30")
        
        # Commit the file
        git_integration = GitIntegration(test_config.repo_path, test_config.branch)
        git_integration.repo.index.add(["test-service.service"])
        git_integration.repo.index.commit("Add test service")
        
        # Start daemon
        daemon = Daemon(test_config)
        daemon_thread = threading.Thread(target=daemon.run, daemon=True)
        daemon_thread.start()
        
        try:
            # Wait for daemon to start
            time.sleep(2)
            
            # Start the service
            send_daemon_command(
                test_config.socket_path,
                {"action": "start", "name": "test-service"}
            )
            time.sleep(1)
            
            # Trigger shutdown
            daemon.running = False
            time.sleep(2)
            
            # Verify state file exists
            assert os.path.exists(test_config.state_file)
            
            # Load state file and verify contents
            with open(test_config.state_file, 'r') as f:
                state_data = json.load(f)
            
            assert "services" in state_data
            assert "test-service" in state_data["services"]
            
        finally:
            daemon.running = False
            time.sleep(0.5)
    
    @SKIP_ON_WINDOWS
    def test_daemon_shutdown_removes_socket(self, test_config):
        """Test that daemon removes Unix socket on shutdown."""
        # Start daemon
        daemon = Daemon(test_config)
        daemon_thread = threading.Thread(target=daemon.run, daemon=True)
        daemon_thread.start()
        
        try:
            # Wait for daemon to start
            time.sleep(2)
            
            # Verify socket exists
            assert os.path.exists(test_config.socket_path)
            
            # Trigger shutdown
            daemon.running = False
            time.sleep(2)
            
            # Verify socket is removed
            assert not os.path.exists(test_config.socket_path)
            
        finally:
            daemon.running = False
            time.sleep(0.5)
