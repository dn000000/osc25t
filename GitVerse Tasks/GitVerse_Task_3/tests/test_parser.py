"""
Tests for UnitFileParser.
"""

import os
import tempfile
import pytest
from gitproc.parser import UnitFile, UnitFileParser


class TestUnitFileParser:
    """Tests for parsing unit files."""
    
    def test_parse_valid_unit_file_with_all_directives(self):
        """Test parsing a valid unit file with all supported directives."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.service', delete=False) as f:
            f.write("""[Service]
ExecStart=/usr/bin/python3 -m http.server 8080
Restart=always
User=nobody
Environment=PORT=8080
MemoryLimit=100M
CPUQuota=50%
HealthCheckURL=http://localhost:8080
HealthCheckInterval=30
After=network.service database.service
""")
            unit_path = f.name
        
        try:
            unit = UnitFileParser.parse(unit_path)
            
            assert unit.name == os.path.basename(unit_path)[:-8]  # Remove .service
            assert unit.exec_start == "/usr/bin/python3 -m http.server 8080"
            assert unit.restart == "always"
            assert unit.user == "nobody"
            assert unit.environment == {"PORT": "8080"}
            assert unit.memory_limit == 100 * 1024 * 1024  # 100MB in bytes
            assert unit.cpu_quota == 0.5
            assert unit.health_check_url == "http://localhost:8080"
            assert unit.health_check_interval == 30
            assert unit.after == ["network.service", "database.service"]
        finally:
            os.unlink(unit_path)
    
    def test_parse_minimal_unit_file(self):
        """Test parsing a minimal unit file with only ExecStart."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.service', delete=False) as f:
            f.write("""[Service]
ExecStart=/bin/sleep 60
""")
            unit_path = f.name
        
        try:
            unit = UnitFileParser.parse(unit_path)
            
            assert unit.exec_start == "/bin/sleep 60"
            assert unit.restart == "no"  # Default value
            assert unit.user is None
            assert unit.environment == {}
            assert unit.memory_limit is None
            assert unit.cpu_quota is None
            assert unit.health_check_url is None
            assert unit.health_check_interval == 30  # Default value
            assert unit.after == []
        finally:
            os.unlink(unit_path)
    
    def test_parse_missing_service_section(self):
        """Test that parsing fails when [Service] section is missing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.service', delete=False) as f:
            f.write("""[Unit]
Description=Test service
""")
            unit_path = f.name
        
        try:
            with pytest.raises(ValueError, match="No \\[Service\\] section found"):
                UnitFileParser.parse(unit_path)
        finally:
            os.unlink(unit_path)
    
    def test_parse_missing_exec_start(self):
        """Test that parsing fails when ExecStart is missing."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.service', delete=False) as f:
            f.write("""[Service]
Restart=always
""")
            unit_path = f.name
        
        try:
            with pytest.raises(ValueError, match="ExecStart directive is required"):
                UnitFileParser.parse(unit_path)
        finally:
            os.unlink(unit_path)
    
    def test_parse_memory_limit_megabytes(self):
        """Test parsing memory limit in megabytes."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.service', delete=False) as f:
            f.write("""[Service]
ExecStart=/bin/true
MemoryLimit=100M
""")
            unit_path = f.name
        
        try:
            unit = UnitFileParser.parse(unit_path)
            assert unit.memory_limit == 100 * 1024 * 1024
        finally:
            os.unlink(unit_path)
    
    def test_parse_memory_limit_gigabytes(self):
        """Test parsing memory limit in gigabytes."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.service', delete=False) as f:
            f.write("""[Service]
ExecStart=/bin/true
MemoryLimit=1G
""")
            unit_path = f.name
        
        try:
            unit = UnitFileParser.parse(unit_path)
            assert unit.memory_limit == 1024 * 1024 * 1024
        finally:
            os.unlink(unit_path)
    
    def test_parse_memory_limit_kilobytes(self):
        """Test parsing memory limit in kilobytes."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.service', delete=False) as f:
            f.write("""[Service]
ExecStart=/bin/true
MemoryLimit=512K
""")
            unit_path = f.name
        
        try:
            unit = UnitFileParser.parse(unit_path)
            assert unit.memory_limit == 512 * 1024
        finally:
            os.unlink(unit_path)
    
    def test_parse_memory_limit_bytes(self):
        """Test parsing memory limit in bytes (no unit)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.service', delete=False) as f:
            f.write("""[Service]
ExecStart=/bin/true
MemoryLimit=1048576
""")
            unit_path = f.name
        
        try:
            unit = UnitFileParser.parse(unit_path)
            assert unit.memory_limit == 1048576
        finally:
            os.unlink(unit_path)
    
    def test_parse_cpu_quota_percentage(self):
        """Test parsing CPU quota as percentage."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.service', delete=False) as f:
            f.write("""[Service]
ExecStart=/bin/true
CPUQuota=50%
""")
            unit_path = f.name
        
        try:
            unit = UnitFileParser.parse(unit_path)
            assert unit.cpu_quota == 0.5
        finally:
            os.unlink(unit_path)
    
    def test_parse_cpu_quota_decimal(self):
        """Test parsing CPU quota as decimal."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.service', delete=False) as f:
            f.write("""[Service]
ExecStart=/bin/true
CPUQuota=0.75
""")
            unit_path = f.name
        
        try:
            unit = UnitFileParser.parse(unit_path)
            assert unit.cpu_quota == 0.75
        finally:
            os.unlink(unit_path)
    
    def test_parse_cpu_quota_number_without_percent(self):
        """Test parsing CPU quota as number > 1 (treated as percentage)."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.service', delete=False) as f:
            f.write("""[Service]
ExecStart=/bin/true
CPUQuota=25
""")
            unit_path = f.name
        
        try:
            unit = UnitFileParser.parse(unit_path)
            assert unit.cpu_quota == 0.25
        finally:
            os.unlink(unit_path)


class TestUnitFileValidation:
    """Tests for validating unit files."""
    
    def test_validate_valid_unit(self):
        """Test that a valid unit passes validation."""
        unit = UnitFile(
            name="test",
            exec_start="/bin/true",
            restart="always",
            memory_limit=100 * 1024 * 1024,
            cpu_quota=0.5
        )
        
        errors = UnitFileParser.validate(unit)
        assert errors == []
    
    def test_validate_missing_exec_start(self):
        """Test validation error for missing ExecStart."""
        unit = UnitFile(
            name="test",
            exec_start=""
        )
        
        errors = UnitFileParser.validate(unit)
        assert len(errors) == 1
        assert "ExecStart directive is required" in errors[0]
    
    def test_validate_invalid_restart_value(self):
        """Test validation error for invalid Restart value."""
        unit = UnitFile(
            name="test",
            exec_start="/bin/true",
            restart="invalid-value"
        )
        
        errors = UnitFileParser.validate(unit)
        assert len(errors) == 1
        assert "Restart value 'invalid-value' is invalid" in errors[0]
        assert "always" in errors[0]
        assert "on-failure" in errors[0]
        assert "no" in errors[0]
    
    def test_validate_valid_restart_values(self):
        """Test that all valid restart values pass validation."""
        for restart_value in ["always", "on-failure", "no"]:
            unit = UnitFile(
                name="test",
                exec_start="/bin/true",
                restart=restart_value
            )
            
            errors = UnitFileParser.validate(unit)
            assert errors == []
    
    def test_validate_negative_memory_limit(self):
        """Test validation error for negative memory limit."""
        unit = UnitFile(
            name="test",
            exec_start="/bin/true",
            memory_limit=-100
        )
        
        errors = UnitFileParser.validate(unit)
        assert len(errors) == 1
        assert "MemoryLimit must be greater than 0" in errors[0]
    
    def test_validate_excessive_memory_limit(self):
        """Test validation error for excessive memory limit."""
        unit = UnitFile(
            name="test",
            exec_start="/bin/true",
            memory_limit=2 * 1024 ** 4  # 2TB
        )
        
        errors = UnitFileParser.validate(unit)
        assert len(errors) == 1
        assert "MemoryLimit exceeds maximum" in errors[0]
    
    def test_validate_negative_cpu_quota(self):
        """Test validation error for negative CPU quota."""
        unit = UnitFile(
            name="test",
            exec_start="/bin/true",
            cpu_quota=-0.5
        )
        
        errors = UnitFileParser.validate(unit)
        assert len(errors) == 1
        assert "CPUQuota must be greater than or equal to 0" in errors[0]
    
    def test_validate_excessive_cpu_quota(self):
        """Test validation error for CPU quota > 100%."""
        unit = UnitFile(
            name="test",
            exec_start="/bin/true",
            cpu_quota=1.5
        )
        
        errors = UnitFileParser.validate(unit)
        assert len(errors) == 1
        assert "CPUQuota must be less than or equal to 100%" in errors[0]
    
    def test_validate_multiple_errors(self):
        """Test that multiple validation errors are reported."""
        unit = UnitFile(
            name="test",
            exec_start="",
            restart="bad-value",
            memory_limit=-100,
            cpu_quota=2.0
        )
        
        errors = UnitFileParser.validate(unit)
        assert len(errors) == 4
