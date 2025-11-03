"""
State management for GitProc.
Tracks service states and process information.
"""

import json
import os
import tempfile
from dataclasses import dataclass, asdict
from typing import Optional, Dict
from pathlib import Path


@dataclass
class ServiceState:
    """
    Represents the state of a managed service.
    """
    name: str
    status: str  # "running", "stopped", "failed"
    pid: Optional[int] = None
    start_time: Optional[float] = None
    restart_count: int = 0
    last_exit_code: Optional[int] = None


class StateManager:
    """
    Manages service states with persistent storage.
    Implements batched writes to reduce I/O overhead.
    """
    
    def __init__(self, state_file: str):
        """
        Initialize StateManager.
        
        Args:
            state_file: Path to the state JSON file
        """
        self.state_file = state_file
        self.services: Dict[str, ServiceState] = {}
        self._dirty = False  # Track if state has changed since last save
        self._last_save_time = 0.0  # Track last save timestamp
    
    def register_service(self, name: str) -> None:
        """
        Register a new service with default state.
        
        Args:
            name: Service name
        """
        if name not in self.services:
            self.services[name] = ServiceState(
                name=name,
                status="stopped"
            )
            self._dirty = True
    
    def update_state(self, name: str, **kwargs) -> None:
        """
        Update service state with provided fields.
        
        Args:
            name: Service name
            **kwargs: Fields to update (status, pid, start_time, restart_count, last_exit_code)
        """
        if name not in self.services:
            raise KeyError(f"Service '{name}' is not registered")
        
        service = self.services[name]
        
        # Update only provided fields
        if 'status' in kwargs:
            service.status = kwargs['status']
            self._dirty = True
        if 'pid' in kwargs:
            service.pid = kwargs['pid']
            self._dirty = True
        if 'start_time' in kwargs:
            service.start_time = kwargs['start_time']
            self._dirty = True
        if 'restart_count' in kwargs:
            service.restart_count = kwargs['restart_count']
            self._dirty = True
        if 'last_exit_code' in kwargs:
            service.last_exit_code = kwargs['last_exit_code']
            self._dirty = True
    
    def get_state(self, name: str) -> Optional[ServiceState]:
        """
        Retrieve service state.
        
        Args:
            name: Service name
            
        Returns:
            ServiceState object or None if service not registered
        """
        return self.services.get(name)
    
    def save_state(self, force: bool = False) -> None:
        """
        Persist state to JSON file using atomic write with batching.
        
        Uses atomic write pattern: write to temp file, then rename.
        This ensures state file is never corrupted even if process crashes.
        
        Implements batched writes: only writes if state is dirty and either
        force=True or minimum time interval has passed since last save.
        
        Args:
            force: If True, save immediately regardless of dirty flag or time interval
        """
        import time as time_module
        
        current_time = time_module.time()
        min_save_interval = 2.0  # Minimum 2 seconds between saves
        
        # Skip save if not dirty and not forced
        if not force and not self._dirty:
            return
        
        # Skip save if too soon since last save (unless forced)
        if not force and (current_time - self._last_save_time) < min_save_interval:
            return
        
        # Create directory if it doesn't exist
        state_dir = os.path.dirname(self.state_file)
        if state_dir:
            os.makedirs(state_dir, exist_ok=True)
        
        # Prepare state data
        state_data = {
            "services": {
                name: asdict(service)
                for name, service in self.services.items()
            }
        }
        
        # Write to temporary file in same directory
        temp_fd, temp_path = tempfile.mkstemp(
            dir=state_dir if state_dir else None,
            prefix='.state_',
            suffix='.json.tmp'
        )
        
        try:
            with os.fdopen(temp_fd, 'w') as f:
                json.dump(state_data, f, indent=2)
            
            # Atomic rename
            os.replace(temp_path, self.state_file)
            
            # Update tracking variables
            self._dirty = False
            self._last_save_time = current_time
        except Exception:
            # Clean up temp file on error
            try:
                os.unlink(temp_path)
            except OSError:
                pass
            raise
    
    def load_state(self) -> None:
        """
        Restore state from JSON file.
        
        If file doesn't exist, starts with empty state.
        """
        if not os.path.exists(self.state_file):
            return
        
        try:
            with open(self.state_file, 'r') as f:
                state_data = json.load(f)
            
            # Restore services
            if 'services' in state_data:
                for name, service_dict in state_data['services'].items():
                    self.services[name] = ServiceState(**service_dict)
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            # If state file is corrupted, log and start fresh
            # In production, this should log the error
            pass
