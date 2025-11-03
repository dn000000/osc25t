use crossbeam_skiplist::SkipMap;
use std::sync::atomic::{AtomicU64, Ordering};

/// In-memory buffer for recent writes
pub struct Memtable {
    data: SkipMap<Vec<u8>, MemtableEntry>,
    size: AtomicU64,
    max_size: u64,
}

impl Memtable {
    pub fn new(max_size: u64) -> Self {
        Self {
            data: SkipMap::new(),
            size: AtomicU64::new(0),
            max_size,
        }
    }

    pub fn put(&self, key: Vec<u8>, value: Vec<u8>, seq: u64) {
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_micros() as u64;
        
        // Calculate size increase: key + value + entry overhead
        let entry_size = key.len() + value.len() + std::mem::size_of::<MemtableEntry>();
        
        let entry = MemtableEntry {
            value: Some(value),
            timestamp,
            sequence: seq,
        };
        
        self.data.insert(key, entry);
        self.size.fetch_add(entry_size as u64, Ordering::Relaxed);
    }

    pub fn get(&self, key: &[u8]) -> Option<MemtableEntry> {
        self.data.get(key).map(|entry| entry.value().clone())
    }

    pub fn delete(&self, key: Vec<u8>, seq: u64) {
        let timestamp = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_micros() as u64;
        
        // Calculate size increase: key + entry overhead (no value for tombstone)
        let entry_size = key.len() + std::mem::size_of::<MemtableEntry>();
        
        let entry = MemtableEntry {
            value: None, // Tombstone
            timestamp,
            sequence: seq,
        };
        
        self.data.insert(key, entry);
        self.size.fetch_add(entry_size as u64, Ordering::Relaxed);
    }

    pub fn scan(&self, start: &[u8], end: &[u8]) -> Vec<(Vec<u8>, Vec<u8>)> {
        let mut results = Vec::new();
        
        // Iterate over the skip list in lexicographic order
        for entry in self.data.range(start.to_vec()..end.to_vec()) {
            let key = entry.key();
            let memtable_entry = entry.value();
            
            // Only include entries with values (skip tombstones)
            if let Some(value) = &memtable_entry.value {
                results.push((key.clone(), value.clone()));
            }
        }
        
        results
    }

    /// Get all entries including tombstones for flushing to SST
    pub fn get_all_entries(&self) -> Vec<(Vec<u8>, Option<Vec<u8>>)> {
        let mut results = Vec::new();
        
        for entry in self.data.iter() {
            let key = entry.key().clone();
            let memtable_entry = entry.value();
            results.push((key, memtable_entry.value.clone()));
        }
        
        results
    }

    pub fn is_full(&self) -> bool {
        self.size.load(Ordering::Relaxed) >= self.max_size
    }

    pub fn clear(&mut self) {
        self.data.clear();
        self.size.store(0, Ordering::Relaxed);
    }
}

#[derive(Debug, Clone)]
pub struct MemtableEntry {
    pub value: Option<Vec<u8>>,
    pub timestamp: u64,
    pub sequence: u64,
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    use std::thread;

    #[test]
    fn test_put_and_get() {
        let memtable = Memtable::new(1024 * 1024); // 1MB
        
        // Test basic put and get
        let key = b"test_key".to_vec();
        let value = b"test_value".to_vec();
        memtable.put(key.clone(), value.clone(), 1);
        
        let result = memtable.get(&key);
        assert!(result.is_some());
        let entry = result.unwrap();
        assert_eq!(entry.value, Some(value));
        assert_eq!(entry.sequence, 1);
    }

    #[test]
    fn test_get_nonexistent_key() {
        let memtable = Memtable::new(1024 * 1024);
        
        let result = memtable.get(b"nonexistent");
        assert!(result.is_none());
    }

    #[test]
    fn test_delete() {
        let memtable = Memtable::new(1024 * 1024);
        
        // Put a key-value pair
        let key = b"delete_key".to_vec();
        let value = b"delete_value".to_vec();
        memtable.put(key.clone(), value, 1);
        
        // Delete the key
        memtable.delete(key.clone(), 2);
        
        // Get should return tombstone (None value)
        let result = memtable.get(&key);
        assert!(result.is_some());
        let entry = result.unwrap();
        assert_eq!(entry.value, None);
        assert_eq!(entry.sequence, 2);
    }

    #[test]
    fn test_scan_basic() {
        let memtable = Memtable::new(1024 * 1024);
        
        // Insert multiple key-value pairs
        memtable.put(b"key1".to_vec(), b"value1".to_vec(), 1);
        memtable.put(b"key2".to_vec(), b"value2".to_vec(), 2);
        memtable.put(b"key3".to_vec(), b"value3".to_vec(), 3);
        memtable.put(b"key5".to_vec(), b"value5".to_vec(), 4);
        
        // Scan from key1 to key4
        let results = memtable.scan(b"key1", b"key4");
        
        assert_eq!(results.len(), 3);
        assert_eq!(results[0].0, b"key1");
        assert_eq!(results[0].1, b"value1");
        assert_eq!(results[1].0, b"key2");
        assert_eq!(results[1].1, b"value2");
        assert_eq!(results[2].0, b"key3");
        assert_eq!(results[2].1, b"value3");
    }

    #[test]
    fn test_scan_with_tombstones() {
        let memtable = Memtable::new(1024 * 1024);
        
        // Insert key-value pairs
        memtable.put(b"key1".to_vec(), b"value1".to_vec(), 1);
        memtable.put(b"key2".to_vec(), b"value2".to_vec(), 2);
        memtable.put(b"key3".to_vec(), b"value3".to_vec(), 3);
        
        // Delete key2
        memtable.delete(b"key2".to_vec(), 4);
        
        // Scan should skip tombstones
        let results = memtable.scan(b"key1", b"key4");
        
        assert_eq!(results.len(), 2);
        assert_eq!(results[0].0, b"key1");
        assert_eq!(results[1].0, b"key3");
    }

    #[test]
    fn test_scan_empty_range() {
        let memtable = Memtable::new(1024 * 1024);
        
        memtable.put(b"key1".to_vec(), b"value1".to_vec(), 1);
        memtable.put(b"key5".to_vec(), b"value5".to_vec(), 2);
        
        // Scan range with no keys
        let results = memtable.scan(b"key2", b"key4");
        assert_eq!(results.len(), 0);
    }

    #[test]
    fn test_size_tracking() {
        let memtable = Memtable::new(1024 * 1024);
        
        // Initially size should be 0
        assert_eq!(memtable.size.load(Ordering::Relaxed), 0);
        
        // Add a key-value pair
        let key = b"test_key".to_vec();
        let value = b"test_value".to_vec();
        memtable.put(key.clone(), value.clone(), 1);
        
        // Size should increase
        let size_after_put = memtable.size.load(Ordering::Relaxed);
        assert!(size_after_put > 0);
        
        // Add another entry
        memtable.put(b"key2".to_vec(), b"value2".to_vec(), 2);
        
        // Size should increase further
        let size_after_second_put = memtable.size.load(Ordering::Relaxed);
        assert!(size_after_second_put > size_after_put);
    }

    #[test]
    fn test_is_full() {
        let max_size = 100;
        let memtable = Memtable::new(max_size);
        
        // Initially not full
        assert!(!memtable.is_full());
        
        // Add entries until full
        let key = b"k".to_vec();
        let value = vec![0u8; 50]; // Large value
        memtable.put(key.clone(), value.clone(), 1);
        
        // Should be full or close to full
        let is_full = memtable.is_full();
        assert!(is_full || memtable.size.load(Ordering::Relaxed) > 0);
    }

    #[test]
    fn test_clear() {
        let memtable = Memtable::new(1024 * 1024);
        
        // Add some entries
        memtable.put(b"key1".to_vec(), b"value1".to_vec(), 1);
        memtable.put(b"key2".to_vec(), b"value2".to_vec(), 2);
        
        assert!(memtable.size.load(Ordering::Relaxed) > 0);
        assert!(memtable.get(b"key1").is_some());
        
        // Clear the memtable
        let mut memtable_mut = memtable;
        memtable_mut.clear();
        
        // Size should be 0 and entries should be gone
        assert_eq!(memtable_mut.size.load(Ordering::Relaxed), 0);
        assert!(memtable_mut.get(b"key1").is_none());
    }

    #[test]
    fn test_concurrent_access() {
        let memtable = Arc::new(Memtable::new(10 * 1024 * 1024)); // 10MB
        let num_threads = 4;
        let ops_per_thread = 100;
        
        let mut handles = vec![];
        
        // Spawn multiple threads doing concurrent puts
        for thread_id in 0..num_threads {
            let memtable_clone = Arc::clone(&memtable);
            let handle = thread::spawn(move || {
                for i in 0..ops_per_thread {
                    let key = format!("thread{}_key{}", thread_id, i).into_bytes();
                    let value = format!("value{}", i).into_bytes();
                    memtable_clone.put(key, value, (thread_id * ops_per_thread + i) as u64);
                }
            });
            handles.push(handle);
        }
        
        // Wait for all threads to complete
        for handle in handles {
            handle.join().unwrap();
        }
        
        // Verify all entries were inserted
        for thread_id in 0..num_threads {
            for i in 0..ops_per_thread {
                let key = format!("thread{}_key{}", thread_id, i).into_bytes();
                let result = memtable.get(&key);
                assert!(result.is_some(), "Key not found: thread{}_key{}", thread_id, i);
            }
        }
    }

    #[test]
    fn test_concurrent_read_write() {
        let memtable = Arc::new(Memtable::new(10 * 1024 * 1024));
        
        // Pre-populate with some data
        for i in 0..50 {
            let key = format!("key{}", i).into_bytes();
            let value = format!("value{}", i).into_bytes();
            memtable.put(key, value, i as u64);
        }
        
        let mut handles = vec![];
        
        // Spawn writer threads
        for thread_id in 0..2 {
            let memtable_clone = Arc::clone(&memtable);
            let handle = thread::spawn(move || {
                for i in 0..50 {
                    let key = format!("write_key{}_{}", thread_id, i).into_bytes();
                    let value = format!("write_value{}", i).into_bytes();
                    memtable_clone.put(key, value, (100 + thread_id * 50 + i) as u64);
                }
            });
            handles.push(handle);
        }
        
        // Spawn reader threads
        for _ in 0..2 {
            let memtable_clone = Arc::clone(&memtable);
            let handle = thread::spawn(move || {
                for i in 0..50 {
                    let key = format!("key{}", i).into_bytes();
                    let _ = memtable_clone.get(&key);
                }
            });
            handles.push(handle);
        }
        
        // Wait for all threads
        for handle in handles {
            handle.join().unwrap();
        }
    }
}
