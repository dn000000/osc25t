"""
Tests for StateManager class.
"""

import json
import os
import tempfile
import pytest
from gitproc.state_manager import ServiceState, StateManager


def test_service_state_creation():
    """Test ServiceState dataclass creation."""
    state = ServiceState(
        name="test-service",
        status="running",
        pid=12345,
        start_time=1698765432.123,
        restart_count=2,
        last_exit_code=None
    )
    
    assert state.name == "test-service"
    assert state.status == "running"
    assert state.pid == 12345
    assert state.start_time == 1698765432.123
    assert state.restart_count == 2
    assert state.last_exit_code is None


def test_service_state_defaults():
    """Test ServiceState default values."""
    state = ServiceState(name="test", status="stopped")
    
    assert state.name == "test"
    assert state.status == "stopped"
    assert state.pid is None
    assert state.start_time is None
    assert state.restart_count == 0
    assert state.last_exit_code is None


def test_register_service():
    """Test service registration."""
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        state_file = f.name
    
    try:
        manager = StateManager(state_file)
        manager.register_service("nginx")
        
        state = manager.get_state("nginx")
        assert state is not None
        assert state.name == "nginx"
        assert state.status == "stopped"
        assert state.pid is None
    finally:
        if os.path.exists(state_file):
            os.unlink(state_file)


def test_register_service_idempotent():
    """Test that registering same service twice doesn't overwrite."""
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        state_file = f.name
    
    try:
        manager = StateManager(state_file)
        manager.register_service("nginx")
        manager.update_state("nginx", status="running", pid=123)
        
        # Register again
        manager.register_service("nginx")
        
        # State should be unchanged
        state = manager.get_state("nginx")
        assert state.status == "running"
        assert state.pid == 123
    finally:
        if os.path.exists(state_file):
            os.unlink(state_file)


def test_update_state():
    """Test state updates."""
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        state_file = f.name
    
    try:
        manager = StateManager(state_file)
        manager.register_service("app")
        
        # Update status and pid
        manager.update_state("app", status="running", pid=9999)
        state = manager.get_state("app")
        assert state.status == "running"
        assert state.pid == 9999
        
        # Update restart count
        manager.update_state("app", restart_count=5)
        state = manager.get_state("app")
        assert state.restart_count == 5
        assert state.status == "running"  # Other fields unchanged
    finally:
        if os.path.exists(state_file):
            os.unlink(state_file)


def test_update_state_unregistered_service():
    """Test updating unregistered service raises error."""
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        state_file = f.name
    
    try:
        manager = StateManager(state_file)
        
        with pytest.raises(KeyError):
            manager.update_state("nonexistent", status="running")
    finally:
        if os.path.exists(state_file):
            os.unlink(state_file)


def test_get_state_nonexistent():
    """Test getting state of nonexistent service returns None."""
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        state_file = f.name
    
    try:
        manager = StateManager(state_file)
        state = manager.get_state("nonexistent")
        assert state is None
    finally:
        if os.path.exists(state_file):
            os.unlink(state_file)


def test_save_and_load_state():
    """Test state persistence and loading."""
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as f:
        state_file = f.name
    
    try:
        # Create and save state
        manager1 = StateManager(state_file)
        manager1.register_service("nginx")
        manager1.update_state("nginx", status="running", pid=12345, start_time=1698765432.0)
        manager1.register_service("app")
        manager1.update_state("app", status="stopped", restart_count=3, last_exit_code=1)
        manager1.save_state()
        
        # Load state in new manager
        manager2 = StateManager(state_file)
        manager2.load_state()
        
        # Verify nginx state
        nginx_state = manager2.get_state("nginx")
        assert nginx_state is not None
        assert nginx_state.name == "nginx"
        assert nginx_state.status == "running"
        assert nginx_state.pid == 12345
        assert nginx_state.start_time == 1698765432.0
        
        # Verify app state
        app_state = manager2.get_state("app")
        assert app_state is not None
        assert app_state.name == "app"
        assert app_state.status == "stopped"
        assert app_state.restart_count == 3
        assert app_state.last_exit_code == 1
    finally:
        if os.path.exists(state_file):
            os.unlink(state_file)


def test_load_state_missing_file():
    """Test loading state when file doesn't exist."""
    with tempfile.NamedTemporaryFile(suffix='.json', delete=True) as f:
        state_file = f.name
    
    # File doesn't exist
    manager = StateManager(state_file)
    manager.load_state()  # Should not raise error
    
    assert len(manager.services) == 0


def test_save_state_atomic_write():
    """Test that save_state uses atomic write."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = os.path.join(tmpdir, "state.json")
        
        manager = StateManager(state_file)
        manager.register_service("test")
        manager.update_state("test", status="running", pid=123)
        manager.save_state()
        
        # Verify file exists and is valid JSON
        assert os.path.exists(state_file)
        with open(state_file, 'r') as f:
            data = json.load(f)
        
        assert "services" in data
        assert "test" in data["services"]
        assert data["services"]["test"]["pid"] == 123


def test_save_state_creates_directory():
    """Test that save_state creates directory if it doesn't exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        state_file = os.path.join(tmpdir, "subdir", "state.json")
        
        manager = StateManager(state_file)
        manager.register_service("test")
        manager.save_state()
        
        assert os.path.exists(state_file)
