"""
Resource controller for GitProc.
Manages cgroups for resource limitation (memory and CPU).
"""

import os
import logging
from typing import Optional
from pathlib import Path


class ResourceController:
    """
    Manages cgroups for resource limitation.
    Supports both cgroup v1 and v2.
    """
    
    def __init__(self, cgroup_root: str = "/sys/fs/cgroup"):
        """
        Initialize ResourceController.
        
        Args:
            cgroup_root: Root path for cgroup filesystem
        """
        self.cgroup_root = cgroup_root
        self.cgroup_version = self._detect_cgroup_version()
        self.logger = logging.getLogger(__name__)
    
    def _detect_cgroup_version(self) -> int:
        """
        Detect cgroup version (v1 or v2).
        
        Returns:
            1 for cgroup v1, 2 for cgroup v2
        """
        # Check if cgroup v2 is mounted (unified hierarchy)
        cgroup2_path = "/sys/fs/cgroup/cgroup.controllers"
        if os.path.exists(cgroup2_path):
            return 2
        
        # Check for cgroup v1 (separate hierarchies)
        memory_path = "/sys/fs/cgroup/memory"
        cpu_path = "/sys/fs/cgroup/cpu"
        if os.path.exists(memory_path) or os.path.exists(cpu_path):
            return 1
        
        # Default to v2 if detection fails
        return 2
    
    def create_cgroup(self, 
                     service_name: str,
                     memory_limit: Optional[int] = None,
                     cpu_quota: Optional[float] = None) -> Optional[str]:
        """
        Create cgroup and set resource limits.
        
        Args:
            service_name: Name of the service
            memory_limit: Memory limit in bytes (optional)
            cpu_quota: CPU quota as float 0.0-1.0 (optional)
            
        Returns:
            Path to created cgroup, or None if creation failed
        """
        try:
            if self.cgroup_version == 2:
                cgroup_path = self._create_cgroup_v2(service_name)
            else:
                cgroup_path = self._create_cgroup_v1(service_name)
            
            if cgroup_path is None:
                return None
            
            # Set memory limit if specified
            if memory_limit is not None:
                self._set_memory_limit(cgroup_path, memory_limit)
            
            # Set CPU quota if specified
            if cpu_quota is not None:
                self._set_cpu_quota(cgroup_path, cpu_quota)
            
            return cgroup_path
            
        except Exception as e:
            self.logger.warning(
                f"Failed to create cgroup for {service_name}: {e}. "
                "Continuing without resource limits."
            )
            return None
    
    def _create_cgroup_v2(self, service_name: str) -> Optional[str]:
        """
        Create cgroup for v2 (unified hierarchy).
        
        Args:
            service_name: Name of the service
            
        Returns:
            Path to created cgroup
        """
        cgroup_path = os.path.join(self.cgroup_root, "gitproc", service_name)
        
        # Create gitproc parent directory if it doesn't exist
        parent_path = os.path.join(self.cgroup_root, "gitproc")
        os.makedirs(parent_path, exist_ok=True)
        
        # Enable controllers in parent if needed
        self._enable_controllers_v2(parent_path)
        
        # Create service cgroup directory
        os.makedirs(cgroup_path, exist_ok=True)
        
        return cgroup_path
    
    def _create_cgroup_v1(self, service_name: str) -> Optional[str]:
        """
        Create cgroup for v1 (separate hierarchies).
        
        Args:
            service_name: Name of the service
            
        Returns:
            Path to created cgroup (memory hierarchy path)
        """
        # For v1, we need to create in both memory and cpu hierarchies
        memory_path = os.path.join(self.cgroup_root, "memory", "gitproc", service_name)
        cpu_path = os.path.join(self.cgroup_root, "cpu", "gitproc", service_name)
        
        # Create memory cgroup
        os.makedirs(memory_path, exist_ok=True)
        
        # Create CPU cgroup
        os.makedirs(cpu_path, exist_ok=True)
        
        # Return memory path as primary (we'll handle CPU separately)
        return memory_path
    
    def _enable_controllers_v2(self, cgroup_path: str) -> None:
        """
        Enable memory and CPU controllers for cgroup v2.
        
        Args:
            cgroup_path: Path to cgroup directory
        """
        try:
            subtree_control = os.path.join(cgroup_path, "cgroup.subtree_control")
            if os.path.exists(subtree_control):
                with open(subtree_control, 'w') as f:
                    f.write("+memory +cpu")
        except (OSError, PermissionError):
            # If we can't enable controllers, continue anyway
            pass

    def _set_memory_limit(self, cgroup_path: str, memory_limit: int) -> None:
        """
        Set memory limit for cgroup.
        
        Args:
            cgroup_path: Path to cgroup directory
            memory_limit: Memory limit in bytes
        """
        if self.cgroup_version == 2:
            # cgroup v2: write to memory.max
            memory_file = os.path.join(cgroup_path, "memory.max")
        else:
            # cgroup v1: write to memory.limit_in_bytes
            memory_file = os.path.join(cgroup_path, "memory.limit_in_bytes")
        
        try:
            with open(memory_file, 'w') as f:
                f.write(str(memory_limit))
            self.logger.info(f"Set memory limit to {memory_limit} bytes for {cgroup_path}")
        except (OSError, PermissionError) as e:
            self.logger.warning(f"Failed to set memory limit: {e}")
    
    def _set_cpu_quota(self, cgroup_path: str, cpu_quota: float) -> None:
        """
        Set CPU quota for cgroup.
        
        Args:
            cgroup_path: Path to cgroup directory
            cpu_quota: CPU quota as float (0.0 to 1.0, e.g., 0.5 = 50%)
        """
        # Convert quota to period/quota values
        # Standard period is 100ms (100000 microseconds)
        period = 100000
        quota = int(period * cpu_quota)
        
        if self.cgroup_version == 2:
            # cgroup v2: write to cpu.max as "quota period"
            cpu_file = os.path.join(cgroup_path, "cpu.max")
            try:
                with open(cpu_file, 'w') as f:
                    f.write(f"{quota} {period}")
                self.logger.info(f"Set CPU quota to {cpu_quota*100}% for {cgroup_path}")
            except (OSError, PermissionError) as e:
                self.logger.warning(f"Failed to set CPU quota: {e}")
        else:
            # cgroup v1: write to cpu.cfs_quota_us and cpu.cfs_period_us
            cpu_cgroup_path = cgroup_path.replace("/memory/", "/cpu/")
            quota_file = os.path.join(cpu_cgroup_path, "cpu.cfs_quota_us")
            period_file = os.path.join(cpu_cgroup_path, "cpu.cfs_period_us")
            
            try:
                # Set period first
                with open(period_file, 'w') as f:
                    f.write(str(period))
                # Then set quota
                with open(quota_file, 'w') as f:
                    f.write(str(quota))
                self.logger.info(f"Set CPU quota to {cpu_quota*100}% for {cpu_cgroup_path}")
            except (OSError, PermissionError) as e:
                self.logger.warning(f"Failed to set CPU quota: {e}")
    
    def add_process(self, cgroup_path: str, pid: int) -> None:
        """
        Add process to cgroup.
        
        Args:
            cgroup_path: Path to cgroup directory
            pid: Process ID to add
        """
        if self.cgroup_version == 2:
            # cgroup v2: write PID to cgroup.procs
            procs_file = os.path.join(cgroup_path, "cgroup.procs")
        else:
            # cgroup v1: write PID to tasks file in both hierarchies
            procs_file = os.path.join(cgroup_path, "tasks")
        
        try:
            with open(procs_file, 'w') as f:
                f.write(str(pid))
            self.logger.info(f"Added process {pid} to cgroup {cgroup_path}")
            
            # For v1, also add to CPU hierarchy
            if self.cgroup_version == 1:
                cpu_cgroup_path = cgroup_path.replace("/memory/", "/cpu/")
                cpu_procs_file = os.path.join(cpu_cgroup_path, "tasks")
                try:
                    with open(cpu_procs_file, 'w') as f:
                        f.write(str(pid))
                except (OSError, PermissionError):
                    pass
                    
        except (OSError, PermissionError) as e:
            self.logger.warning(f"Failed to add process {pid} to cgroup: {e}")
    
    def remove_cgroup(self, cgroup_path: str) -> None:
        """
        Remove cgroup directory.
        
        Args:
            cgroup_path: Path to cgroup directory
        """
        try:
            # Remove the cgroup directory
            os.rmdir(cgroup_path)
            self.logger.info(f"Removed cgroup {cgroup_path}")
            
            # For v1, also remove CPU hierarchy
            if self.cgroup_version == 1:
                cpu_cgroup_path = cgroup_path.replace("/memory/", "/cpu/")
                try:
                    os.rmdir(cpu_cgroup_path)
                except (OSError, FileNotFoundError):
                    pass
                    
        except (OSError, FileNotFoundError) as e:
            self.logger.warning(f"Failed to remove cgroup {cgroup_path}: {e}")
