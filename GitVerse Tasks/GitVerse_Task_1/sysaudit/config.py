"""Configuration management for the audit system"""

import os
import yaml
from pathlib import Path
from typing import Optional, Dict, Any, List
from .models import Config


class ConfigManager:
    """Manages configuration loading and merging from files and CLI arguments"""
    
    DEFAULT_CONFIG = {
        'repository': {
            'path': '/var/lib/sysaudit',
            'baseline': 'main',
            'gpg_sign': False,
        },
        'monitoring': {
            'paths': [],  # Must be provided by user
            'blacklist_file': None,
            'whitelist_file': None,
            'batch_interval': 5,
            'batch_size': 10,
        },
        'compliance': {
            'auto_check': False,
        },
        'alerts': {
            'enabled': True,
            'webhook_url': None,
        }
    }
    
    @classmethod
    def load_config(
        cls,
        config_file: Optional[str] = None,
        cli_overrides: Optional[Dict[str, Any]] = None
    ) -> Config:
        """
        Load configuration from file and apply CLI overrides.
        
        Args:
            config_file: Path to YAML config file (optional)
            cli_overrides: Dictionary of CLI argument overrides (optional)
            
        Returns:
            Config object with merged configuration
            
        Raises:
            ValueError: If configuration is invalid
            FileNotFoundError: If config file doesn't exist
        """
        # Start with defaults
        config_dict = cls._deep_copy_dict(cls.DEFAULT_CONFIG)
        
        # Load from file if provided
        if config_file:
            file_config = cls._load_yaml_file(config_file)
            config_dict = cls._merge_dicts(config_dict, file_config)
        
        # Apply CLI overrides
        if cli_overrides:
            config_dict = cls._apply_cli_overrides(config_dict, cli_overrides)
        
        # Convert to Config object
        return cls._dict_to_config(config_dict)
    
    @classmethod
    def _load_yaml_file(cls, filepath: str) -> Dict[str, Any]:
        """Load YAML configuration file"""
        path = Path(filepath)
        
        if not path.exists():
            raise FileNotFoundError(f"Configuration file not found: {filepath}")
        
        if not path.is_file():
            raise ValueError(f"Configuration path is not a file: {filepath}")
        
        try:
            with open(path, 'r') as f:
                config = yaml.safe_load(f)
                
            if config is None:
                return {}
                
            if not isinstance(config, dict):
                raise ValueError(f"Configuration file must contain a YAML dictionary")
                
            return config
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in configuration file: {e}")
    
    @classmethod
    def _merge_dicts(cls, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge two dictionaries"""
        result = base.copy()
        
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = cls._merge_dicts(result[key], value)
            else:
                result[key] = value
                
        return result
    
    @classmethod
    def _apply_cli_overrides(cls, config: Dict[str, Any], overrides: Dict[str, Any]) -> Dict[str, Any]:
        """Apply CLI argument overrides to configuration"""
        result = config.copy()
        
        # Map CLI arguments to config structure
        cli_mapping = {
            'repo_path': ('repository', 'path'),
            'baseline': ('repository', 'baseline'),
            'watch_paths': ('monitoring', 'paths'),
            'blacklist_file': ('monitoring', 'blacklist_file'),
            'whitelist_file': ('monitoring', 'whitelist_file'),
            'batch_interval': ('monitoring', 'batch_interval'),
            'batch_size': ('monitoring', 'batch_size'),
            'auto_compliance': ('compliance', 'auto_check'),
            'gpg_sign': ('repository', 'gpg_sign'),
            'webhook_url': ('alerts', 'webhook_url'),
        }
        
        for cli_key, value in overrides.items():
            if value is None:
                continue
                
            if cli_key in cli_mapping:
                section, config_key = cli_mapping[cli_key]
                if section not in result:
                    result[section] = {}
                result[section][config_key] = value
        
        return result
    
    @classmethod
    def _dict_to_config(cls, config_dict: Dict[str, Any]) -> Config:
        """Convert configuration dictionary to Config object"""
        repo = config_dict.get('repository', {})
        monitoring = config_dict.get('monitoring', {})
        compliance = config_dict.get('compliance', {})
        alerts = config_dict.get('alerts', {})
        
        # Extract watch paths
        watch_paths = monitoring.get('paths', [])
        
        # Ensure watch_paths is a list
        if isinstance(watch_paths, str):
            watch_paths = [watch_paths]
        elif not isinstance(watch_paths, list):
            watch_paths = []
        
        # If no watch paths provided, use current directory as default
        if not watch_paths:
            watch_paths = [os.getcwd()]
        
        # Expand paths
        watch_paths = [os.path.expanduser(os.path.expandvars(p)) for p in watch_paths]
        
        # Expand repo path
        repo_path = os.path.expanduser(os.path.expandvars(repo.get('path', '/var/lib/sysaudit')))
        
        # Expand blacklist/whitelist files if provided
        blacklist_file = monitoring.get('blacklist_file')
        if blacklist_file:
            blacklist_file = os.path.expanduser(os.path.expandvars(blacklist_file))
        
        whitelist_file = monitoring.get('whitelist_file')
        if whitelist_file:
            whitelist_file = os.path.expanduser(os.path.expandvars(whitelist_file))
        
        return Config(
            repo_path=repo_path,
            watch_paths=watch_paths,
            baseline_branch=repo.get('baseline', 'main'),
            blacklist_file=blacklist_file,
            whitelist_file=whitelist_file,
            auto_compliance=compliance.get('auto_check', False),
            gpg_sign=repo.get('gpg_sign', False),
            webhook_url=alerts.get('webhook_url'),
            batch_interval=monitoring.get('batch_interval', 5),
            batch_size=monitoring.get('batch_size', 10),
        )
    
    @classmethod
    def _deep_copy_dict(cls, d: Dict[str, Any]) -> Dict[str, Any]:
        """Deep copy a dictionary"""
        result = {}
        for key, value in d.items():
            if isinstance(value, dict):
                result[key] = cls._deep_copy_dict(value)
            elif isinstance(value, list):
                result[key] = value.copy()
            else:
                result[key] = value
        return result
    
    @classmethod
    def create_default_config_file(cls, filepath: str) -> None:
        """Create a default configuration file"""
        config_template = """# System Audit Configuration File

repository:
  # Path where the audit Git repository will be stored
  path: /var/lib/sysaudit
  
  # Baseline branch name for drift detection
  baseline: main
  
  # Enable GPG signing of commits (requires GPG setup)
  gpg_sign: false

monitoring:
  # Paths to monitor for changes (can be multiple)
  paths:
    - /etc
    - /usr/local/bin
  
  # Optional: Path to blacklist file (patterns to ignore)
  blacklist_file: /etc/sysaudit/blacklist.txt
  
  # Optional: Path to whitelist file (only monitor these patterns)
  whitelist_file: null
  
  # Batch events within this interval (seconds)
  batch_interval: 5
  
  # Maximum number of events per batch
  batch_size: 10

compliance:
  # Automatically run compliance checks on file changes
  auto_check: false

alerts:
  # Enable alert system
  enabled: true
  
  # Optional: Webhook URL for alerts
  webhook_url: null
"""
        
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            f.write(config_template)
    
    @classmethod
    def create_default_blacklist_file(cls, filepath: str) -> None:
        """Create a default blacklist file with common ignore patterns"""
        blacklist_template = """# System Audit Blacklist Patterns
# Files matching these patterns will be ignored during monitoring
# Supports glob patterns (* and ?)

# Temporary files
*.tmp
*.swp
*.swo
*~
*.bak
*.backup

# Log files
*.log
*.log.*

# Python cache
*.pyc
*.pyo
__pycache__/*
*.egg-info/*

# Git directory
.git/*
.gitignore

# Editor files
.*.sw?
.vscode/*
.idea/*
*.sublime-*

# System files
.DS_Store
Thumbs.db

# Lock files
*.lock
.*.lock

# Package manager caches
node_modules/*
.npm/*
.cache/*

# Build artifacts
*.o
*.so
*.a
*.out
dist/*
build/*

# Temporary directories
/tmp/*
/var/tmp/*
/var/cache/*
"""
        
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, 'w') as f:
            f.write(blacklist_template)
