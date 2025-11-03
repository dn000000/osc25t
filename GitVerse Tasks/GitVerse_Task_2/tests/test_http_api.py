"""
HTTP API integration tests
"""
import sys
import time
import unittest
import threading
import requests
import shutil
import pytest
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from gitconfig_node import GitConfigNode


class TestHTTPAPI(unittest.TestCase):
    """Test HTTP API endpoints"""
    
    @classmethod
    def setUpClass(cls):
        """Start HTTP server for tests"""
        cls.test_dir = Path('./test_data/http')
        if cls.test_dir.exists():
            shutil.rmtree(cls.test_dir)
        
        cls.node = GitConfigNode(str(cls.test_dir), 8888)
        
        # Start server in background thread
        cls.server_thread = threading.Thread(target=cls.node.run, daemon=True)
        cls.server_thread.start()
        
        # Wait for server to start
        time.sleep(2)
        cls.base_url = 'http://localhost:8888'
        
    @classmethod
    def tearDownClass(cls):
        """Cleanup"""
        cls.node.store.stop()
        if cls.test_dir.exists():
            try:
                shutil.rmtree(cls.test_dir)
            except PermissionError:
                # On Windows, Git may hold files open
                print(f"Warning: Could not remove {cls.test_dir} (files in use)")
    
    def test_health_check(self):
        """Test health endpoint"""
        response = requests.get(f'{self.base_url}/health')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'healthy')
    
    def test_set_and_get_key(self):
        """Test POST and GET key"""
        # Set key
        response = requests.post(f'{self.base_url}/keys/test/api/key', data='test_value')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # Get key
        response = requests.get(f'{self.base_url}/keys/test/api/key')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['value'], 'test_value')
    
    def test_get_nonexistent_key(self):
        """Test GET non-existent key returns 404"""
        response = requests.get(f'{self.base_url}/keys/nonexistent/key')
        self.assertEqual(response.status_code, 404)
    
    def test_delete_key(self):
        """Test DELETE key"""
        # Set key first
        requests.post(f'{self.base_url}/keys/test/delete/key', data='value')
        
        # Delete key
        response = requests.delete(f'{self.base_url}/keys/test/delete/key')
        self.assertEqual(response.status_code, 200)
        
        # Verify deleted
        response = requests.get(f'{self.base_url}/keys/test/delete/key')
        self.assertEqual(response.status_code, 404)
    
    @pytest.mark.windows_skip
    def test_set_with_ttl(self):
        """Test setting key with TTL"""
        response = requests.post(f'{self.base_url}/keys/test/ttl/key?ttl=2', data='ttl_value')
        self.assertEqual(response.status_code, 200)
        
        # Should exist immediately
        time.sleep(0.5)  # Small delay to ensure write completes
        response = requests.get(f'{self.base_url}/keys/test/ttl/key')
        self.assertEqual(response.status_code, 200)
        
        # Wait for expiration
        time.sleep(3)
        
        # Should be gone
        response = requests.get(f'{self.base_url}/keys/test/ttl/key')
        self.assertEqual(response.status_code, 404)
    
    def test_list_keys(self):
        """Test list endpoint"""
        # Set multiple keys
        requests.post(f'{self.base_url}/keys/list/test/key1', data='v1')
        requests.post(f'{self.base_url}/keys/list/test/key2', data='v2')
        requests.post(f'{self.base_url}/keys/list/other/key3', data='v3')
        
        # List with prefix
        response = requests.get(f'{self.base_url}/list?prefix=/list/test/')
        self.assertEqual(response.status_code, 200)
        keys = response.json()['keys']
        self.assertIn('/list/test/key1', keys)
        self.assertIn('/list/test/key2', keys)
        self.assertNotIn('/list/other/key3', keys)
    
    def test_history(self):
        """Test history endpoint"""
        # Set key multiple times
        requests.post(f'{self.base_url}/keys/history/key', data='v1')
        time.sleep(0.1)
        requests.post(f'{self.base_url}/keys/history/key', data='v2')
        
        # Get history
        response = requests.get(f'{self.base_url}/keys/history/key/history')
        self.assertEqual(response.status_code, 200)
        history = response.json()['history']
        self.assertGreaterEqual(len(history), 2)
    
    def test_cas_success(self):
        """Test successful CAS"""
        # Set initial value
        requests.post(f'{self.base_url}/keys/cas/counter', data='5')
        
        # CAS with correct expected value
        response = requests.post(
            f'{self.base_url}/cas/cas/counter',
            json={'expected': '5', 'new_value': '6'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()['success'])
        
        # Verify new value
        response = requests.get(f'{self.base_url}/keys/cas/counter')
        self.assertEqual(response.json()['value'], '6')
    
    def test_cas_failure(self):
        """Test failed CAS"""
        # Set initial value
        requests.post(f'{self.base_url}/keys/cas/counter2', data='5')
        
        # CAS with wrong expected value
        response = requests.post(
            f'{self.base_url}/cas/cas/counter2',
            json={'expected': '4', 'new_value': '6'}
        )
        self.assertEqual(response.status_code, 409)
        self.assertFalse(response.json()['success'])
        
        # Verify value unchanged
        response = requests.get(f'{self.base_url}/keys/cas/counter2')
        self.assertEqual(response.json()['value'], '5')


if __name__ == '__main__':
    unittest.main(verbosity=2)
