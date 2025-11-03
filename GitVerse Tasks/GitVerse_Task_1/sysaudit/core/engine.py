"""Core audit engine that orchestrates all subsystems"""

import logging
import time
from datetime import datetime
from typing import List, Optional, Callable, Any
from pathlib import Path
from functools import wraps

from ..models import FileEvent, ComplianceIssue, Config
from ..monitor.file_monitor import FileMonitor
from ..git.manager import GitManager, GitManagerError
from ..compliance.checker import ComplianceChecker
from ..alert.manager import AlertManager


logger = logging.getLogger(__name__)


def retry_on_transient_error(max_retries: int = 3, delay: float = 0.5) -> Callable:
    """
    Decorator for retrying operations on transient errors.
    
    Retries operations that fail due to temporary issues like
    file locks or brief unavailability.
    
    Args:
        max_retries: Maximum number of retry attempts
        delay: Delay between retries in seconds
        
    Requirements: 9.2, 9.3
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except (OSError, IOError) as e:
                    # Transient errors that might resolve with retry
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.debug(
                            f"Transient error in {func.__name__}, "
                            f"retrying ({attempt + 1}/{max_retries}): {e}"
                        )
                        time.sleep(delay)
                    else:
                        logger.warning(
                            f"Operation {func.__name__} failed after {max_retries} attempts: {e}"
                        )
                except Exception as e:
                    # Non-transient errors - don't retry
                    raise
            
            # If we exhausted retries, raise the last exception
            if last_exception:
                raise last_exception
                
        return wrapper
    return decorator


def safe_operation(operation_name: str) -> Callable:
    """
    Decorator for safe operations that handles errors gracefully.
    
    Logs errors but doesn't crash the system, implementing graceful
    error recovery for race conditions and file disappearance.
    
    Args:
        operation_name: Name of the operation for logging
        
    Requirements: 9.2, 9.3
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except FileNotFoundError as e:
                # Handle file disappearance gracefully (Requirement 9.2)
                logger.warning(
                    f"{operation_name}: File disappeared during operation: {e}"
                )
                return None
            except PermissionError as e:
                # Handle permission errors gracefully
                logger.error(
                    f"{operation_name}: Permission denied: {e}"
                )
                return None
            except GitManagerError as e:
                # Handle Git-specific errors
                logger.error(
                    f"{operation_name}: Git operation failed: {e}"
                )
                return None
            except Exception as e:
                # Handle any unexpected errors (Requirement 9.3)
                logger.error(
                    f"{operation_name}: Unexpected error: {e}",
                    exc_info=True
                )
                return None
        return wrapper
    return decorator


class AuditEngineError(Exception):
    """Base exception for AuditEngine errors"""
    pass


class AuditEngine:
    """
    Core orchestration engine for the audit system.
    
    Coordinates all subsystems:
    - File monitoring
    - Git version control
    - Compliance checking
    - Alert management
    
    Requirements: 1.1, 1.2, 2.1, 6.1
    """
    
    def __init__(self, config: Config, log_level: str = 'INFO'):
        """
        Initialize the audit engine with configuration.
        
        Args:
            config: System configuration
            log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            
        Raises:
            AuditEngineError: If initialization fails
        """
        self.config = config
        self.running = False
        
        # Configure logging (Requirement 9.2, 9.3)
        self._configure_logging(log_level)
        
        logger.info("Initializing AuditEngine...")
        logger.info(f"Configuration: repo_path={config.repo_path}, watch_paths={config.watch_paths}")
        
        try:
            # Initialize subsystems
            self.monitor = FileMonitor(config)
            logger.debug("FileMonitor initialized")
            
            self.git_manager = GitManager(config)
            logger.debug("GitManager initialized")
            
            self.compliance_checker = ComplianceChecker(config)
            logger.debug("ComplianceChecker initialized")
            
            self.alert_manager = AlertManager(config)
            logger.debug("AlertManager initialized")
            
            logger.info("AuditEngine initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize AuditEngine: {e}", exc_info=True)
            raise AuditEngineError(f"Failed to initialize AuditEngine: {e}")
    
    @staticmethod
    def _configure_logging(log_level: str) -> None:
        """
        Configure logging for the audit system.
        
        Sets up comprehensive logging for all operations.
        
        Args:
            log_level: Logging level string
            
        Requirements: 9.2, 9.3
        """
        # Convert string to logging level
        numeric_level = getattr(logging, log_level.upper(), logging.INFO)
        
        # Configure root logger for sysaudit package
        sysaudit_logger = logging.getLogger('sysaudit')
        sysaudit_logger.setLevel(numeric_level)
        
        # Create console handler if not already configured
        if not sysaudit_logger.handlers:
            handler = logging.StreamHandler()
            handler.setLevel(numeric_level)
            
            # Create formatter
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            handler.setFormatter(formatter)
            
            sysaudit_logger.addHandler(handler)
        
        logger.debug(f"Logging configured at {log_level} level")
    
    def initialize_repository(self) -> None:
        """
        Initialize the Git repository if not already initialized.
        
        Creates the repository and baseline branch.
        
        Raises:
            AuditEngineError: If repository initialization fails
        """
        try:
            if not self.git_manager.is_initialized():
                logger.info("Initializing Git repository...")
                logger.info(f"Repository path: {self.config.repo_path}")
                logger.info(f"Baseline branch: {self.config.baseline_branch}")
                
                self.git_manager.init_repo()
                
                logger.info("Git repository initialized successfully")
                logger.info(f"Repository location: {self.config.repo_path}")
            else:
                logger.info("Git repository already initialized")
                logger.debug(f"Repository path: {self.config.repo_path}")
                
        except GitManagerError as e:
            logger.error(f"Failed to initialize repository: {e}", exc_info=True)
            raise AuditEngineError(f"Failed to initialize repository: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during repository initialization: {e}", exc_info=True)
            raise AuditEngineError(f"Failed to initialize repository: {e}")
    
    def start_monitoring(self) -> None:
        """
        Start continuous file system monitoring.
        
        Begins monitoring configured paths and processing file change events.
        This method blocks until monitoring is stopped.
        
        Requirements: 1.1, 1.2
        
        Raises:
            AuditEngineError: If monitoring cannot be started
        """
        if self.running:
            logger.warning("Attempted to start monitoring while already running")
            raise AuditEngineError("Monitoring is already running")
        
        # Ensure repository is initialized
        if not self.git_manager.is_initialized():
            logger.error("Repository not initialized")
            raise AuditEngineError(
                "Repository not initialized. Call initialize_repository() first."
            )
        
        # Validate watch paths exist
        logger.debug("Validating watch paths...")
        for path in self.config.watch_paths:
            if not Path(path).exists():
                logger.error(f"Watch path does not exist: {path}")
                raise AuditEngineError(f"Watch path does not exist: {path}")
            logger.debug(f"Watch path validated: {path}")
        
        logger.info(f"Starting monitoring of {len(self.config.watch_paths)} path(s)")
        logger.info(f"Watch paths: {', '.join(self.config.watch_paths)}")
        logger.info(f"Auto-compliance: {self.config.auto_compliance}")
        logger.info(f"Batch interval: {self.config.batch_interval}s, Batch size: {self.config.batch_size}")
        
        try:
            # Start file monitor with callback
            self.monitor.start(callback=self._on_file_change)
            self.running = True
            
            logger.info("=" * 60)
            logger.info("Monitoring started successfully - Press Ctrl+C to stop")
            logger.info("=" * 60)
            
            # Keep running until stopped
            self.monitor.wait()
            
        except KeyboardInterrupt:
            logger.info("Received interrupt signal (Ctrl+C)")
            self.stop_monitoring()
        except Exception as e:
            self.running = False
            logger.error(f"Monitoring failed: {e}", exc_info=True)
            raise AuditEngineError(f"Monitoring failed: {e}")
    
    def stop_monitoring(self) -> None:
        """
        Stop file system monitoring.
        
        Gracefully stops the monitor and flushes any pending events.
        """
        if not self.running:
            logger.warning("Attempted to stop monitoring while not running")
            return
        
        logger.info("=" * 60)
        logger.info("Stopping monitoring...")
        logger.info("=" * 60)
        
        try:
            # Stop the monitor (this will flush pending events)
            self.monitor.stop()
            self.running = False
            
            logger.info("Monitoring stopped successfully")
            logger.info("All pending events have been processed")
            
        except Exception as e:
            logger.error(f"Error stopping monitoring: {e}", exc_info=True)
            self.running = False
    
    @safe_operation("File change processing")
    def _on_file_change(self, events: List[FileEvent]) -> None:
        """
        Handle file change events from the monitor.
        
        This is the main event processing callback that:
        1. Commits changes to Git
        2. Runs compliance checks if enabled
        3. Sends alerts for critical issues
        
        Args:
            events: List of FileEvent objects representing changes
            
        Requirements: 2.1, 6.1, 9.2, 9.3
        """
        if not events:
            return
        
        logger.info(f"Processing {len(events)} file change events")
        
        # Commit changes to Git (Requirement 2.1)
        self._commit_changes(events)
        
        # Run compliance checks if enabled (Requirement 6.1)
        if self.config.auto_compliance:
            self._check_compliance(events)
    
    @safe_operation("Git commit")
    @retry_on_transient_error(max_retries=3, delay=0.5)
    def _commit_changes(self, events: List[FileEvent]) -> None:
        """
        Commit file changes to Git repository.
        
        Handles race conditions and file disappearance gracefully.
        
        Args:
            events: List of FileEvent objects
            
        Requirements: 2.1, 9.2, 9.3
        """
        # Filter out events for files that no longer exist (race condition)
        valid_events = []
        for event in events:
            path = Path(event.path)
            # For deleted events, we don't need the file to exist
            if event.event_type == 'deleted' or path.exists():
                valid_events.append(event)
            else:
                logger.debug(f"Skipping commit for disappeared file: {event.path}")
        
        if not valid_events:
            logger.debug("No valid events to commit after filtering")
            return
        
        commit = self.git_manager.commit_changes(valid_events)
        
        if commit:
            logger.info(f"Created commit: {commit.hexsha[:8]} - {commit.summary}")
        else:
            logger.debug("No changes to commit (files may have disappeared)")
    
    @safe_operation("Compliance check")
    def _check_compliance(self, events: List[FileEvent]) -> None:
        """
        Run compliance checks on changed files.
        
        Checks files for security issues and sends alerts for critical findings.
        
        Args:
            events: List of FileEvent objects
            
        Requirements: 6.1, 13.1, 13.2, 13.3, 13.4
        """
        # Extract file paths from events (skip deleted files)
        file_paths = [event.path for event in events if event.event_type != 'deleted']
        
        if not file_paths:
            return
        
        # Filter out files that no longer exist (race condition handling)
        existing_paths = []
        for path in file_paths:
            if Path(path).exists():
                existing_paths.append(path)
            else:
                logger.debug(f"Skipping compliance check for disappeared file: {path}")
        
        if not existing_paths:
            return
        
        # Run compliance checks
        issues = self.compliance_checker.check_files(existing_paths)
        
        if issues:
            logger.info(f"Found {len(issues)} compliance issues")
            
            # Send alerts for critical issues
            for issue in issues:
                logger.warning(
                    f"Compliance issue: {issue.severity} - {issue.rule} - {issue.path}"
                )
                
                # Send alert (AlertManager filters by severity)
                try:
                    self.alert_manager.send_alert(issue)
                except Exception as e:
                    # Don't fail if alert sending fails
                    logger.error(f"Failed to send alert: {e}")
        else:
            logger.debug("No compliance issues found")
    
    def create_snapshot(self, message: str) -> None:
        """
        Create a manual snapshot of current state.
        
        Commits all currently monitored files to the repository.
        
        Args:
            message: Commit message for the snapshot
            
        Raises:
            AuditEngineError: If snapshot creation fails
        """
        if not self.git_manager.is_initialized():
            raise AuditEngineError("Repository not initialized")
        
        logger.info(f"Creating snapshot: {message}")
        
        try:
            # Create events for all files in watch paths
            events = []
            for watch_path in self.config.watch_paths:
                path = Path(watch_path)
                
                if not path.exists():
                    logger.warning(f"Watch path no longer exists: {watch_path}")
                    continue
                
                if path.is_file():
                    # Single file - verify it still exists
                    try:
                        if path.exists():
                            events.append(FileEvent(
                                path=str(path),
                                event_type='modified',
                                timestamp=datetime.now()
                            ))
                    except (OSError, PermissionError) as e:
                        logger.warning(f"Cannot access file {path}: {e}")
                        continue
                        
                elif path.is_dir():
                    # Directory - add all files with error handling
                    try:
                        for file_path in path.rglob('*'):
                            try:
                                if file_path.is_file():
                                    # Apply filters
                                    if not self.monitor.filter.should_ignore(str(file_path)):
                                        events.append(FileEvent(
                                            path=str(file_path),
                                            event_type='modified',
                                            timestamp=datetime.now()
                                        ))
                            except (OSError, PermissionError) as e:
                                logger.debug(f"Cannot access file {file_path}: {e}")
                                continue
                    except (OSError, PermissionError) as e:
                        logger.warning(f"Cannot scan directory {path}: {e}")
                        continue
            
            if events:
                # Override commit message for snapshot
                commit = self.git_manager.commit_changes(events)
                if commit:
                    logger.info(f"Snapshot created: {commit.hexsha[:8]}")
                else:
                    logger.warning("No changes to snapshot")
            else:
                logger.warning("No files found to snapshot")
                
        except Exception as e:
            logger.error(f"Snapshot creation failed: {e}", exc_info=True)
            raise AuditEngineError(f"Failed to create snapshot: {e}")
    
    def run_compliance_scan(self) -> List[ComplianceIssue]:
        """
        Run a full compliance scan on all watched paths.
        
        Returns:
            List of compliance issues found
            
        Raises:
            AuditEngineError: If scan fails
        """
        logger.info("Running full compliance scan...")
        
        try:
            issues = self.compliance_checker.scan_all_watched_paths()
            
            logger.info(f"Compliance scan complete: found {len(issues)} issues")
            
            # Log summary by severity
            high = sum(1 for i in issues if i.severity == 'HIGH')
            medium = sum(1 for i in issues if i.severity == 'MEDIUM')
            low = sum(1 for i in issues if i.severity == 'LOW')
            
            logger.info(f"  HIGH: {high}, MEDIUM: {medium}, LOW: {low}")
            
            return issues
            
        except Exception as e:
            raise AuditEngineError(f"Compliance scan failed: {e}")
    
    def is_running(self) -> bool:
        """
        Check if monitoring is currently active.
        
        Returns:
            True if monitoring is running, False otherwise
        """
        return self.running
    
    def get_status(self) -> dict:
        """
        Get current status of the audit engine.
        
        Returns:
            Dictionary with status information
        """
        return {
            'running': self.running,
            'repository_initialized': self.git_manager.is_initialized(),
            'watch_paths': self.config.watch_paths,
            'auto_compliance': self.config.auto_compliance,
            'gpg_signing': self.config.gpg_sign,
            'webhook_configured': self.config.webhook_url is not None,
        }
