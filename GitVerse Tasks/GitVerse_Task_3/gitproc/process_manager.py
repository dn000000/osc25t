"""
Process manager for GitProc.
Spawns, monitors, and controls service processes with isolation.
"""

import os
import sys
import signal
import time
import logging
import shlex
from typing import Optional, Dict, Tuple
from dataclasses import dataclass

# Import pwd only on Unix systems
try:
    import pwd
    HAS_PWD = True
except ImportError:
    HAS_PWD = False

from gitproc.config import Config
from gitproc.resource_controller import ResourceController
from gitproc.parser import UnitFile


@dataclass
class ProcessInfo:
    """Information about a spawned process."""
    pid: int
    service_name: str
    log_file: str


class ProcessManager:
    """
    Manages service processes with isolation and resource control.
    """
    
    def __init__(self, config: Config, resource_controller: Optional[ResourceController] = None):
        """
        Initialize ProcessManager.
        
        Args:
            config: Configuration object
            resource_controller: ResourceController instance (optional)
        """
        self.config = config
        self.resource_controller = resource_controller or ResourceController(config.cgroup_root)
        self.logger = logging.getLogger(__name__)
        self.processes: Dict[int, ProcessInfo] = {}
        
        # Set up signal handler for SIGCHLD
        self._setup_signal_handlers()
    
    def _setup_signal_handlers(self) -> None:
        """
        Set up signal handlers for SIGCHLD to detect process termination.
        """
        # Note: In a real daemon, this would be set up properly
        # For now, we'll handle it in the daemon process
        pass
    
    def is_running(self, pid: int) -> bool:
        """
        Check if a process is running.
        
        Args:
            pid: Process ID to check
            
        Returns:
            True if process exists and is running, False otherwise
        """
        try:
            # Send signal 0 to check if process exists
            # This doesn't actually send a signal, just checks permissions
            os.kill(pid, 0)
            
            # Process exists, but check if it's a zombie
            try:
                with open(f'/proc/{pid}/stat', 'r') as f:
                    stat = f.read()
                    # The state is the 3rd field (after pid and comm)
                    # Z = zombie, X = dead
                    if ') Z ' in stat or ') X ' in stat:
                        return False
            except (FileNotFoundError, IOError):
                # /proc not available or process gone
                pass
            
            return True
        except (OSError, ProcessLookupError):
            return False

    def start_process(self, unit: UnitFile, cgroup_path: Optional[str] = None) -> ProcessInfo:
        """
        Start a process with isolation and resource limits.
        
        Args:
            unit: UnitFile object with service configuration
            cgroup_path: Optional pre-created cgroup path
            
        Returns:
            ProcessInfo object with process details
            
        Raises:
            RuntimeError: If process spawning fails
        """
        # Ensure log directory exists
        os.makedirs(self.config.log_dir, exist_ok=True)
        
        # Create log file path
        log_file = os.path.join(self.config.log_dir, f"{unit.name}.log")
        
        # Parse command
        cmd_parts = shlex.split(unit.exec_start)
        if not cmd_parts:
            raise ValueError("ExecStart command is empty")
        
        self.logger.info(f"Starting process for service {unit.name}: {unit.exec_start}")
        
        # Fork the process
        pid = os.fork()
        
        if pid == 0:  # Child process
            try:
                # Create new PID namespace for isolation
                self._create_pid_namespace()
                
                # Set up environment variables
                self._setup_environment(unit)
                
                # Redirect stdout/stderr to log file
                self._redirect_output(log_file)
                
                # Drop privileges if User is specified
                if unit.user:
                    self._drop_privileges(unit.user)
                
                # Move to cgroup if specified
                if cgroup_path:
                    self._move_to_cgroup(cgroup_path)
                
                # Execute the command
                os.execvp(cmd_parts[0], cmd_parts)
                
            except Exception as e:
                # Log error and exit child process
                sys.stderr.write(f"Failed to start process: {e}\n")
                sys.stderr.flush()
                os._exit(1)  # Use os._exit to avoid exception handling
        
        # Parent process
        self.logger.info(f"Spawned process {pid} for service {unit.name}")
        
        # Store process info
        process_info = ProcessInfo(
            pid=pid,
            service_name=unit.name,
            log_file=log_file
        )
        self.processes[pid] = process_info
        
        return process_info
    
    def _create_pid_namespace(self) -> None:
        """
        Create a new PID namespace for process isolation.
        Handles failures gracefully by logging a warning.
        """
        try:
            # Try to import and use unshare
            # CLONE_NEWPID = 0x20000000
            if hasattr(os, 'unshare'):
                CLONE_NEWPID = 0x20000000
                os.unshare(CLONE_NEWPID)
                self.logger.debug("Created PID namespace for process isolation")
            else:
                # Platform doesn't support unshare (e.g., Windows)
                self.logger.warning(
                    "PID namespace isolation not supported on this platform. "
                    "Continuing without isolation."
                )
        except (OSError, AttributeError) as e:
            # Namespace creation failed (insufficient permissions or not supported)
            self.logger.warning(
                f"Failed to create PID namespace: {e}. "
                "Continuing without isolation."
            )
    
    def _setup_environment(self, unit: UnitFile) -> None:
        """
        Set up environment variables from unit file.
        
        Args:
            unit: UnitFile object with environment configuration
        """
        if unit.environment:
            for key, value in unit.environment.items():
                os.environ[key] = value
                self.logger.debug(f"Set environment variable {key}={value}")
    
    def _redirect_output(self, log_file: str) -> None:
        """
        Redirect stdout and stderr to log file.
        
        Args:
            log_file: Path to log file
        """
        # Open log file
        log_fd = os.open(log_file, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
        
        # Redirect stdout (fd 1) and stderr (fd 2) to log file
        os.dup2(log_fd, 1)
        os.dup2(log_fd, 2)
        
        # Close the original file descriptor
        os.close(log_fd)
    
    def _move_to_cgroup(self, cgroup_path: str) -> None:
        """
        Move current process to cgroup.
        
        Args:
            cgroup_path: Path to cgroup directory
        """
        try:
            pid = os.getpid()
            self.resource_controller.add_process(cgroup_path, pid)
        except Exception as e:
            self.logger.warning(f"Failed to move process to cgroup: {e}")

    def _drop_privileges(self, username: str) -> None:
        """
        Drop privileges to run as specified user.
        
        Args:
            username: Username to run as
            
        Raises:
            RuntimeError: If user doesn't exist or privilege dropping fails
        """
        if not HAS_PWD:
            self.logger.warning(
                f"Privilege dropping not supported on this platform. "
                f"User directive '{username}' will be ignored."
            )
            return
        
        try:
            # Get user information
            user_info = pwd.getpwnam(username)
            uid = user_info.pw_uid
            gid = user_info.pw_gid
            
            # Drop privileges (must set GID before UID)
            os.setgid(gid)
            os.setuid(uid)
            
            self.logger.info(f"Dropped privileges to user {username} (UID={uid}, GID={gid})")
            
        except KeyError:
            raise RuntimeError(f"User '{username}' does not exist")
        except (OSError, PermissionError) as e:
            raise RuntimeError(f"Failed to drop privileges to user '{username}': {e}")

    def spawn_process(self, unit: UnitFile) -> ProcessInfo:
        """
        Spawn a process with full isolation, resource limits, and privilege dropping.
        This is the main entry point for starting services.
        
        Args:
            unit: UnitFile object with service configuration
            
        Returns:
            ProcessInfo object with process details
            
        Raises:
            RuntimeError: If process spawning fails
        """
        # Create cgroup before forking if resource limits are specified
        cgroup_path = None
        if unit.memory_limit is not None or unit.cpu_quota is not None:
            cgroup_path = self.resource_controller.create_cgroup(
                service_name=unit.name,
                memory_limit=unit.memory_limit,
                cpu_quota=unit.cpu_quota
            )
            if cgroup_path:
                self.logger.info(f"Created cgroup for {unit.name} at {cgroup_path}")
        
        # Start the process with the cgroup path
        return self.start_process(unit, cgroup_path)

    def stop_process(self, pid: int, timeout: int = 5) -> bool:
        """
        Stop a process gracefully with fallback to forced termination.
        
        Args:
            pid: Process ID to stop
            timeout: Seconds to wait for graceful shutdown before forcing (default: 5)
            
        Returns:
            True if process was stopped successfully, False otherwise
        """
        if not self.is_running(pid):
            self.logger.info(f"Process {pid} is not running")
            return True
        
        try:
            # Send SIGTERM for graceful shutdown
            self.logger.info(f"Sending SIGTERM to process {pid}")
            os.kill(pid, signal.SIGTERM)
            
            # Wait for process to terminate
            start_time = time.time()
            while time.time() - start_time < timeout:
                if not self.is_running(pid):
                    self.logger.info(f"Process {pid} terminated gracefully")
                    # Try to reap the zombie process
                    try:
                        os.waitpid(pid, os.WNOHANG)
                    except (OSError, ChildProcessError):
                        pass
                    self._cleanup_process(pid)
                    return True
                time.sleep(0.1)
            
            # Process didn't terminate, send SIGKILL
            self.logger.warning(
                f"Process {pid} did not terminate after {timeout} seconds, "
                "sending SIGKILL"
            )
            os.kill(pid, signal.SIGKILL)
            
            # Wait a bit for SIGKILL to take effect and reap the process
            time.sleep(0.5)
            
            # Try to reap the zombie process
            try:
                os.waitpid(pid, os.WNOHANG)
            except (OSError, ChildProcessError):
                pass
            
            if not self.is_running(pid):
                self.logger.info(f"Process {pid} terminated forcefully")
                self._cleanup_process(pid)
                return True
            else:
                self.logger.error(f"Failed to terminate process {pid}")
                return False
                
        except (OSError, ProcessLookupError) as e:
            self.logger.error(f"Error stopping process {pid}: {e}")
            self._cleanup_process(pid)
            return False
    
    def _cleanup_process(self, pid: int) -> None:
        """
        Clean up process information after termination.
        
        Args:
            pid: Process ID to clean up
        """
        if pid in self.processes:
            process_info = self.processes[pid]
            
            # Remove cgroup if it exists
            # Note: We need to track cgroup paths per process for proper cleanup
            # For now, we'll attempt to remove based on service name
            try:
                cgroup_path = os.path.join(
                    self.resource_controller.cgroup_root,
                    "gitproc",
                    process_info.service_name
                )
                if os.path.exists(cgroup_path):
                    self.resource_controller.remove_cgroup(cgroup_path)
            except Exception as e:
                self.logger.warning(f"Failed to remove cgroup: {e}")
            
            # Remove from process tracking
            del self.processes[pid]

    def get_logs(self, service_name: str, lines: Optional[int] = None) -> str:
        """
        Read log file contents for a service.
        
        Args:
            service_name: Name of the service
            lines: Optional number of lines to return (from end of file)
            
        Returns:
            Log file contents as string
            
        Raises:
            FileNotFoundError: If log file doesn't exist
        """
        log_file = os.path.join(self.config.log_dir, f"{service_name}.log")
        
        if not os.path.exists(log_file):
            raise FileNotFoundError(f"Log file not found for service {service_name}")
        
        with open(log_file, 'r') as f:
            if lines is None:
                # Return entire file
                return f.read()
            else:
                # Return last N lines
                all_lines = f.readlines()
                return ''.join(all_lines[-lines:])
    
    def get_log_file_path(self, service_name: str) -> str:
        """
        Get the log file path for a service.
        
        Args:
            service_name: Name of the service
            
        Returns:
            Path to log file
        """
        return os.path.join(self.config.log_dir, f"{service_name}.log")
