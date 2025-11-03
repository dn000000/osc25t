"""Git integration module"""

from .manager import GitManager, GitManagerError
from .drift import DriftDetector, DriftDetectorError
from .severity import SeverityScorer
from .rollback import RollbackManager, RollbackError

__all__ = [
    'GitManager',
    'GitManagerError',
    'DriftDetector',
    'DriftDetectorError',
    'SeverityScorer',
    'RollbackManager',
    'RollbackError'
]
