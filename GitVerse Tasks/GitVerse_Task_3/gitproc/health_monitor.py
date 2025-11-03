"""
Health monitoring for GitProc services.
Performs periodic health checks and triggers restarts on failures.
"""

import logging
import threading
import time
import requests
from typing import Dict, Optional, Callable
from dataclasses import dataclass

from gitproc.state_manager import StateManager


@dataclass
class HealthCheck:
    """Configuration for a service health check."""
    service_name: str
    url: str
    interval: int  # seconds
    timeout: int = 5  # seconds
    last_check_time: float = 0.0
    failure_count: int = 0


class HealthMonitor:
    """
    Monitors service health and triggers restarts on failures.
    """
    
    def __init__(self, state_manager: StateManager, restart_callback: Callable[[str], None]):
        """
        Initialize HealthMonitor.
        
        Args:
            state_manager: StateManager instance for tracking service states
            restart_callback: Callback function to restart a service (takes service_name)
        """
        self.state_manager = state_manager
        self.restart_callback = restart_callback
        self.checks: Dict[str, HealthCheck] = {}
        self.logger = logging.getLogger(__name__)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
    
    def register_check(self, service_name: str, url: str, interval: int) -> None:
        """
        Register a health check for a service.
        
        Args:
            service_name: Name of the service to monitor
            url: HTTP URL to check
            interval: Check interval in seconds
        """
        with self._lock:
            self.checks[service_name] = HealthCheck(
                service_name=service_name,
                url=url,
                interval=interval,
                last_check_time=time.time()
            )
            self.logger.info(
                f"Registered health check for {service_name}: "
                f"URL={url}, interval={interval}s"
            )
    
    def unregister_check(self, service_name: str) -> None:
        """
        Unregister a health check for a service.
        
        Args:
            service_name: Name of the service
        """
        with self._lock:
            if service_name in self.checks:
                del self.checks[service_name]
                self.logger.info(f"Unregistered health check for {service_name}")
    
    def start(self) -> None:
        """
        Start the health monitoring thread.
        """
        if self._running:
            self.logger.warning("Health monitor is already running")
            return
        
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._thread.start()
        self.logger.info("Health monitor started")
    
    def stop(self) -> None:
        """
        Stop the health monitoring thread.
        """
        if not self._running:
            return
        
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        self.logger.info("Health monitor stopped")
    
    def _monitor_loop(self) -> None:
        """
        Main monitoring loop that runs in a separate thread.
        """
        while self._running:
            try:
                self.run_checks()
            except Exception as e:
                self.logger.error(f"Error in health monitor loop: {e}")
            
            # Sleep for a short interval before next check cycle
            time.sleep(1)
    
    def run_checks(self) -> None:
        """
        Execute all scheduled health checks.
        Checks are run in separate threads to avoid blocking.
        """
        current_time = time.time()
        
        with self._lock:
            checks_to_run = []
            for check in self.checks.values():
                # Check if it's time to run this health check
                if current_time - check.last_check_time >= check.interval:
                    checks_to_run.append(check)
                    check.last_check_time = current_time
        
        # Run checks in separate threads
        for check in checks_to_run:
            thread = threading.Thread(
                target=self._run_single_check,
                args=(check,),
                daemon=True
            )
            thread.start()
    
    def _run_single_check(self, check: HealthCheck) -> None:
        """
        Run a single health check.
        
        Args:
            check: HealthCheck configuration
        """
        try:
            success = self.check_http(check.url, check.timeout)
            
            if success:
                # Health check passed
                if check.failure_count > 0:
                    self.logger.info(
                        f"Health check recovered for {check.service_name}"
                    )
                check.failure_count = 0
            else:
                # Health check failed
                check.failure_count += 1
                self._handle_failure(check)
                
        except Exception as e:
            self.logger.error(
                f"Exception during health check for {check.service_name}: {e}"
            )
            check.failure_count += 1
            self._handle_failure(check)
    
    def check_http(self, url: str, timeout: int = 5) -> bool:
        """
        Perform HTTP health check.
        
        Args:
            url: URL to check
            timeout: Request timeout in seconds
            
        Returns:
            True if health check passed (HTTP 200), False otherwise
        """
        try:
            response = requests.get(url, timeout=timeout)
            return response.status_code == 200
        except requests.exceptions.RequestException as e:
            self.logger.debug(f"HTTP health check failed for {url}: {e}")
            return False
    
    def _handle_failure(self, check: HealthCheck) -> None:
        """
        Handle health check failure.
        
        Args:
            check: HealthCheck that failed
        """
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.logger.warning(
            f"Health check failed for {check.service_name} at {timestamp} "
            f"(failure count: {check.failure_count})"
        )
        
        # Trigger service restart
        try:
            self.logger.info(
                f"Triggering restart for {check.service_name} due to health check failure"
            )
            self.restart_callback(check.service_name)
        except Exception as e:
            self.logger.error(
                f"Failed to restart {check.service_name}: {e}"
            )
