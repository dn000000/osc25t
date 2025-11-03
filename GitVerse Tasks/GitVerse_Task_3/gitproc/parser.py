"""
Unit file parser for GitProc.
Parses and validates .service unit files.
"""

import re
from dataclasses import dataclass, field
from typing import Optional, List, Dict


@dataclass
class UnitFile:
    """
    Represents a parsed unit file with all supported directives.
    """
    name: str
    exec_start: str
    restart: str = "no"
    user: Optional[str] = None
    environment: Dict[str, str] = field(default_factory=dict)
    memory_limit: Optional[int] = None  # bytes
    cpu_quota: Optional[float] = None  # 0.0 to 1.0
    health_check_url: Optional[str] = None
    health_check_interval: int = 30
    after: List[str] = field(default_factory=list)



class UnitFileParser:
    """
    Parser for .service unit files.
    """
    
    @staticmethod
    def parse(file_path: str) -> UnitFile:
        """
        Parse a unit file and return a UnitFile object.
        
        Args:
            file_path: Path to the .service file
            
        Returns:
            UnitFile object with parsed directives
            
        Raises:
            FileNotFoundError: If file doesn't exist
            ValueError: If file format is invalid
        """
        with open(file_path, 'r') as f:
            content = f.read()
        
        # Extract service name from filename
        import os
        name = os.path.basename(file_path)
        if name.endswith('.service'):
            name = name[:-8]  # Remove .service extension
        
        # Parse [Service] section
        service_section = UnitFileParser._extract_section(content, 'Service')
        if not service_section:
            raise ValueError("No [Service] section found in unit file")
        
        # Parse directives
        directives = UnitFileParser._parse_directives(service_section)
        
        # Extract required field
        exec_start = directives.get('ExecStart', '')
        if not exec_start:
            raise ValueError("ExecStart directive is required")
        
        # Extract optional fields with defaults
        restart = directives.get('Restart', 'no')
        user = directives.get('User')
        
        # Parse environment variables
        environment = {}
        if 'Environment' in directives:
            env_value = directives['Environment']
            # Support multiple formats: KEY=VALUE or just pass through
            if '=' in env_value:
                parts = env_value.split('=', 1)
                if len(parts) == 2:
                    environment[parts[0]] = parts[1]
        
        # Parse memory limit
        memory_limit = None
        if 'MemoryLimit' in directives:
            memory_limit = UnitFileParser._parse_memory_limit(directives['MemoryLimit'])
        
        # Parse CPU quota
        cpu_quota = None
        if 'CPUQuota' in directives:
            cpu_quota = UnitFileParser._parse_cpu_quota(directives['CPUQuota'])
        
        # Parse health check settings
        health_check_url = directives.get('HealthCheckURL')
        health_check_interval = 30
        if 'HealthCheckInterval' in directives:
            try:
                health_check_interval = int(directives['HealthCheckInterval'])
            except ValueError:
                health_check_interval = 30
        
        # Parse dependencies
        after = []
        if 'After' in directives:
            after_value = directives['After']
            # Support comma-separated or space-separated list
            after = [s.strip() for s in re.split(r'[,\s]+', after_value) if s.strip()]
        
        return UnitFile(
            name=name,
            exec_start=exec_start,
            restart=restart,
            user=user,
            environment=environment,
            memory_limit=memory_limit,
            cpu_quota=cpu_quota,
            health_check_url=health_check_url,
            health_check_interval=health_check_interval,
            after=after
        )
    
    @staticmethod
    def _extract_section(content: str, section_name: str) -> Optional[str]:
        """
        Extract a section from the unit file content.
        
        Args:
            content: Full unit file content
            section_name: Name of section to extract (without brackets)
            
        Returns:
            Section content or None if not found
        """
        pattern = rf'\[{section_name}\](.*?)(?:\[|$)'
        match = re.search(pattern, content, re.DOTALL)
        if match:
            return match.group(1)
        return None
    
    @staticmethod
    def _parse_directives(section_content: str) -> Dict[str, str]:
        """
        Parse directives from a section content.
        
        Args:
            section_content: Content of a section
            
        Returns:
            Dictionary of directive name to value
        """
        directives = {}
        for line in section_content.split('\n'):
            line = line.strip()
            # Skip empty lines and comments
            if not line or line.startswith('#') or line.startswith(';'):
                continue
            
            # Parse KEY=VALUE format
            if '=' in line:
                key, value = line.split('=', 1)
                directives[key.strip()] = value.strip()
        
        return directives
    
    @staticmethod
    def _parse_memory_limit(value: str) -> int:
        """
        Parse memory limit string to bytes.
        
        Args:
            value: Memory limit string (e.g., "100M", "1G", "512K")
            
        Returns:
            Memory limit in bytes
            
        Raises:
            ValueError: If format is invalid
        """
        value = value.strip().upper()
        
        # Extract number and unit
        match = re.match(r'^(\d+(?:\.\d+)?)\s*([KMGT]?)B?$', value)
        if not match:
            raise ValueError(f"Invalid memory limit format: {value}")
        
        number = float(match.group(1))
        unit = match.group(2)
        
        # Convert to bytes
        multipliers = {
            '': 1,
            'K': 1024,
            'M': 1024 ** 2,
            'G': 1024 ** 3,
            'T': 1024 ** 4
        }
        
        return int(number * multipliers[unit])
    
    @staticmethod
    def _parse_cpu_quota(value: str) -> float:
        """
        Parse CPU quota string to float (0.0 to 1.0).
        
        Args:
            value: CPU quota string (e.g., "50%", "0.5")
            
        Returns:
            CPU quota as float (0.0 to 1.0)
            
        Raises:
            ValueError: If format is invalid
        """
        value = value.strip()
        
        # Handle percentage format
        if value.endswith('%'):
            try:
                percentage = float(value[:-1])
                return percentage / 100.0
            except ValueError:
                raise ValueError(f"Invalid CPU quota format: {value}")
        
        # Handle decimal format
        try:
            quota = float(value)
            # If value is > 1, assume it's a percentage without % sign
            if quota > 1:
                return quota / 100.0
            return quota
        except ValueError:
            raise ValueError(f"Invalid CPU quota format: {value}")

    
    @staticmethod
    def validate(unit: UnitFile) -> List[str]:
        """
        Validate a UnitFile object.
        
        Args:
            unit: UnitFile object to validate
            
        Returns:
            List of validation error messages (empty if valid)
        """
        errors = []
        
        # Validate ExecStart is present
        if not unit.exec_start or not unit.exec_start.strip():
            errors.append("ExecStart directive is required and cannot be empty")
        
        # Validate Restart value
        valid_restart_values = ['always', 'on-failure', 'no']
        if unit.restart not in valid_restart_values:
            errors.append(
                f"Restart value '{unit.restart}' is invalid. "
                f"Must be one of: {', '.join(valid_restart_values)}"
            )
        
        # Validate memory limit
        if unit.memory_limit is not None:
            if unit.memory_limit <= 0:
                errors.append("MemoryLimit must be greater than 0")
            # Check for reasonable upper bound (e.g., 1TB)
            if unit.memory_limit > 1024 ** 4:
                errors.append("MemoryLimit exceeds maximum allowed value (1TB)")
        
        # Validate CPU quota
        if unit.cpu_quota is not None:
            if unit.cpu_quota < 0.0:
                errors.append("CPUQuota must be greater than or equal to 0")
            if unit.cpu_quota > 1.0:
                errors.append("CPUQuota must be less than or equal to 100%")
        
        # Validate health check interval
        if unit.health_check_interval <= 0:
            errors.append("HealthCheckInterval must be greater than 0")
        
        return errors
