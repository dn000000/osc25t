"""Process tracking for identifying which process modified files"""

import os
import sys
import logging
from typing import Optional
from pathlib import Path

from ..models import ProcessInfo

logger = logging.getLogger(__name__)


class ProcessTracker:
    """
    Tracks and identifies processes that modify files.
    
    Uses platform-specific methods to identify the process responsible
    for file modifications. On Linux, uses /proc filesystem. On Windows,
    uses alternative methods.
    """
    
    @staticmethod
    def get_process_info() -> Optional[ProcessInfo]:
        """
        Get information about the current process or the process that triggered the event.
        
        This is a best-effort attempt to identify the process. If identification
        fails, returns None (Requirement 4.3).
        
        Returns:
            ProcessInfo object or None if process cannot be identified
        """
        try:
            if sys.platform.startswith('linux'):
                return ProcessTracker._get_process_info_linux()
            elif sys.platform == 'win32':
                return ProcessTracker._get_process_info_windows()
            else:
                logger.debug(f"Process tracking not implemented for platform: {sys.platform}")
                return None
        except Exception as e:
            logger.debug(f"Failed to get process info: {e}")
            return None
    
    @staticmethod
    def _get_process_info_linux() -> Optional[ProcessInfo]:
        """
        Get process information on Linux using /proc filesystem.
        
        Attempts to identify the process by reading /proc entries.
        This is a simplified implementation that gets the parent process
        information, as identifying the exact process that modified a file
        requires kernel-level auditing (auditd).
        
        Returns:
            ProcessInfo object or None
        """
        try:
            # Get parent process ID (the process that spawned this monitoring)
            # In a real implementation, we'd use auditd or fanotify to get
            # the actual process that modified the file
            ppid = os.getppid()
            
            # Read process information from /proc
            proc_path = Path(f"/proc/{ppid}")
            
            if not proc_path.exists():
                logger.debug(f"Process {ppid} not found in /proc")
                return None
            
            # Read process name from /proc/[pid]/comm
            comm_file = proc_path / "comm"
            if comm_file.exists():
                process_name = comm_file.read_text().strip()
            else:
                process_name = "unknown"
            
            # Read command line from /proc/[pid]/cmdline
            cmdline_file = proc_path / "cmdline"
            if cmdline_file.exists():
                # cmdline is null-separated, convert to space-separated
                cmdline_raw = cmdline_file.read_bytes()
                cmdline = cmdline_raw.replace(b'\x00', b' ').decode('utf-8', errors='replace').strip()
            else:
                cmdline = ""
            
            # If cmdline is empty, use process name
            if not cmdline:
                cmdline = process_name
            
            return ProcessInfo(
                pid=ppid,
                name=process_name,
                cmdline=cmdline
            )
            
        except Exception as e:
            logger.debug(f"Error reading /proc filesystem: {e}")
            return None
    
    @staticmethod
    def _get_process_info_windows() -> Optional[ProcessInfo]:
        """
        Get process information on Windows.
        
        Uses Windows-specific APIs to identify the process.
        This is a simplified implementation.
        
        Returns:
            ProcessInfo object or None
        """
        try:
            import psutil
            
            # Get parent process
            parent = psutil.Process(os.getppid())
            
            return ProcessInfo(
                pid=parent.pid,
                name=parent.name(),
                cmdline=' '.join(parent.cmdline())
            )
            
        except ImportError:
            logger.debug("psutil not available for Windows process tracking")
            return None
        except Exception as e:
            logger.debug(f"Error getting Windows process info: {e}")
            return None
    
    @staticmethod
    def get_process_by_pid(pid: int) -> Optional[ProcessInfo]:
        """
        Get process information for a specific PID.
        
        Args:
            pid: Process ID
            
        Returns:
            ProcessInfo object or None if process not found
        """
        try:
            if sys.platform.startswith('linux'):
                return ProcessTracker._get_process_by_pid_linux(pid)
            elif sys.platform == 'win32':
                return ProcessTracker._get_process_by_pid_windows(pid)
            else:
                return None
        except Exception as e:
            logger.debug(f"Failed to get process info for PID {pid}: {e}")
            return None
    
    @staticmethod
    def _get_process_by_pid_linux(pid: int) -> Optional[ProcessInfo]:
        """
        Get process information for a specific PID on Linux.
        
        Args:
            pid: Process ID
            
        Returns:
            ProcessInfo object or None
        """
        try:
            proc_path = Path(f"/proc/{pid}")
            
            if not proc_path.exists():
                return None
            
            # Read process name
            comm_file = proc_path / "comm"
            if comm_file.exists():
                process_name = comm_file.read_text().strip()
            else:
                process_name = "unknown"
            
            # Read command line
            cmdline_file = proc_path / "cmdline"
            if cmdline_file.exists():
                cmdline_raw = cmdline_file.read_bytes()
                cmdline = cmdline_raw.replace(b'\x00', b' ').decode('utf-8', errors='replace').strip()
            else:
                cmdline = ""
            
            if not cmdline:
                cmdline = process_name
            
            return ProcessInfo(
                pid=pid,
                name=process_name,
                cmdline=cmdline
            )
            
        except Exception as e:
            logger.debug(f"Error reading /proc/{pid}: {e}")
            return None
    
    @staticmethod
    def _get_process_by_pid_windows(pid: int) -> Optional[ProcessInfo]:
        """
        Get process information for a specific PID on Windows.
        
        Args:
            pid: Process ID
            
        Returns:
            ProcessInfo object or None
        """
        try:
            import psutil
            
            process = psutil.Process(pid)
            
            return ProcessInfo(
                pid=process.pid,
                name=process.name(),
                cmdline=' '.join(process.cmdline())
            )
            
        except ImportError:
            logger.debug("psutil not available for Windows process tracking")
            return None
        except Exception as e:
            logger.debug(f"Error getting Windows process info for PID {pid}: {e}")
            return None
    
    @staticmethod
    def find_process_by_file(filepath: str) -> Optional[ProcessInfo]:
        """
        Attempt to find which process has a file open.
        
        This is a best-effort implementation. On Linux, it searches through
        /proc/*/fd to find processes with the file open. This may not always
        identify the process that modified the file, especially if the
        modification was quick.
        
        Args:
            filepath: Path to the file
            
        Returns:
            ProcessInfo object or None if no process found
        """
        try:
            if sys.platform.startswith('linux'):
                return ProcessTracker._find_process_by_file_linux(filepath)
            else:
                logger.debug(f"find_process_by_file not implemented for {sys.platform}")
                return None
        except Exception as e:
            logger.debug(f"Error finding process for file {filepath}: {e}")
            return None
    
    @staticmethod
    def _find_process_by_file_linux(filepath: str) -> Optional[ProcessInfo]:
        """
        Find process that has a file open on Linux.
        
        Args:
            filepath: Path to the file
            
        Returns:
            ProcessInfo object or None
        """
        try:
            # Resolve to absolute path
            abs_path = str(Path(filepath).resolve())
            
            # Search through /proc/*/fd
            proc_dir = Path("/proc")
            
            for pid_dir in proc_dir.iterdir():
                if not pid_dir.is_dir() or not pid_dir.name.isdigit():
                    continue
                
                try:
                    pid = int(pid_dir.name)
                    fd_dir = pid_dir / "fd"
                    
                    if not fd_dir.exists():
                        continue
                    
                    # Check each file descriptor
                    for fd in fd_dir.iterdir():
                        try:
                            link_target = str(fd.resolve())
                            if link_target == abs_path:
                                # Found the process!
                                return ProcessTracker._get_process_by_pid_linux(pid)
                        except (OSError, PermissionError):
                            # Can't read this fd, skip
                            continue
                            
                except (OSError, PermissionError, ValueError):
                    # Can't access this process, skip
                    continue
            
            return None
            
        except Exception as e:
            logger.debug(f"Error searching /proc for file {filepath}: {e}")
            return None
