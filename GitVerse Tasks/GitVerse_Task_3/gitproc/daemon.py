"""
Daemon process for GitProc.
Manages services, monitors Git changes, and handles health checks.
"""

import os
import sys
import json
import signal
import socket
import logging
import threading
import time
from typing import Dict, Optional, Any
from pathlib import Path

from gitproc.config import Config
from gitproc.state_manager import StateManager, ServiceState
from gitproc.process_manager import ProcessManager
from gitproc.git_integration import GitIntegration
from gitproc.health_monitor import HealthMonitor
from gitproc.dependency_resolver import DependencyResolver
from gitproc.parser import UnitFileParser


class Daemon:
    """
    Main daemon process that manages all services and monitors for changes.
    """
    
    def __init__(self, config: Config):
        """
        Initialize the daemon with all necessary components.
        
        Args:
            config: Configuration object
        """
        self.config = config
        self.logger = self._setup_logging()
        
        # Initialize core components
        self.state_manager = StateManager(config.state_file)
        self.process_manager = ProcessManager(config)
        self.git_integration = GitIntegration(config.repo_path, config.branch)
        self.dependency_resolver = DependencyResolver()
        
        # Initialize health monitor with restart callback
        self.health_monitor = HealthMonitor(
            state_manager=self.state_manager,
            restart_callback=self._restart_service_internal
        )
        
        # Unix socket server for CLI communication
        self.socket_path = config.socket_path
        self.server_socket: Optional[socket.socket] = None
        
        # Control flags
        self.running = False
        self.git_monitor_thread: Optional[threading.Thread] = None
        self.process_monitor_thread: Optional[threading.Thread] = None
        self.state_save_thread: Optional[threading.Thread] = None
        
        # Track unit files
        self.unit_files: Dict[str, str] = {}  # service_name -> file_path
        
        self.logger.info("Daemon initialized")
    
    def _setup_logging(self) -> logging.Logger:
        """
        Set up logging for the daemon.
        
        Returns:
            Logger instance
        """
        # Ensure log directory exists
        os.makedirs(self.config.log_dir, exist_ok=True)
        
        # Configure logging
        log_file = os.path.join(self.config.log_dir, "daemon.log")
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        return logging.getLogger(__name__)
    
    def _setup_unix_socket(self) -> None:
        """
        Set up Unix socket server for CLI communication.
        """
        # Remove existing socket file if it exists
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)
        
        # Ensure directory exists
        socket_dir = os.path.dirname(self.socket_path)
        if socket_dir:
            os.makedirs(socket_dir, exist_ok=True)
        
        # Create Unix socket
        self.server_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server_socket.bind(self.socket_path)
        self.server_socket.listen(5)
        
        # Set socket to non-blocking mode for graceful shutdown
        self.server_socket.settimeout(1.0)
        
        self.logger.info(f"Unix socket server listening on {self.socket_path}")
    
    def _restart_service_internal(self, service_name: str) -> None:
        """
        Internal method to restart a service (used by health monitor).
        
        Args:
            service_name: Name of service to restart
        """
        try:
            self.logger.info(f"Restarting service {service_name}")
            self._stop_service(service_name)
            time.sleep(0.5)  # Brief pause between stop and start
            self._start_service(service_name)
        except Exception as e:
            self.logger.error(f"Failed to restart service {service_name}: {e}")

    def run(self) -> None:
        """
        Main daemon event loop.
        
        Loads state, registers services, sets up monitoring, and handles CLI requests.
        """
        try:
            self.logger.info("Starting GitProc daemon")
            
            # Ensure necessary directories exist
            self.config.ensure_directories()
            
            # Load state from disk
            self.logger.info("Loading state from disk")
            self.state_manager.load_state()
            
            # Load all unit files from Git repository
            self.logger.info("Loading unit files from Git repository")
            self._load_unit_files()
            
            # Register all services with StateManager
            self.logger.info("Registering services")
            for service_name in self.unit_files.keys():
                self.state_manager.register_service(service_name)
            
            # Set up signal handlers
            self.logger.info("Setting up signal handlers")
            self._setup_signal_handlers()
            
            # Set up Unix socket server
            self.logger.info("Setting up Unix socket server")
            self._setup_unix_socket()
            
            # Start Git monitoring thread
            self.logger.info("Starting Git monitoring thread")
            self.running = True
            self.git_monitor_thread = threading.Thread(
                target=self._git_monitor_loop,
                daemon=True
            )
            self.git_monitor_thread.start()
            
            # Start health check thread
            self.logger.info("Starting health monitor")
            self.health_monitor.start()
            
            # Start process monitoring thread (fallback for when SIGCHLD doesn't work)
            self.logger.info("Starting process monitoring thread")
            self.process_monitor_thread = threading.Thread(
                target=self._process_monitor_loop,
                daemon=True
            )
            self.process_monitor_thread.start()
            
            # Start periodic state save thread
            self.logger.info("Starting periodic state save thread")
            self.state_save_thread = threading.Thread(
                target=self._periodic_state_save_loop,
                daemon=True
            )
            self.state_save_thread.start()
            
            # Enter main event loop to handle CLI requests
            self.logger.info("Entering main event loop")
            self._main_loop()
            
        except KeyboardInterrupt:
            self.logger.info("Received keyboard interrupt")
        except Exception as e:
            self.logger.error(f"Fatal error in daemon: {e}", exc_info=True)
        finally:
            self._shutdown()
    
    def _load_unit_files(self) -> None:
        """
        Load all unit files from the Git repository.
        """
        unit_file_paths = self.git_integration.get_unit_files()
        
        for rel_path in unit_file_paths:
            full_path = os.path.join(self.config.repo_path, rel_path)
            
            try:
                unit = UnitFileParser.parse(full_path)
                
                # Validate unit file
                errors = UnitFileParser.validate(unit)
                if errors:
                    self.logger.error(
                        f"Unit file {rel_path} has validation errors: {errors}"
                    )
                    continue
                
                # Store unit file path
                self.unit_files[unit.name] = full_path
                self.logger.info(f"Loaded unit file: {unit.name}")
                
            except Exception as e:
                self.logger.error(f"Failed to parse unit file {rel_path}: {e}")
    
    def _setup_signal_handlers(self) -> None:
        """
        Set up signal handlers for SIGTERM and SIGCHLD.
        """
        try:
            signal.signal(signal.SIGTERM, self._handle_sigterm)
            signal.signal(signal.SIGCHLD, self._handle_sigchld)
            
            # On Windows, SIGCHLD doesn't exist
            if hasattr(signal, 'SIGINT'):
                signal.signal(signal.SIGINT, self._handle_sigterm)
        except ValueError as e:
            # Signal handlers can only be set in the main thread
            # In test environments, this is expected
            self.logger.warning(f"Could not set up signal handlers: {e}. This is expected in test environments.")
    
    def _handle_sigterm(self, signum, frame) -> None:
        """
        Handle SIGTERM signal for graceful shutdown.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        self.logger.info("Received SIGTERM, initiating graceful shutdown")
        self.running = False
    
    def _main_loop(self) -> None:
        """
        Main event loop that handles CLI requests via Unix socket.
        """
        while self.running:
            try:
                # Accept connections with timeout
                try:
                    client_socket, _ = self.server_socket.accept()
                except socket.timeout:
                    # Timeout allows us to check self.running flag
                    continue
                
                # Handle client request in a separate thread
                client_thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket,),
                    daemon=True
                )
                client_thread.start()
                
            except Exception as e:
                if self.running:
                    self.logger.error(f"Error in main loop: {e}")
    
    def _git_monitor_loop(self) -> None:
        """
        Git monitoring loop that runs in a separate thread.
        Checks for Git changes periodically with adaptive polling.
        """
        self.logger.info("Git monitor thread started")
        
        # Adaptive polling: start with 10s, increase to 30s if no changes
        poll_interval = 10
        max_poll_interval = 30
        no_change_count = 0
        
        while self.running:
            try:
                if self.git_integration.has_changes():
                    self.logger.info("Git changes detected")
                    self._handle_git_changes()
                    # Reset to fast polling after changes
                    poll_interval = 10
                    no_change_count = 0
                else:
                    # Gradually increase polling interval if no changes
                    no_change_count += 1
                    if no_change_count >= 3 and poll_interval < max_poll_interval:
                        poll_interval = min(poll_interval + 5, max_poll_interval)
                        self.logger.debug(f"Increased Git polling interval to {poll_interval}s")
            except Exception as e:
                self.logger.error(f"Error in Git monitor: {e}")
            
            # Sleep with adaptive interval
            time.sleep(poll_interval)
        
        self.logger.info("Git monitor thread stopped")
    
    def _periodic_state_save_loop(self) -> None:
        """
        Periodic state save loop that runs in a separate thread.
        Saves state at regular intervals to reduce I/O overhead.
        """
        self.logger.info("Periodic state save thread started")
        
        while self.running:
            try:
                # Save state if dirty (batched write with time throttling)
                self.state_manager.save_state(force=False)
            except Exception as e:
                self.logger.error(f"Error in periodic state save: {e}")
            
            # Sleep for 5 seconds before next save attempt
            time.sleep(5)
        
        self.logger.info("Periodic state save thread stopped")
    
    def _process_monitor_loop(self) -> None:
        """
        Process monitoring loop that runs in a separate thread.
        Checks for terminated processes and handles restarts.
        This is a fallback for when SIGCHLD signal handlers don't work (e.g., in threads).
        """
        self.logger.info("Process monitor thread started")
        check_count = 0
        
        while self.running:
            try:
                check_count += 1
                # Check all running services
                running_services = [(name, state) for name, state in self.state_manager.services.items() 
                                   if state.status == "running" and state.pid is not None]
                
                if check_count % 25 == 0:  # Log every 5 seconds (25 * 0.2s)
                    self.logger.debug(f"Process monitor check #{check_count}, monitoring {len(running_services)} services")
                
                for service_name, state in running_services:
                    # Check if process is still running
                    is_running = self.process_manager.is_running(state.pid)
                    
                    if not is_running:
                        # Double-check the state hasn't changed (race condition protection)
                        current_state = self.state_manager.get_state(service_name)
                        if current_state.status != "running" or current_state.pid != state.pid:
                            # State changed, skip this one
                            self.logger.debug(f"State changed for {service_name}, skipping")
                            continue
                        
                        self.logger.info(f"Detected terminated process {state.pid} for service {service_name}")
                        
                        # Try to reap the zombie process
                        exit_code = -1
                        try:
                            pid, status = os.waitpid(state.pid, os.WNOHANG)
                            if pid > 0:
                                # Extract exit code
                                if os.WIFEXITED(status):
                                    exit_code = os.WEXITSTATUS(status)
                                elif os.WIFSIGNALED(status):
                                    exit_code = -os.WTERMSIG(status)
                                else:
                                    exit_code = -1
                                self.logger.info(f"Reaped process {pid} with exit code {exit_code}")
                            else:
                                self.logger.debug(f"Waitpid returned 0 for PID {state.pid}")
                        except (OSError, ChildProcessError) as e:
                            self.logger.debug(f"Could not reap process {state.pid}: {e}")
                            # Process already reaped or doesn't exist
                            pass
                        
                        # Handle the termination
                        self._handle_process_termination(service_name, state.pid, exit_code)
            except Exception as e:
                self.logger.error(f"Error in process monitor: {e}", exc_info=True)
            
            # Check more frequently (every 0.2 seconds) for faster detection
            time.sleep(0.2)
        
        self.logger.info(f"Process monitor thread stopped after {check_count} checks")

    def _handle_sigchld(self, signum, frame) -> None:
        """
        Handle SIGCHLD signal when a child process terminates.
        
        Reaps zombie processes and handles restart policies.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        # Reap all terminated child processes
        while True:
            try:
                # Use WNOHANG to avoid blocking
                pid, status = os.waitpid(-1, os.WNOHANG)
                
                if pid == 0:
                    # No more terminated children
                    break
                
                # Extract exit code
                if os.WIFEXITED(status):
                    exit_code = os.WEXITSTATUS(status)
                elif os.WIFSIGNALED(status):
                    exit_code = -os.WTERMSIG(status)
                else:
                    exit_code = -1
                
                self.logger.info(
                    f"Process {pid} terminated with exit code {exit_code}"
                )
                
                # Find which service this process belongs to
                service_name = self._find_service_by_pid(pid)
                
                if service_name:
                    self._handle_process_termination(service_name, pid, exit_code)
                else:
                    self.logger.warning(
                        f"Terminated process {pid} does not belong to any known service"
                    )
                
            except ChildProcessError:
                # No more child processes
                break
            except Exception as e:
                self.logger.error(f"Error handling SIGCHLD: {e}")
                break
    
    def _find_service_by_pid(self, pid: int) -> Optional[str]:
        """
        Find the service name associated with a PID.
        
        Args:
            pid: Process ID
            
        Returns:
            Service name or None if not found
        """
        for service_name, state in self.state_manager.services.items():
            if state.pid == pid:
                return service_name
        return None
    
    def _handle_process_termination(
        self, service_name: str, pid: int, exit_code: int
    ) -> None:
        """
        Handle process termination and apply restart policy.
        
        Args:
            service_name: Name of the service
            pid: Process ID that terminated
            exit_code: Exit code of the process
        """
        self.logger.info(
            f"Service {service_name} (PID {pid}) terminated with exit code {exit_code}"
        )
        
        # Get current state
        state = self.state_manager.get_state(service_name)
        if not state:
            return
        
        # Update state
        self.state_manager.update_state(
            service_name,
            status="stopped",
            pid=None,
            last_exit_code=exit_code
        )
        
        # Check restart policy
        unit_file_path = self.unit_files.get(service_name)
        if not unit_file_path:
            self.logger.error(f"Unit file not found for service {service_name}")
            return
        
        try:
            unit = UnitFileParser.parse(unit_file_path)
            
            # Determine if we should restart
            should_restart = False
            
            if unit.restart == "always":
                should_restart = True
                self.logger.info(
                    f"Service {service_name} has Restart=always, will restart"
                )
            elif unit.restart == "on-failure" and exit_code != 0:
                should_restart = True
                self.logger.info(
                    f"Service {service_name} has Restart=on-failure and failed, will restart"
                )
            
            if should_restart:
                # Increment restart count
                new_restart_count = state.restart_count + 1
                self.state_manager.update_state(
                    service_name,
                    restart_count=new_restart_count
                )
                
                self.logger.info(
                    f"Restarting service {service_name} (restart count: {new_restart_count})"
                )
                
                # Restart the service
                self._start_service(service_name)
            else:
                self.logger.info(
                    f"Service {service_name} will not be restarted (Restart={unit.restart})"
                )
            
            # Mark state as dirty (will be saved by periodic thread)
            # No need to call save_state() here - batched writes handle it
            
        except Exception as e:
            self.logger.error(
                f"Error handling termination for service {service_name}: {e}"
            )

    def _handle_git_changes(self) -> None:
        """
        Handle Git repository changes.
        
        Detects modified, added, and deleted unit files and takes appropriate actions.
        """
        try:
            # Get changed files
            modified, added, deleted = self.git_integration.get_changed_files()
            
            self.logger.info(
                f"Git changes: {len(modified)} modified, "
                f"{len(added)} added, {len(deleted)} deleted"
            )
            
            # Handle deleted unit files
            for file_path in deleted:
                service_name = self._extract_service_name(file_path)
                if service_name in self.unit_files:
                    self.logger.info(f"Stopping and unregistering deleted service: {service_name}")
                    self._stop_service(service_name)
                    
                    # Unregister health check if exists
                    self.health_monitor.unregister_check(service_name)
                    
                    # Remove from tracking
                    del self.unit_files[service_name]
            
            # Handle new unit files
            for file_path in added:
                full_path = os.path.join(self.config.repo_path, file_path)
                
                try:
                    unit = UnitFileParser.parse(full_path)
                    
                    # Validate unit file
                    errors = UnitFileParser.validate(unit)
                    if errors:
                        self.logger.error(
                            f"New unit file {file_path} has validation errors: {errors}"
                        )
                        continue
                    
                    # Register new service
                    self.logger.info(f"Registering new service: {unit.name}")
                    self.unit_files[unit.name] = full_path
                    self.state_manager.register_service(unit.name)
                    
                except Exception as e:
                    self.logger.error(f"Failed to parse new unit file {file_path}: {e}")
            
            # Handle modified unit files
            for file_path in modified:
                full_path = os.path.join(self.config.repo_path, file_path)
                
                try:
                    unit = UnitFileParser.parse(full_path)
                    
                    # Validate unit file
                    errors = UnitFileParser.validate(unit)
                    if errors:
                        self.logger.error(
                            f"Modified unit file {file_path} has validation errors: {errors}"
                        )
                        continue
                    
                    # Reload and restart affected service
                    self.logger.info(f"Reloading and restarting modified service: {unit.name}")
                    
                    # Update unit file path
                    self.unit_files[unit.name] = full_path
                    
                    # Restart if running
                    state = self.state_manager.get_state(unit.name)
                    if state and state.status == "running":
                        self._stop_service(unit.name)
                        time.sleep(0.5)  # Brief pause
                        self._start_service(unit.name)
                    
                except Exception as e:
                    self.logger.error(f"Failed to reload unit file {file_path}: {e}")
            
            # Mark state as dirty (will be saved by periodic thread)
            # No need to call save_state() here - batched writes handle it
            
        except Exception as e:
            self.logger.error(f"Error handling Git changes: {e}")
    
    def _extract_service_name(self, file_path: str) -> str:
        """
        Extract service name from unit file path.
        
        Args:
            file_path: Path to unit file (relative or absolute)
            
        Returns:
            Service name (filename without .service extension)
        """
        basename = os.path.basename(file_path)
        if basename.endswith('.service'):
            return basename[:-8]
        return basename

    def _handle_client(self, client_socket: socket.socket) -> None:
        """
        Handle a client connection from the CLI.
        
        Receives JSON command, processes it, and sends JSON response.
        
        Args:
            client_socket: Connected client socket
        """
        try:
            # Receive data from client
            data = b""
            while True:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                data += chunk
                # Check if we have a complete JSON message
                try:
                    json.loads(data.decode('utf-8'))
                    break
                except json.JSONDecodeError:
                    continue
            
            if not data:
                return
            
            # Parse JSON command
            try:
                command = json.loads(data.decode('utf-8'))
            except json.JSONDecodeError as e:
                response = {
                    "success": False,
                    "error": f"Invalid JSON: {e}"
                }
                self._send_response(client_socket, response)
                return
            
            # Route command to appropriate handler
            response = self._route_command(command)
            
            # Send response back to client
            self._send_response(client_socket, response)
            
        except Exception as e:
            self.logger.error(f"Error handling client: {e}")
            response = {
                "success": False,
                "error": str(e)
            }
            try:
                self._send_response(client_socket, response)
            except:
                pass
        finally:
            client_socket.close()
    
    def _send_response(self, client_socket: socket.socket, response: Dict[str, Any]) -> None:
        """
        Send JSON response to client.
        
        Args:
            client_socket: Connected client socket
            response: Response dictionary to send
        """
        response_json = json.dumps(response)
        client_socket.sendall(response_json.encode('utf-8'))
    
    def _route_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Route command to appropriate handler.
        
        Args:
            command: Command dictionary with 'action' and other parameters
            
        Returns:
            Response dictionary
        """
        action = command.get('action')
        
        if not action:
            return {
                "success": False,
                "error": "No action specified"
            }
        
        try:
            if action == "start":
                return self._cmd_start_service(command)
            elif action == "stop":
                return self._cmd_stop_service(command)
            elif action == "restart":
                return self._cmd_restart_service(command)
            elif action == "status":
                return self._cmd_get_status(command)
            elif action == "logs":
                return self._cmd_get_logs(command)
            elif action == "list":
                return self._cmd_list_services(command)
            elif action == "rollback":
                return self._cmd_rollback(command)
            elif action == "sync":
                return self._cmd_sync(command)
            else:
                return {
                    "success": False,
                    "error": f"Unknown action: {action}"
                }
        except Exception as e:
            self.logger.error(f"Error executing command {action}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def _cmd_start_service(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle start service command.
        
        Args:
            command: Command dictionary with 'name' parameter
            
        Returns:
            Response dictionary
        """
        service_name = command.get('name')
        if not service_name:
            return {"success": False, "error": "Service name not specified"}
        
        try:
            self._start_service(service_name)
            return {
                "success": True,
                "message": f"Service {service_name} started"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _cmd_stop_service(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle stop service command.
        
        Args:
            command: Command dictionary with 'name' parameter
            
        Returns:
            Response dictionary
        """
        service_name = command.get('name')
        if not service_name:
            return {"success": False, "error": "Service name not specified"}
        
        try:
            self._stop_service(service_name)
            return {
                "success": True,
                "message": f"Service {service_name} stopped"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _cmd_restart_service(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle restart service command.
        
        Args:
            command: Command dictionary with 'name' parameter
            
        Returns:
            Response dictionary
        """
        service_name = command.get('name')
        if not service_name:
            return {"success": False, "error": "Service name not specified"}
        
        try:
            self._stop_service(service_name)
            time.sleep(0.5)  # Brief pause between stop and start
            self._start_service(service_name)
            return {
                "success": True,
                "message": f"Service {service_name} restarted"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _cmd_get_status(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get status command.
        
        Args:
            command: Command dictionary with 'name' parameter
            
        Returns:
            Response dictionary with service state
        """
        service_name = command.get('name')
        if not service_name:
            return {"success": False, "error": "Service name not specified"}
        
        state = self.state_manager.get_state(service_name)
        if not state:
            return {
                "success": False,
                "error": f"Service {service_name} not found"
            }
        
        return {
            "success": True,
            "state": {
                "name": state.name,
                "status": state.status,
                "pid": state.pid,
                "start_time": state.start_time,
                "restart_count": state.restart_count,
                "last_exit_code": state.last_exit_code
            }
        }
    
    def _cmd_get_logs(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle get logs command.
        
        Args:
            command: Command dictionary with 'name' and optional 'lines' parameters
            
        Returns:
            Response dictionary with log contents
        """
        service_name = command.get('name')
        if not service_name:
            return {"success": False, "error": "Service name not specified"}
        
        lines = command.get('lines')
        
        try:
            log_content = self.process_manager.get_logs(service_name, lines)
            return {
                "success": True,
                "logs": log_content
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": f"Log file not found for service {service_name}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _cmd_list_services(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle list services command.
        
        Args:
            command: Command dictionary (no parameters needed)
            
        Returns:
            Response dictionary with list of all services
        """
        services = []
        
        for service_name, state in self.state_manager.services.items():
            services.append({
                "name": state.name,
                "status": state.status,
                "pid": state.pid,
                "restart_count": state.restart_count
            })
        
        return {
            "success": True,
            "services": services
        }
    
    def _cmd_rollback(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle rollback command.
        
        Args:
            command: Command dictionary with 'commit' parameter
            
        Returns:
            Response dictionary
        """
        commit_hash = command.get('commit')
        if not commit_hash:
            return {"success": False, "error": "Commit hash not specified"}
        
        try:
            # Get current unit files before rollback
            old_services = set(self.unit_files.keys())
            
            # Perform rollback
            success = self.git_integration.rollback(commit_hash)
            if not success:
                return {
                    "success": False,
                    "error": f"Failed to rollback to commit {commit_hash}"
                }
            
            # Reload unit files
            self.unit_files.clear()
            self._load_unit_files()
            
            # Get new unit files after rollback
            new_services = set(self.unit_files.keys())
            
            # Determine affected services
            affected = old_services.union(new_services)
            
            # Restart affected services that are running
            restarted = []
            for service_name in affected:
                state = self.state_manager.get_state(service_name)
                if state and state.status == "running":
                    try:
                        self._stop_service(service_name)
                        if service_name in self.unit_files:
                            time.sleep(0.5)
                            self._start_service(service_name)
                        restarted.append(service_name)
                    except Exception as e:
                        self.logger.error(
                            f"Failed to restart service {service_name} after rollback: {e}"
                        )
            
            return {
                "success": True,
                "message": f"Rolled back to commit {commit_hash}",
                "affected_services": list(affected),
                "restarted_services": restarted
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _cmd_sync(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle manual sync command.
        
        Args:
            command: Command dictionary (no parameters needed)
            
        Returns:
            Response dictionary
        """
        try:
            # Force check for Git changes
            if self.git_integration.has_changes():
                self._handle_git_changes()
                return {
                    "success": True,
                    "message": "Git sync completed, changes applied"
                }
            else:
                return {
                    "success": True,
                    "message": "Git sync completed, no changes detected"
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _start_service(self, service_name: str) -> None:
        """
        Start a service.
        
        Args:
            service_name: Name of service to start
            
        Raises:
            ValueError: If service not found or already running
            RuntimeError: If service fails to start
        """
        # Check if service exists
        if service_name not in self.unit_files:
            raise ValueError(f"Service {service_name} not found")
        
        # Check current state
        state = self.state_manager.get_state(service_name)
        if state and state.status == "running":
            raise ValueError(f"Service {service_name} is already running")
        
        # Parse unit file
        unit_file_path = self.unit_files[service_name]
        unit = UnitFileParser.parse(unit_file_path)
        
        # Resolve dependencies
        if unit.after:
            try:
                # Build dependency graph
                self.dependency_resolver.clear()
                for dep in unit.after:
                    # Remove .service extension if present
                    dep_name = dep.replace('.service', '')
                    self.dependency_resolver.add_dependency(service_name, dep_name)
                
                # Get start order
                services_to_start = [service_name] + [
                    dep.replace('.service', '') for dep in unit.after
                ]
                start_order = self.dependency_resolver.get_start_order(services_to_start)
                
                # Start dependencies first
                for dep_service in start_order:
                    if dep_service == service_name:
                        continue
                    
                    dep_state = self.state_manager.get_state(dep_service)
                    if dep_state and dep_state.status != "running":
                        self.logger.info(
                            f"Starting dependency {dep_service} for {service_name}"
                        )
                        self._start_service(dep_service)
                
            except ValueError as e:
                raise RuntimeError(f"Dependency resolution failed: {e}")
        
        # Start the process
        self.logger.info(f"Starting service {service_name}")
        process_info = self.process_manager.spawn_process(unit)
        
        # Update state
        self.state_manager.update_state(
            service_name,
            status="running",
            pid=process_info.pid,
            start_time=time.time()
        )
        
        # Register health check if configured
        if unit.health_check_url:
            self.health_monitor.register_check(
                service_name,
                unit.health_check_url,
                unit.health_check_interval
            )
        
        # Mark state as dirty (will be saved by periodic thread)
        # No need to call save_state() here - batched writes handle it
        
        self.logger.info(
            f"Service {service_name} started with PID {process_info.pid}"
        )
    
    def _stop_service(self, service_name: str) -> None:
        """
        Stop a service.
        
        Args:
            service_name: Name of service to stop
            
        Raises:
            ValueError: If service not found or not running
        """
        # Check if service exists
        state = self.state_manager.get_state(service_name)
        if not state:
            raise ValueError(f"Service {service_name} not found")
        
        if state.status != "running" or state.pid is None:
            raise ValueError(f"Service {service_name} is not running")
        
        # Stop the process
        self.logger.info(f"Stopping service {service_name} (PID {state.pid})")
        success = self.process_manager.stop_process(state.pid)
        
        if success:
            # Update state
            self.state_manager.update_state(
                service_name,
                status="stopped",
                pid=None
            )
            
            # Unregister health check
            self.health_monitor.unregister_check(service_name)
            
            # Mark state as dirty (will be saved by periodic thread)
            # No need to call save_state() here - batched writes handle it
            
            self.logger.info(f"Service {service_name} stopped")
        else:
            raise RuntimeError(f"Failed to stop service {service_name}")

    def _shutdown(self) -> None:
        """
        Perform graceful shutdown of the daemon.
        
        Stops all running services, saves state, and cleans up resources.
        """
        self.logger.info("Initiating graceful shutdown")
        
        try:
            # Stop health monitor
            self.logger.info("Stopping health monitor")
            self.health_monitor.stop()
            
            # Stop all running services
            self.logger.info("Stopping all running services")
            running_services = [
                name for name, state in self.state_manager.services.items()
                if state.status == "running" and state.pid is not None
            ]
            
            for service_name in running_services:
                try:
                    self.logger.info(f"Stopping service {service_name}")
                    self._stop_service(service_name)
                except Exception as e:
                    self.logger.error(f"Error stopping service {service_name}: {e}")
            
            # Save state to disk (force immediate save on shutdown)
            self.logger.info("Saving state to disk")
            self.state_manager.save_state(force=True)
            
            # Close Unix socket
            if self.server_socket:
                self.logger.info("Closing Unix socket")
                self.server_socket.close()
                
                # Remove socket file
                if os.path.exists(self.socket_path):
                    os.unlink(self.socket_path)
            
            # Wait for Git monitor thread to finish
            if self.git_monitor_thread and self.git_monitor_thread.is_alive():
                self.logger.info("Waiting for Git monitor thread to finish")
                self.git_monitor_thread.join(timeout=5)
            
            # Wait for process monitor thread to finish
            if self.process_monitor_thread and self.process_monitor_thread.is_alive():
                self.logger.info("Waiting for process monitor thread to finish")
                self.process_monitor_thread.join(timeout=5)
            
            # Wait for state save thread to finish
            if self.state_save_thread and self.state_save_thread.is_alive():
                self.logger.info("Waiting for state save thread to finish")
                self.state_save_thread.join(timeout=5)
            
            self.logger.info("Graceful shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}", exc_info=True)
