"""
Test helpers and fixtures for GitProc test suite.
Provides utilities for creating test unit files, repositories, and mock servers.
"""

import os
import time
import tempfile
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, List, Dict
import git


class TestHelper:
    """Helper class for creating test fixtures and utilities."""
    
    @staticmethod
    def create_test_unit(
        repo_path: str,
        name: str,
        exec_start: str = "/bin/sleep 30",
        restart: str = "no",
        user: Optional[str] = None,
        environment: Optional[Dict[str, str]] = None,
        memory_limit: Optional[str] = None,
        cpu_quota: Optional[str] = None,
        health_check_url: Optional[str] = None,
        health_check_interval: Optional[int] = None,
        after: Optional[List[str]] = None
    ) -> str:
        """
        Create a test unit file in the specified repository.
        
        Args:
            repo_path: Path to Git repository
            name: Service name (without .service extension)
            exec_start: Command to execute
            restart: Restart policy (always, on-failure, no)
            user: User to run as
            environment: Environment variables dict
            memory_limit: Memory limit (e.g., "100M")
            cpu_quota: CPU quota (e.g., "50%")
            health_check_url: HTTP health check URL
            health_check_interval: Health check interval in seconds
            after: List of service dependencies
            
        Returns:
            Path to created unit file
        """
        unit_path = os.path.join(repo_path, f"{name}.service")
        
        content = "[Service]\n"
        content += f"ExecStart={exec_start}\n"
        
        if restart != "no":
            content += f"Restart={restart}\n"
        
        if user:
            content += f"User={user}\n"
        
        if environment:
            for key, value in environment.items():
                content += f"Environment={key}={value}\n"
        
        if memory_limit:
            content += f"MemoryLimit={memory_limit}\n"
        
        if cpu_quota:
            content += f"CPUQuota={cpu_quota}\n"
        
        if health_check_url:
            content += f"HealthCheckURL={health_check_url}\n"
        
        if health_check_interval:
            content += f"HealthCheckInterval={health_check_interval}\n"
        
        if after:
            for dep in after:
                content += f"After={dep}\n"
        
        with open(unit_path, 'w') as f:
            f.write(content)
        
        return unit_path
    
    @staticmethod
    def wait_for_process(pid: int, timeout: int = 5, expect_running: bool = True) -> bool:
        """
        Wait for a process to reach the expected state.
        
        Args:
            pid: Process ID to check
            timeout: Maximum time to wait in seconds
            expect_running: True to wait for process to be running, False to wait for it to stop
            
        Returns:
            True if process reached expected state, False if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Check if process exists
                os.kill(pid, 0)
                is_running = True
            except (OSError, ProcessLookupError):
                is_running = False
            
            if is_running == expect_running:
                return True
            
            time.sleep(0.1)
        
        return False
    
    @staticmethod
    def create_test_repo(base_path: Optional[str] = None) -> str:
        """
        Create a temporary Git repository for testing.
        
        Args:
            base_path: Optional base path for repository. If None, uses temp directory.
            
        Returns:
            Path to created repository
        """
        if base_path is None:
            repo_path = tempfile.mkdtemp(prefix="gitproc_test_repo_")
        else:
            repo_path = base_path
            os.makedirs(repo_path, exist_ok=True)
        
        # Initialize Git repository
        repo = git.Repo.init(repo_path)
        
        # Configure Git user for commits
        with repo.config_writer() as config:
            config.set_value("user", "name", "Test User")
            config.set_value("user", "email", "test@example.com")
        
        # Create initial commit
        readme_path = os.path.join(repo_path, "README.md")
        with open(readme_path, 'w') as f:
            f.write("# GitProc Test Repository\n")
        
        repo.index.add(["README.md"])
        repo.index.commit("Initial commit")
        
        return repo_path
    
    @staticmethod
    def create_test_script(
        repo_path: str,
        name: str,
        content: str,
        executable: bool = True
    ) -> str:
        """
        Create a test script file.
        
        Args:
            repo_path: Path to repository
            name: Script filename
            content: Script content
            executable: Whether to make script executable
            
        Returns:
            Path to created script
        """
        script_path = os.path.join(repo_path, name)
        
        with open(script_path, 'w') as f:
            f.write(content)
        
        if executable:
            os.chmod(script_path, 0o755)
        
        return script_path
    
    @staticmethod
    def commit_files(repo_path: str, files: List[str], message: str = "Test commit"):
        """
        Commit files to the Git repository.
        
        Args:
            repo_path: Path to repository
            files: List of filenames to commit
            message: Commit message
        """
        repo = git.Repo(repo_path)
        repo.index.add(files)
        repo.index.commit(message)
    
    @staticmethod
    def get_current_commit(repo_path: str) -> str:
        """
        Get the current commit hash.
        
        Args:
            repo_path: Path to repository
            
        Returns:
            Current commit hash
        """
        repo = git.Repo(repo_path)
        return repo.head.commit.hexsha


class MockHTTPHealthCheckHandler(BaseHTTPRequestHandler):
    """HTTP request handler for mock health check server."""
    
    # Class variable to control response status
    response_status = 200
    response_body = "OK"
    
    def do_GET(self):
        """Handle GET requests."""
        self.send_response(self.response_status)
        self.send_header('Content-type', 'text/plain')
        self.end_headers()
        self.wfile.write(self.response_body.encode('utf-8'))
    
    def log_message(self, format, *args):
        """Suppress log messages."""
        pass


class MockHTTPServer:
    """Mock HTTP server for health check testing."""
    
    def __init__(self, port: int = 0):
        """
        Initialize mock HTTP server.
        
        Args:
            port: Port to listen on (0 for random available port)
        """
        self.server = HTTPServer(('localhost', port), MockHTTPHealthCheckHandler)
        self.port = self.server.server_port
        self.thread = None
        self.running = False
    
    def start(self):
        """Start the server in a background thread."""
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        time.sleep(0.1)  # Give server time to start
    
    def _run(self):
        """Run the server loop."""
        while self.running:
            self.server.handle_request()
    
    def stop(self):
        """Stop the server."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=1)
        self.server.server_close()
    
    def set_response(self, status: int = 200, body: str = "OK"):
        """
        Set the response status and body for subsequent requests.
        
        Args:
            status: HTTP status code
            body: Response body
        """
        MockHTTPHealthCheckHandler.response_status = status
        MockHTTPHealthCheckHandler.response_body = body
    
    def get_url(self) -> str:
        """
        Get the server URL.
        
        Returns:
            Server URL (e.g., "http://localhost:8080")
        """
        return f"http://localhost:{self.port}"


class ProcessHelper:
    """Helper for managing test processes."""
    
    @staticmethod
    def kill_process_tree(pid: int):
        """
        Kill a process and all its children.
        
        Args:
            pid: Process ID to kill
        """
        try:
            # Try to kill the process
            os.kill(pid, 9)  # SIGKILL
        except (OSError, ProcessLookupError):
            pass
    
    @staticmethod
    def is_process_running(pid: int) -> bool:
        """
        Check if a process is running.
        
        Args:
            pid: Process ID to check
            
        Returns:
            True if process is running, False otherwise
        """
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False
    
    @staticmethod
    def wait_for_log_content(
        log_path: str,
        expected_content: str,
        timeout: int = 5
    ) -> bool:
        """
        Wait for specific content to appear in a log file.
        
        Args:
            log_path: Path to log file
            expected_content: Content to wait for
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if content found, False if timeout
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if os.path.exists(log_path):
                with open(log_path, 'r') as f:
                    content = f.read()
                    if expected_content in content:
                        return True
            
            time.sleep(0.1)
        
        return False
