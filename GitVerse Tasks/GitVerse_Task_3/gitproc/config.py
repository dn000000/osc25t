"""
Configuration management for GitProc.
Loads and manages configuration from config.json file.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional
from pathlib import Path


@dataclass
class Config:
    """Configuration for GitProc daemon and services."""
    
    repo_path: str = "/etc/gitproc/services"
    branch: str = "main"
    socket_path: str = "/var/run/gitproc.sock"
    state_file: str = "/var/lib/gitproc/state.json"
    log_dir: str = "/var/log/gitproc"
    cgroup_root: str = "/sys/fs/cgroup/gitproc"
    
    @classmethod
    def load(cls, config_path: str) -> "Config":
        """
        Load configuration from JSON file.
        
        Args:
            config_path: Path to config.json file
            
        Returns:
            Config object with loaded settings
            
        Raises:
            FileNotFoundError: If config file doesn't exist
            json.JSONDecodeError: If config file is invalid JSON
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
        
        with open(config_path, 'r') as f:
            data = json.load(f)
        
        return cls(**data)
    
    @classmethod
    def load_or_default(cls, config_path: str) -> "Config":
        """
        Load configuration from file, or return default if file doesn't exist.
        
        Args:
            config_path: Path to config.json file
            
        Returns:
            Config object with loaded or default settings
        """
        try:
            return cls.load(config_path)
        except FileNotFoundError:
            return cls()
    
    def save(self, config_path: str) -> None:
        """
        Save configuration to JSON file.
        
        Args:
            config_path: Path to config.json file
        """
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(config_path), exist_ok=True)
        
        with open(config_path, 'w') as f:
            json.dump(asdict(self), f, indent=2)
    
    def ensure_directories(self) -> None:
        """
        Create all necessary directories if they don't exist.
        """
        directories = [
            self.log_dir,
            os.path.dirname(self.state_file),
            os.path.dirname(self.socket_path),
        ]
        
        for directory in directories:
            if directory:  # Skip empty strings
                os.makedirs(directory, exist_ok=True)
