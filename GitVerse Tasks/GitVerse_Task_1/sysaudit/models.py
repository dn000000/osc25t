"""Data models for the audit system"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List
from pathlib import Path


@dataclass
class ProcessInfo:
    """Information about a process that modified a file"""
    pid: int
    name: str
    cmdline: str
    
    def __post_init__(self):
        """Validate process info"""
        if self.pid < 0:
            raise ValueError(f"Invalid PID: {self.pid}")
        if not self.name:
            raise ValueError("Process name cannot be empty")


@dataclass
class FileEvent:
    """Represents a file system event"""
    path: str
    event_type: str  # 'created', 'modified', 'deleted'
    timestamp: datetime
    process_info: Optional[ProcessInfo] = None
    
    def __post_init__(self):
        """Validate file event"""
        valid_types = {'created', 'modified', 'deleted'}
        if self.event_type not in valid_types:
            raise ValueError(f"Invalid event_type: {self.event_type}. Must be one of {valid_types}")
        if not self.path:
            raise ValueError("File path cannot be empty")
        if not isinstance(self.timestamp, datetime):
            raise ValueError("Timestamp must be a datetime object")


@dataclass
class ComplianceIssue:
    """Represents a compliance/security issue"""
    severity: str  # 'HIGH', 'MEDIUM', 'LOW'
    rule: str
    path: str
    description: str
    recommendation: str
    timestamp: datetime = field(default_factory=datetime.now)
    
    def __post_init__(self):
        """Validate compliance issue"""
        valid_severities = {'HIGH', 'MEDIUM', 'LOW'}
        if self.severity not in valid_severities:
            raise ValueError(f"Invalid severity: {self.severity}. Must be one of {valid_severities}")
        if not self.rule:
            raise ValueError("Rule name cannot be empty")
        if not self.path:
            raise ValueError("File path cannot be empty")
        if not self.description:
            raise ValueError("Description cannot be empty")


@dataclass
class FileChange:
    """Represents a change to a file detected during drift analysis"""
    path: str
    change_type: str  # 'added', 'modified', 'deleted'
    severity: str  # 'HIGH', 'MEDIUM', 'LOW'
    
    def __post_init__(self):
        """Validate file change"""
        valid_types = {'added', 'modified', 'deleted'}
        if self.change_type not in valid_types:
            raise ValueError(f"Invalid change_type: {self.change_type}. Must be one of {valid_types}")
        valid_severities = {'HIGH', 'MEDIUM', 'LOW'}
        if self.severity not in valid_severities:
            raise ValueError(f"Invalid severity: {self.severity}. Must be one of {valid_severities}")
        if not self.path:
            raise ValueError("File path cannot be empty")


@dataclass
class DriftReport:
    """Report of drift from baseline"""
    baseline: str
    changes: List[FileChange]
    timestamp: datetime
    
    def __post_init__(self):
        """Validate drift report"""
        if not self.baseline:
            raise ValueError("Baseline cannot be empty")
        if not isinstance(self.changes, list):
            raise ValueError("Changes must be a list")
        if not isinstance(self.timestamp, datetime):
            raise ValueError("Timestamp must be a datetime object")
    
    def get_high_severity_changes(self) -> List[FileChange]:
        """Get only high severity changes"""
        return [c for c in self.changes if c.severity == 'HIGH']
    
    def get_changes_by_type(self, change_type: str) -> List[FileChange]:
        """Get changes filtered by type"""
        return [c for c in self.changes if c.change_type == change_type]


@dataclass
class Config:
    """Configuration for the audit system"""
    repo_path: str
    watch_paths: List[str]
    baseline_branch: str = 'main'
    blacklist_file: Optional[str] = None
    whitelist_file: Optional[str] = None
    auto_compliance: bool = False
    gpg_sign: bool = False
    webhook_url: Optional[str] = None
    batch_interval: int = 5  # seconds
    batch_size: int = 10
    
    def __post_init__(self):
        """Validate configuration"""
        if not self.repo_path:
            raise ValueError("Repository path cannot be empty")
        if not self.watch_paths:
            raise ValueError("At least one watch path must be specified")
        if not isinstance(self.watch_paths, list):
            raise ValueError("Watch paths must be a list")
        if self.batch_interval <= 0:
            raise ValueError("Batch interval must be positive")
        if self.batch_size <= 0:
            raise ValueError("Batch size must be positive")
        if not self.baseline_branch:
            raise ValueError("Baseline branch cannot be empty")
    
    def validate_paths(self) -> bool:
        """Validate that watch paths exist"""
        for path in self.watch_paths:
            if not Path(path).exists():
                return False
        return True
    
    @classmethod
    def from_yaml(cls, config_file: str) -> 'Config':
        """
        Load configuration from YAML file.
        
        Args:
            config_file: Path to YAML configuration file
            
        Returns:
            Config object
        """
        from .config import ConfigManager
        return ConfigManager.load_config(config_file=config_file)
