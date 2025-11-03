"""
Integration tests for HealthMonitor class.
Tests HTTP health checks and service restart on failure.
"""

import time
import threading
import pytest
from http.server import HTTPServer, BaseHTTPRequestHandler
from gitproc.health_monitor import HealthMonitor
from gitproc.state_manager import StateManager
import tempfile
import os


class MockHTTPHandler(BaseHTTPRequestHandler):
    """Mock HTTP handler for health check testing."""
    
    # Class variable to control response status
    response_status = 200
    
    def do_GET(self):
        """Handle GET requests."""
        self.send_response(self.response_status)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(b'OK')
    
    def log_message(self, format, *args):
        """Suppress log messages."""
        pass


class MockHTTPServer:
    """Mock HTTP server for testing health checks."""
    
    def __init__(self, port=0):
        """Initialize mock server."""
        self.server = HTTPServer(('127.0.0.1', port), MockHTTPHandler)
        self.server.timeout = 0.5
        self.port = self.server.server_address[1]
        self.thread = None
    
    def start(self):
        """Start the server in a background thread."""
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        time.sleep(0.2)  # Give server time to start
    
    def stop(self):
        """Stop the server."""
        self.server.shutdown()
        if self.thread:
            self.thread.join(timeout=2)
        self.server.server_close()
    
    def set_status(self, status_code):
        """Set the response status code."""
        MockHTTPHandler.response_status = status_code
    
    def get_url(self):
        """Get the server URL."""
        return f"http://127.0.0.1:{self.port}"


@pytest.fixture
def state_manager():
    """Create a StateManager instance for testing."""
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        state_file = f.name
    
    try:
        manager = StateManager(state_file)
        yield manager
    finally:
        if os.path.exists(state_file):
            os.unlink(state_file)


@pytest.fixture
def mock_server():
    """Create a mock HTTP server for testing."""
    server = MockHTTPServer()
    server.start()
    yield server
    server.stop()


class TestHTTPHealthCheck:
    """Tests for HTTP health check functionality."""
    
    def test_http_health_check_success(self, state_manager, mock_server):
        """Test HTTP health check with mock server returning 200."""
        restart_called = []
        
        def restart_callback(service_name):
            restart_called.append(service_name)
        
        # Create health monitor
        monitor = HealthMonitor(state_manager, restart_callback)
        
        # Set server to return 200
        mock_server.set_status(200)
        
        # Perform health check
        result = monitor.check_http(mock_server.get_url(), timeout=5)
        
        # Verify health check passed
        assert result is True
        
        # Verify restart was not called
        assert len(restart_called) == 0
    
    def test_http_health_check_failure(self, state_manager, mock_server):
        """Test HTTP health check with mock server returning 500."""
        restart_called = []
        
        def restart_callback(service_name):
            restart_called.append(service_name)
        
        # Create health monitor
        monitor = HealthMonitor(state_manager, restart_callback)
        
        # Set server to return 500
        mock_server.set_status(500)
        
        # Perform health check
        result = monitor.check_http(mock_server.get_url(), timeout=5)
        
        # Verify health check failed
        assert result is False
        
        # Verify restart was not called (check_http doesn't trigger restart)
        assert len(restart_called) == 0
    
    def test_http_health_check_timeout(self, state_manager):
        """Test HTTP health check with unreachable server."""
        restart_called = []
        
        def restart_callback(service_name):
            restart_called.append(service_name)
        
        # Create health monitor
        monitor = HealthMonitor(state_manager, restart_callback)
        
        # Use unreachable URL
        result = monitor.check_http("http://localhost:9999", timeout=1)
        
        # Verify health check failed
        assert result is False


class TestServiceRestartOnFailure:
    """Tests for service restart on health check failure."""
    
    def test_service_restart_on_health_check_failure(self, state_manager, mock_server):
        """Test service restart on health check failure."""
        restart_called = []
        restart_event = threading.Event()
        
        def restart_callback(service_name):
            restart_called.append(service_name)
            restart_event.set()
        
        # Register a service
        state_manager.register_service("test-service")
        state_manager.update_state("test-service", status="running", pid=12345)
        
        # Create health monitor
        monitor = HealthMonitor(state_manager, restart_callback)
        
        # Register health check with interval of 0 to ensure it runs immediately
        monitor.register_check("test-service", mock_server.get_url(), interval=0)
        
        # Set server to return 500 (failure)
        mock_server.set_status(500)
        
        # Run checks manually
        monitor.run_checks()
        
        # Wait for restart callback to be called
        assert restart_event.wait(timeout=5), "Restart callback was not called"
        
        # Verify restart was called
        assert "test-service" in restart_called
        assert len(restart_called) == 1
    
    def test_multiple_failures_trigger_multiple_restarts(self, state_manager, mock_server):
        """Test that multiple health check failures trigger restarts."""
        restart_called = []
        restart_events = [threading.Event() for _ in range(3)]
        
        def restart_callback(service_name):
            restart_called.append(service_name)
            if len(restart_called) <= len(restart_events):
                restart_events[len(restart_called) - 1].set()
        
        # Register a service
        state_manager.register_service("test-service")
        state_manager.update_state("test-service", status="running", pid=12345)
        
        # Create health monitor
        monitor = HealthMonitor(state_manager, restart_callback)
        
        # Register health check with interval of 0
        monitor.register_check("test-service", mock_server.get_url(), interval=0)
        
        # Set server to return 500 (failure)
        mock_server.set_status(500)
        
        # Run checks multiple times
        for i in range(3):
            monitor.run_checks()
            assert restart_events[i].wait(timeout=5), f"Restart {i+1} was not called"
        
        # Verify restart was called multiple times
        assert len(restart_called) >= 3
        assert all(name == "test-service" for name in restart_called)
    
    def test_health_check_recovery(self, state_manager, mock_server):
        """Test that health check recovery is logged."""
        restart_called = []
        restart_event1 = threading.Event()
        restart_event2 = threading.Event()
        
        def restart_callback(service_name):
            restart_called.append(service_name)
            if len(restart_called) == 1:
                restart_event1.set()
            elif len(restart_called) == 2:
                restart_event2.set()
        
        # Register a service
        state_manager.register_service("test-service")
        state_manager.update_state("test-service", status="running", pid=12345)
        
        # Create health monitor
        monitor = HealthMonitor(state_manager, restart_callback)
        
        # Register health check with interval of 0
        monitor.register_check("test-service", mock_server.get_url(), interval=0)
        
        # First check: failure
        mock_server.set_status(500)
        monitor.run_checks()
        assert restart_event1.wait(timeout=5), "First restart was not called"
        
        # Verify restart was called
        assert len(restart_called) == 1
        
        # Second check: success (recovery)
        mock_server.set_status(200)
        monitor.run_checks()
        time.sleep(1.5)
        
        # Verify no additional restart
        assert len(restart_called) == 1
        
        # Third check: failure again
        mock_server.set_status(500)
        monitor.run_checks()
        assert restart_event2.wait(timeout=5), "Second restart was not called"
        
        # Verify restart was called again
        assert len(restart_called) == 2


class TestHealthMonitorLifecycle:
    """Tests for health monitor lifecycle operations."""
    
    def test_register_and_unregister_check(self, state_manager):
        """Test registering and unregistering health checks."""
        def restart_callback(service_name):
            pass
        
        monitor = HealthMonitor(state_manager, restart_callback)
        
        # Register a check
        monitor.register_check("test-service", "http://localhost:8080", interval=30)
        
        # Verify check is registered
        assert "test-service" in monitor.checks
        assert monitor.checks["test-service"].url == "http://localhost:8080"
        assert monitor.checks["test-service"].interval == 30
        
        # Unregister the check
        monitor.unregister_check("test-service")
        
        # Verify check is removed
        assert "test-service" not in monitor.checks
    
    def test_start_and_stop_monitor(self, state_manager, mock_server):
        """Test starting and stopping the health monitor."""
        restart_called = []
        restart_event = threading.Event()
        
        def restart_callback(service_name):
            restart_called.append(service_name)
            restart_event.set()
        
        # Register a service
        state_manager.register_service("test-service")
        state_manager.update_state("test-service", status="running", pid=12345)
        
        # Create health monitor
        monitor = HealthMonitor(state_manager, restart_callback)
        
        # Register health check with short interval
        monitor.register_check("test-service", mock_server.get_url(), interval=1)
        
        # Set server to return 500
        mock_server.set_status(500)
        
        # Start monitor
        monitor.start()
        
        # Wait for restart to be called
        assert restart_event.wait(timeout=5), "Restart was not called by monitor"
        
        # Stop monitor
        monitor.stop()
        
        # Verify restart was called at least once
        assert len(restart_called) >= 1
        assert "test-service" in restart_called
    
    def test_check_interval_respected(self, state_manager, mock_server):
        """Test that health check interval is respected."""
        restart_called = []
        restart_event1 = threading.Event()
        restart_event2 = threading.Event()
        
        def restart_callback(service_name):
            restart_called.append(service_name)
            if len(restart_called) == 1:
                restart_event1.set()
            elif len(restart_called) == 2:
                restart_event2.set()
        
        # Register a service
        state_manager.register_service("test-service")
        state_manager.update_state("test-service", status="running", pid=12345)
        
        # Create health monitor
        monitor = HealthMonitor(state_manager, restart_callback)
        
        # Register health check with 1-second interval
        monitor.register_check("test-service", mock_server.get_url(), interval=1)
        
        # Set server to return 500
        mock_server.set_status(500)
        
        # Manually set last_check_time to past so first check runs immediately
        monitor.checks["test-service"].last_check_time = time.time() - 2
        
        # Run checks immediately (should execute)
        monitor.run_checks()
        assert restart_event1.wait(timeout=5), "First restart was not called"
        initial_count = len(restart_called)
        assert initial_count >= 1
        
        # Run checks again immediately (should NOT execute due to interval)
        monitor.run_checks()
        time.sleep(1.0)
        assert len(restart_called) == initial_count
        
        # Wait for interval to pass
        time.sleep(1.5)
        
        # Run checks again (should execute now)
        monitor.run_checks()
        assert restart_event2.wait(timeout=5), "Second restart was not called"
        assert len(restart_called) > initial_count
