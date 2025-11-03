"""
Comprehensive tests for GitConfig
"""
import os
import sys
import time
import shutil
import unittest
import threading
import subprocess
import pytest
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from gitconfig_core import GitConfigStore


@pytest.mark.windows_skip
class TestGitConfigBasic(unittest.TestCase):
    """Test basic operations"""
    
    def setUp(self):
        self.test_dir = Path('./test_data/basic')
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.store = GitConfigStore(str(self.test_dir))
        
    def tearDown(self):
        self.store.stop()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            
    def test_set_and_get(self):
        """Test set and get operations"""
        self.assertTrue(self.store.set('/test/key', 'value1'))
        self.assertEqual(self.store.get('/test/key'), 'value1')
        
    def test_set_creates_git_commit(self):
        """Test that set creates a Git commit"""
        self.store.set('/test/key', 'value1')
        commits = list(self.store.repo.iter_commits())
        self.assertGreater(len(commits), 1)  # Initial commit + our commit
        
    def test_delete(self):
        """Test delete operation"""
        self.store.set('/test/key', 'value1')
        self.assertTrue(self.store.delete('/test/key'))
        self.assertIsNone(self.store.get('/test/key'))
        
    def test_delete_nonexistent(self):
        """Test deleting non-existent key"""
        self.assertFalse(self.store.delete('/nonexistent'))


@pytest.mark.windows_skip
class TestGitConfigHierarchical(unittest.TestCase):
    """Test hierarchical keys"""
    
    def setUp(self):
        self.test_dir = Path('./test_data/hierarchical')
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.store = GitConfigStore(str(self.test_dir))
        
    def tearDown(self):
        self.store.stop()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            
    def test_hierarchical_storage(self):
        """Test that keys are stored as files in hierarchy"""
        self.store.set('/app/db/host', 'localhost')
        file_path = self.test_dir / 'app' / 'db' / 'host'
        self.assertTrue(file_path.exists())
        self.assertEqual(file_path.read_text(), 'localhost')
        
    def test_list_keys(self):
        """Test listing keys"""
        self.store.set('/app/db/host', 'localhost')
        self.store.set('/app/db/port', '5432')
        self.store.set('/app/api/endpoint', 'http://api')
        
        keys = self.store.list_keys('/app/db/')
        self.assertIn('/app/db/host', keys)
        self.assertIn('/app/db/port', keys)
        
    def test_list_recursive(self):
        """Test recursive listing"""
        self.store.set('/app/db/host', 'localhost')
        self.store.set('/app/api/endpoint', 'http://api')
        
        keys = self.store.list_keys('/app/', recursive=True)
        self.assertIn('/app/db/host', keys)
        self.assertIn('/app/api/endpoint', keys)


@pytest.mark.windows_skip
class TestGitConfigVersioning(unittest.TestCase):
    """Test versioning features"""
    
    def setUp(self):
        self.test_dir = Path('./test_data/versioning')
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.store = GitConfigStore(str(self.test_dir))
        
    def tearDown(self):
        self.store.stop()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            
    def test_get_old_version(self):
        """Test getting old version of key"""
        self.store.set('/test/key', 'v1')
        time.sleep(0.1)
        commits = list(self.store.repo.iter_commits())
        first_commit = commits[-2].hexsha  # -1 is initial, -2 is our first set
        
        self.store.set('/test/key', 'v2')
        
        self.assertEqual(self.store.get('/test/key'), 'v2')
        self.assertEqual(self.store.get('/test/key', commit=first_commit), 'v1')
        
    def test_history(self):
        """Test history command"""
        self.store.set('/test/key', 'v1')
        time.sleep(0.1)
        self.store.set('/test/key', 'v2')
        
        history = self.store.history('/test/key')
        self.assertEqual(len(history), 2)
        self.assertIn('commit', history[0])
        self.assertIn('date', history[0])



@pytest.mark.windows_skip
class TestGitConfigWatch(unittest.TestCase):
    """Test watch mechanism"""
    
    def setUp(self):
        self.test_dir = Path('./test_data/watch')
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.store = GitConfigStore(str(self.test_dir))
        
    def tearDown(self):
        self.store.stop()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            
    def test_watch_triggers_on_change(self):
        """Test that watch triggers when key changes"""
        self.store.set('/test/key', 'v1')
        
        result = {'triggered': False}
        
        def watcher():
            if self.store.watch('/test/key', timeout=5):
                result['triggered'] = True
        
        thread = threading.Thread(target=watcher)
        thread.start()
        
        time.sleep(0.5)
        self.store.set('/test/key', 'v2')
        
        thread.join(timeout=6)
        self.assertTrue(result['triggered'])
        
    def test_watch_timeout(self):
        """Test watch timeout"""
        self.store.set('/test/key', 'v1')
        triggered = self.store.watch('/test/key', timeout=1)
        self.assertFalse(triggered)


@pytest.mark.windows_skip
class TestGitConfigTTL(unittest.TestCase):
    """Test TTL functionality"""
    
    def setUp(self):
        self.test_dir = Path('./test_data/ttl')
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.store = GitConfigStore(str(self.test_dir))
        self.store.start_ttl_cleanup()
        
    def tearDown(self):
        self.store.stop()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            
    def test_ttl_expiration(self):
        """Test that keys expire after TTL"""
        self.store.set('/test/key', 'value', ttl=2)
        self.assertEqual(self.store.get('/test/key'), 'value')
        
        time.sleep(3)
        self.assertIsNone(self.store.get('/test/key'))


@pytest.mark.windows_skip
class TestGitConfigCAS(unittest.TestCase):
    """Test Compare-and-Swap"""
    
    def setUp(self):
        self.test_dir = Path('./test_data/cas')
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.store = GitConfigStore(str(self.test_dir))
        
    def tearDown(self):
        self.store.stop()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            
    def test_cas_success(self):
        """Test successful CAS operation"""
        self.store.set('/counter', '5')
        self.assertTrue(self.store.cas('/counter', '5', '6'))
        self.assertEqual(self.store.get('/counter'), '6')
        
    def test_cas_failure(self):
        """Test failed CAS operation"""
        self.store.set('/counter', '5')
        self.assertFalse(self.store.cas('/counter', '4', '6'))
        self.assertEqual(self.store.get('/counter'), '5')


@pytest.mark.windows_skip
@pytest.mark.sync
class TestGitConfigSync(unittest.TestCase):
    """Test synchronization between nodes"""
    
    def setUp(self):
        self.test_dir = Path('./test_data/sync')
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True)
        
        # Create bare repository as remote
        self.bare_repo = self.test_dir / 'bare.git'
        subprocess.run(['git', 'init', '--bare', str(self.bare_repo)], 
                      capture_output=True, check=True)
        
        # Create two nodes
        self.node1_dir = self.test_dir / 'node1'
        self.node2_dir = self.test_dir / 'node2'
        
        self.store1 = GitConfigStore(str(self.node1_dir))
        self.store1.add_remote('origin', str(self.bare_repo.absolute()))
        
        self.store2 = GitConfigStore(str(self.node2_dir))
        self.store2.add_remote('origin', str(self.bare_repo.absolute()))
        
    def tearDown(self):
        self.store1.stop()
        self.store2.stop()
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
            
    def test_manual_sync(self):
        """Test manual push/pull synchronization"""
        # Node1 sets a key and pushes
        self.store1.set('/test/key', 'value1')
        self.store1.push('origin')
        
        # Node2 pulls and gets the key
        self.store2.pull('origin')
        self.assertEqual(self.store2.get('/test/key'), 'value1')
        
    def test_conflict_resolution(self):
        """Test conflict resolution with last-write-wins"""
        # Both nodes set the same key
        self.store1.set('/test/key', 'value1')
        self.store2.set('/test/key', 'value2')
        
        # Node1 pushes first
        self.store1.push('origin')
        
        # Node2 pulls (should resolve conflict) and pushes
        self.store2.pull('origin')
        self.store2.push('origin')
        
        # Node1 pulls and should see resolved value
        self.store1.pull('origin')
        
        # Both nodes should have a value (not in broken state)
        val1 = self.store1.get('/test/key')
        val2 = self.store2.get('/test/key')
        self.assertIsNotNone(val1)
        self.assertIsNotNone(val2)
        self.assertEqual(val1, val2)


def run_tests():
    """Run all tests"""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    suite.addTests(loader.loadTestsFromTestCase(TestGitConfigBasic))
    suite.addTests(loader.loadTestsFromTestCase(TestGitConfigHierarchical))
    suite.addTests(loader.loadTestsFromTestCase(TestGitConfigVersioning))
    suite.addTests(loader.loadTestsFromTestCase(TestGitConfigWatch))
    suite.addTests(loader.loadTestsFromTestCase(TestGitConfigTTL))
    suite.addTests(loader.loadTestsFromTestCase(TestGitConfigCAS))
    suite.addTests(loader.loadTestsFromTestCase(TestGitConfigSync))
    
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    exit(0 if success else 1)
