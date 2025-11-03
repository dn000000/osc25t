"""Base compliance rule architecture"""

from abc import ABC, abstractmethod
from typing import Optional
from sysaudit.models import ComplianceIssue


class ComplianceRule(ABC):
    """Abstract base class for compliance rules"""
    
    @abstractmethod
    def applies_to(self, path: str) -> bool:
        """
        Check if this rule applies to the given file path
        
        Args:
            path: File path to check
            
        Returns:
            True if rule should be applied to this path
        """
        pass
    
    @abstractmethod
    def check(self, path: str) -> Optional[ComplianceIssue]:
        """
        Check the file for compliance issues
        
        Args:
            path: File path to check
            
        Returns:
            ComplianceIssue if a problem is found, None otherwise
        """
        pass
    
    @property
    @abstractmethod
    def rule_name(self) -> str:
        """Return the name of this rule"""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Return a description of what this rule checks"""
        pass
