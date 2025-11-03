"""
Tests for ResourceController class.
"""

import os
import tempfile
import pytest
from unittest.mock import Mock, patch, mock_open, MagicMock
from gitproc.resource_controller import ResourceController


class TestResourceControllerInit:
    """Tests for ResourceController initialization."""
    
    def test_init_default_cgroup_root(self):
        """Test initialization with default cgroup root."""
        controller = ResourceController()
        assert controller.cgroup_root == "/sys/fs/cgroup"
    
    def test_init_custom_cgroup_root(self):
        """Test initialization with custom cgroup root."""
        controller = ResourceController(cgroup_root="/custom/cgroup")
        assert controller.cgroup_root == "/custom/cgroup"
    
    @patch('os.path.exists')
    def test_detect_cgroup_v2(self, mock_exists):
        """Test detection of cgroup v2."""
        # Mock cgroup v2 detection
        def exists_side_effect(path):
            return path == "/sys/fs/cgroup/cgroup.controllers"
        
        mock_exists.side_effect = exists_side_effect
        controller = ResourceController()
        assert controller.cgroup_version == 2
    
    @patch('os.path.exists')
    def test_detect_cgroup_v1(self, mock_exists):
        """Test detection of cgroup v1."""
        # Mock cgroup v1 detection
        def exists_side_effect(path):
            if path == "/sys/fs/cgroup/cgroup.controllers":
                return False
            elif path == "/sys/fs/cgroup/memory":
                return True
            return False
        
        mock_exists.side_effect = exists_side_effect
        controller = ResourceController()
        assert controller.cgroup_version == 1


class TestCgroupCreation:
    """Tests for cgroup creation."""
    
    @patch('os.makedirs')
    @patch('os.path.exists')
    def test_create_cgroup_v2_success(self, mock_exists, mock_makedirs):
        """Test successful cgroup creation for v2."""
        mock_exists.return_value = True
        
        with patch.object(ResourceController, '_detect_cgroup_version', return_value=2):
            controller = ResourceController()
            
            with patch.object(controller, '_enable_controllers_v2'):
                cgroup_path = controller.create_cgroup("test-service")
        
        expected_path = os.path.join("/sys/fs/cgroup", "gitproc", "test-service")
        assert cgroup_path == expected_path
        assert mock_makedirs.call_count == 2  # Parent and service directories
    
    @patch('os.makedirs')
    @patch('os.path.exists')
    def test_create_cgroup_v1_success(self, mock_exists, mock_makedirs):
        """Test successful cgroup creation for v1."""
        mock_exists.return_value = False
        
        with patch.object(ResourceController, '_detect_cgroup_version', return_value=1):
            controller = ResourceController()
            cgroup_path = controller.create_cgroup("test-service")
        
        expected_path = os.path.join("/sys/fs/cgroup", "memory", "gitproc", "test-service")
        assert cgroup_path == expected_path
        assert mock_makedirs.call_count == 2  # Memory and CPU hierarchies
    
    @patch('os.makedirs')
    @patch('os.path.exists')
    def test_create_cgroup_with_memory_limit(self, mock_exists, mock_makedirs):
        """Test cgroup creation with memory limit."""
        mock_exists.return_value = True
        
        with patch.object(ResourceController, '_detect_cgroup_version', return_value=2):
            controller = ResourceController()
            
            with patch.object(controller, '_enable_controllers_v2'):
                with patch.object(controller, '_set_memory_limit') as mock_set_memory:
                    cgroup_path = controller.create_cgroup(
                        "test-service",
                        memory_limit=100 * 1024 * 1024
                    )
        
        mock_set_memory.assert_called_once_with(cgroup_path, 100 * 1024 * 1024)
    
    @patch('os.makedirs')
    @patch('os.path.exists')
    def test_create_cgroup_with_cpu_quota(self, mock_exists, mock_makedirs):
        """Test cgroup creation with CPU quota."""
        mock_exists.return_value = True
        
        with patch.object(ResourceController, '_detect_cgroup_version', return_value=2):
            controller = ResourceController()
            
            with patch.object(controller, '_enable_controllers_v2'):
                with patch.object(controller, '_set_cpu_quota') as mock_set_cpu:
                    cgroup_path = controller.create_cgroup(
                        "test-service",
                        cpu_quota=0.5
                    )
        
        mock_set_cpu.assert_called_once_with(cgroup_path, 0.5)
    
    @patch('os.makedirs')
    @patch('os.path.exists')
    def test_create_cgroup_failure_returns_none(self, mock_exists, mock_makedirs):
        """Test that cgroup creation failure returns None."""
        mock_exists.return_value = True
        mock_makedirs.side_effect = PermissionError("Access denied")
        
        with patch.object(ResourceController, '_detect_cgroup_version', return_value=2):
            controller = ResourceController()
            cgroup_path = controller.create_cgroup("test-service")
        
        assert cgroup_path is None


class TestMemoryLimitSetting:
    """Tests for memory limit setting."""
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_set_memory_limit_v2(self, mock_exists, mock_file):
        """Test setting memory limit for cgroup v2."""
        mock_exists.return_value = True
        
        with patch.object(ResourceController, '_detect_cgroup_version', return_value=2):
            controller = ResourceController()
            cgroup_path = os.path.join("/sys/fs/cgroup", "gitproc", "test")
            controller._set_memory_limit(cgroup_path, 100 * 1024 * 1024)
        
        expected_file = os.path.join(cgroup_path, "memory.max")
        mock_file.assert_called_once_with(expected_file, 'w')
        mock_file().write.assert_called_once_with(str(100 * 1024 * 1024))
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_set_memory_limit_v1(self, mock_exists, mock_file):
        """Test setting memory limit for cgroup v1."""
        mock_exists.return_value = False
        
        with patch.object(ResourceController, '_detect_cgroup_version', return_value=1):
            controller = ResourceController()
            cgroup_path = os.path.join("/sys/fs/cgroup", "memory", "gitproc", "test")
            controller._set_memory_limit(cgroup_path, 200 * 1024 * 1024)
        
        expected_file = os.path.join(cgroup_path, "memory.limit_in_bytes")
        mock_file.assert_called_once_with(expected_file, 'w')
        mock_file().write.assert_called_once_with(str(200 * 1024 * 1024))
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_set_memory_limit_permission_error(self, mock_exists, mock_file):
        """Test that permission errors are handled gracefully."""
        mock_exists.return_value = True
        mock_file.side_effect = PermissionError("Access denied")
        
        with patch.object(ResourceController, '_detect_cgroup_version', return_value=2):
            controller = ResourceController()
            # Should not raise exception
            controller._set_memory_limit("/sys/fs/cgroup/gitproc/test", 100 * 1024 * 1024)


class TestCPUQuotaSetting:
    """Tests for CPU quota setting."""
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_set_cpu_quota_v2(self, mock_exists, mock_file):
        """Test setting CPU quota for cgroup v2."""
        mock_exists.return_value = True
        
        with patch.object(ResourceController, '_detect_cgroup_version', return_value=2):
            controller = ResourceController()
            cgroup_path = os.path.join("/sys/fs/cgroup", "gitproc", "test")
            controller._set_cpu_quota(cgroup_path, 0.5)
        
        expected_file = os.path.join(cgroup_path, "cpu.max")
        mock_file.assert_called_once_with(expected_file, 'w')
        # 50% = 50000/100000
        mock_file().write.assert_called_once_with("50000 100000")
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_set_cpu_quota_v1(self, mock_exists, mock_file):
        """Test setting CPU quota for cgroup v1."""
        mock_exists.return_value = False
        
        with patch.object(ResourceController, '_detect_cgroup_version', return_value=1):
            controller = ResourceController()
            cgroup_path = os.path.join("/sys/fs/cgroup", "memory", "gitproc", "test")
            controller._set_cpu_quota(cgroup_path, 0.75)
        
        # Should write to both period and quota files
        assert mock_file.call_count == 2
        
        # Check that period file is written first
        calls = mock_file.call_args_list
        assert "cpu.cfs_period_us" in calls[0][0][0]
        assert "cpu.cfs_quota_us" in calls[1][0][0]
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_set_cpu_quota_25_percent(self, mock_exists, mock_file):
        """Test setting CPU quota to 25%."""
        mock_exists.return_value = True
        
        with patch.object(ResourceController, '_detect_cgroup_version', return_value=2):
            controller = ResourceController()
            cgroup_path = os.path.join("/sys/fs/cgroup", "gitproc", "test")
            controller._set_cpu_quota(cgroup_path, 0.25)
        
        # 25% = 25000/100000
        mock_file().write.assert_called_once_with("25000 100000")
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_set_cpu_quota_permission_error(self, mock_exists, mock_file):
        """Test that permission errors are handled gracefully."""
        mock_exists.return_value = True
        mock_file.side_effect = PermissionError("Access denied")
        
        with patch.object(ResourceController, '_detect_cgroup_version', return_value=2):
            controller = ResourceController()
            # Should not raise exception
            controller._set_cpu_quota("/sys/fs/cgroup/gitproc/test", 0.5)


class TestProcessAssignment:
    """Tests for process assignment to cgroup."""
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_add_process_v2(self, mock_exists, mock_file):
        """Test adding process to cgroup v2."""
        mock_exists.return_value = True
        
        with patch.object(ResourceController, '_detect_cgroup_version', return_value=2):
            controller = ResourceController()
            cgroup_path = os.path.join("/sys/fs/cgroup", "gitproc", "test")
            controller.add_process(cgroup_path, 12345)
        
        expected_file = os.path.join(cgroup_path, "cgroup.procs")
        mock_file.assert_called_once_with(expected_file, 'w')
        mock_file().write.assert_called_once_with("12345")
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_add_process_v1(self, mock_exists, mock_file):
        """Test adding process to cgroup v1."""
        mock_exists.return_value = False
        
        with patch.object(ResourceController, '_detect_cgroup_version', return_value=1):
            controller = ResourceController()
            cgroup_path = os.path.join("/sys/fs/cgroup", "memory", "gitproc", "test")
            controller.add_process(cgroup_path, 12345)
        
        # Should write to both memory and CPU hierarchies
        assert mock_file.call_count == 2
        
        calls = mock_file.call_args_list
        assert "tasks" in calls[0][0][0]
        assert "tasks" in calls[1][0][0]
    
    @patch('builtins.open', new_callable=mock_open)
    @patch('os.path.exists')
    def test_add_process_permission_error(self, mock_exists, mock_file):
        """Test that permission errors are handled gracefully."""
        mock_exists.return_value = True
        mock_file.side_effect = PermissionError("Access denied")
        
        with patch.object(ResourceController, '_detect_cgroup_version', return_value=2):
            controller = ResourceController()
            # Should not raise exception
            controller.add_process("/sys/fs/cgroup/gitproc/test", 12345)


class TestCgroupRemoval:
    """Tests for cgroup removal."""
    
    @patch('os.rmdir')
    @patch('os.path.exists')
    def test_remove_cgroup_v2(self, mock_exists, mock_rmdir):
        """Test removing cgroup for v2."""
        mock_exists.return_value = True
        
        with patch.object(ResourceController, '_detect_cgroup_version', return_value=2):
            controller = ResourceController()
            controller.remove_cgroup("/sys/fs/cgroup/gitproc/test")
        
        mock_rmdir.assert_called_once_with("/sys/fs/cgroup/gitproc/test")
    
    @patch('os.rmdir')
    @patch('os.path.exists')
    def test_remove_cgroup_v1(self, mock_exists, mock_rmdir):
        """Test removing cgroup for v1."""
        mock_exists.return_value = False
        
        with patch.object(ResourceController, '_detect_cgroup_version', return_value=1):
            controller = ResourceController()
            controller.remove_cgroup("/sys/fs/cgroup/memory/gitproc/test")
        
        # Should remove both memory and CPU hierarchies
        assert mock_rmdir.call_count == 2
    
    @patch('os.rmdir')
    @patch('os.path.exists')
    def test_remove_cgroup_not_found(self, mock_exists, mock_rmdir):
        """Test that missing cgroup errors are handled gracefully."""
        mock_exists.return_value = True
        mock_rmdir.side_effect = FileNotFoundError("Not found")
        
        with patch.object(ResourceController, '_detect_cgroup_version', return_value=2):
            controller = ResourceController()
            # Should not raise exception
            controller.remove_cgroup("/sys/fs/cgroup/gitproc/test")
