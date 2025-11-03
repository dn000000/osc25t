"""Compliance checker engine"""

import os
from typing import List, Optional
from pathlib import Path
from sysaudit.models import ComplianceIssue, Config
from sysaudit.compliance.rules import ComplianceRule


class ComplianceChecker:
    """Main compliance checking engine"""
    
    def __init__(self, config: Config):
        """
        Initialize compliance checker
        
        Args:
            config: System configuration
        """
        self.config = config
        self.rules: List[ComplianceRule] = []
        self._load_rules()
    
    def _load_rules(self):
        """Load all compliance rules"""
        # Import rules here to avoid circular imports
        from sysaudit.compliance.world_writable import WorldWritableRule
        from sysaudit.compliance.suid_sgid import SUIDSGIDRule
        from sysaudit.compliance.weak_permissions import WeakPermissionsRule
        
        self.rules = [
            WorldWritableRule(),
            SUIDSGIDRule(),
            WeakPermissionsRule(),
        ]
    
    def add_rule(self, rule: ComplianceRule):
        """
        Add a custom compliance rule
        
        Args:
            rule: ComplianceRule instance to add
        """
        self.rules.append(rule)
    
    def check_files(self, paths: List[str]) -> List[ComplianceIssue]:
        """
        Run compliance checks on specified files
        
        Args:
            paths: List of file paths to check
            
        Returns:
            List of compliance issues found
        """
        issues = []
        
        for path in paths:
            if not os.path.exists(path):
                continue
            
            # Skip if it's a directory (we check files only)
            if os.path.isdir(path):
                continue
                
            for rule in self.rules:
                if rule.applies_to(path):
                    result = rule.check(path)
                    if result:
                        issues.append(result)
        
        return issues
    
    def check_directory(self, directory: str, recursive: bool = True) -> List[ComplianceIssue]:
        """
        Run compliance checks on all files in a directory
        
        Args:
            directory: Directory path to scan
            recursive: Whether to scan subdirectories
            
        Returns:
            List of compliance issues found
        """
        issues = []
        
        if not os.path.exists(directory):
            return issues
        
        if not os.path.isdir(directory):
            # If it's a file, check it directly
            return self.check_files([directory])
        
        # Scan directory
        if recursive:
            for root, dirs, files in os.walk(directory):
                for file in files:
                    file_path = os.path.join(root, file)
                    issues.extend(self.check_files([file_path]))
        else:
            for item in os.listdir(directory):
                item_path = os.path.join(directory, item)
                if os.path.isfile(item_path):
                    issues.extend(self.check_files([item_path]))
        
        return issues
    
    def scan_all_watched_paths(self) -> List[ComplianceIssue]:
        """
        Scan all configured watch paths for compliance issues
        
        Returns:
            List of all compliance issues found
        """
        all_issues = []
        
        for path in self.config.watch_paths:
            if os.path.isdir(path):
                all_issues.extend(self.check_directory(path, recursive=True))
            elif os.path.isfile(path):
                all_issues.extend(self.check_files([path]))
        
        return all_issues
    
    def get_rule_by_name(self, rule_name: str) -> Optional[ComplianceRule]:
        """
        Get a rule by its name
        
        Args:
            rule_name: Name of the rule to find
            
        Returns:
            ComplianceRule instance or None if not found
        """
        for rule in self.rules:
            if rule.rule_name == rule_name:
                return rule
        return None
    
    def list_rules(self) -> List[str]:
        """
        Get list of all loaded rule names
        
        Returns:
            List of rule names
        """
        return [rule.rule_name for rule in self.rules]
