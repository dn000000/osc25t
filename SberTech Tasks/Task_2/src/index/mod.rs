use dashmap::DashMap;

/// In-memory index for fast key lookups
pub struct Index {
    map: DashMap<Vec<u8>, Location>,
}

impl Index {
    pub fn new() -> Self {
        Self {
            map: DashMap::new(),
        }
    }

    pub fn insert(&self, key: Vec<u8>, location: Location) {
        self.map.insert(key, location);
    }

    pub fn get(&self, key: &[u8]) -> Option<Location> {
        self.map.get(key).map(|entry| entry.value().clone())
    }

    pub fn remove(&self, key: &[u8]) {
        self.map.remove(key);
    }

    pub fn range(&self, start: &[u8], end: &[u8]) -> Vec<(Vec<u8>, Location)> {
        let mut results = Vec::new();
        
        for entry in self.map.iter() {
            let key = entry.key();
            // Check if key is within the range [start, end)
            if key.as_slice() >= start && key.as_slice() < end {
                results.push((key.clone(), entry.value().clone()));
            }
        }
        
        // Sort results by key to maintain lexicographic order
        results.sort_by(|a, b| a.0.cmp(&b.0));
        
        results
    }
}

#[derive(Debug, Clone)]
pub struct Location {
    pub file_type: FileType,
    pub file_id: u64,
    pub offset: u64,
    pub length: u32,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum FileType {
    Memtable,
    Wal,
    Sst,
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::sync::Arc;
    use std::thread;

    #[test]
    fn test_insert_and_get() {
        let index = Index::new();
        let key = b"test_key".to_vec();
        let location = Location {
            file_type: FileType::Sst,
            file_id: 1,
            offset: 100,
            length: 50,
        };

        index.insert(key.clone(), location.clone());
        let result = index.get(&key);

        assert!(result.is_some());
        let retrieved = result.unwrap();
        assert_eq!(retrieved.file_type, FileType::Sst);
        assert_eq!(retrieved.file_id, 1);
        assert_eq!(retrieved.offset, 100);
        assert_eq!(retrieved.length, 50);
    }

    #[test]
    fn test_get_nonexistent_key() {
        let index = Index::new();
        let result = index.get(b"nonexistent");
        assert!(result.is_none());
    }

    #[test]
    fn test_remove() {
        let index = Index::new();
        let key = b"test_key".to_vec();
        let location = Location {
            file_type: FileType::Wal,
            file_id: 2,
            offset: 200,
            length: 100,
        };

        index.insert(key.clone(), location);
        assert!(index.get(&key).is_some());

        index.remove(&key);
        assert!(index.get(&key).is_none());
    }

    #[test]
    fn test_update_existing_key() {
        let index = Index::new();
        let key = b"test_key".to_vec();
        
        let location1 = Location {
            file_type: FileType::Wal,
            file_id: 1,
            offset: 100,
            length: 50,
        };
        index.insert(key.clone(), location1);

        let location2 = Location {
            file_type: FileType::Sst,
            file_id: 2,
            offset: 200,
            length: 75,
        };
        index.insert(key.clone(), location2);

        let result = index.get(&key).unwrap();
        assert_eq!(result.file_type, FileType::Sst);
        assert_eq!(result.file_id, 2);
        assert_eq!(result.offset, 200);
    }

    #[test]
    fn test_range_query() {
        let index = Index::new();

        // Insert keys in non-sorted order
        index.insert(b"key5".to_vec(), Location {
            file_type: FileType::Sst,
            file_id: 5,
            offset: 500,
            length: 10,
        });
        index.insert(b"key2".to_vec(), Location {
            file_type: FileType::Sst,
            file_id: 2,
            offset: 200,
            length: 10,
        });
        index.insert(b"key8".to_vec(), Location {
            file_type: FileType::Sst,
            file_id: 8,
            offset: 800,
            length: 10,
        });
        index.insert(b"key3".to_vec(), Location {
            file_type: FileType::Sst,
            file_id: 3,
            offset: 300,
            length: 10,
        });

        // Query range [key2, key6)
        let results = index.range(b"key2", b"key6");

        assert_eq!(results.len(), 3);
        assert_eq!(results[0].0, b"key2");
        assert_eq!(results[1].0, b"key3");
        assert_eq!(results[2].0, b"key5");
        assert_eq!(results[0].1.file_id, 2);
        assert_eq!(results[1].1.file_id, 3);
        assert_eq!(results[2].1.file_id, 5);
    }

    #[test]
    fn test_range_query_empty() {
        let index = Index::new();
        index.insert(b"key1".to_vec(), Location {
            file_type: FileType::Sst,
            file_id: 1,
            offset: 100,
            length: 10,
        });

        let results = index.range(b"key5", b"key9");
        assert_eq!(results.len(), 0);
    }

    #[test]
    fn test_range_query_all() {
        let index = Index::new();
        
        index.insert(b"a".to_vec(), Location {
            file_type: FileType::Sst,
            file_id: 1,
            offset: 100,
            length: 10,
        });
        index.insert(b"m".to_vec(), Location {
            file_type: FileType::Sst,
            file_id: 2,
            offset: 200,
            length: 10,
        });
        index.insert(b"z".to_vec(), Location {
            file_type: FileType::Sst,
            file_id: 3,
            offset: 300,
            length: 10,
        });

        let results = index.range(b"a", b"zz");
        assert_eq!(results.len(), 3);
    }

    #[test]
    fn test_concurrent_insert() {
        let index = Arc::new(Index::new());
        let mut handles = vec![];

        for i in 0..10 {
            let index_clone = Arc::clone(&index);
            let handle = thread::spawn(move || {
                for j in 0..100 {
                    let key = format!("key_{}_{}", i, j).into_bytes();
                    let location = Location {
                        file_type: FileType::Sst,
                        file_id: (i * 100 + j) as u64,
                        offset: (i * 1000 + j * 10) as u64,
                        length: 10,
                    };
                    index_clone.insert(key, location);
                }
            });
            handles.push(handle);
        }

        for handle in handles {
            handle.join().unwrap();
        }

        // Verify all keys were inserted
        for i in 0..10 {
            for j in 0..100 {
                let key = format!("key_{}_{}", i, j).into_bytes();
                let result = index.get(&key);
                assert!(result.is_some());
            }
        }
    }

    #[test]
    fn test_concurrent_read_write() {
        let index = Arc::new(Index::new());

        // Pre-populate with some data
        for i in 0..100 {
            let key = format!("key_{}", i).into_bytes();
            let location = Location {
                file_type: FileType::Sst,
                file_id: i as u64,
                offset: i as u64 * 100,
                length: 10,
            };
            index.insert(key, location);
        }

        let mut handles = vec![];

        // Spawn reader threads
        for _ in 0..5 {
            let index_clone = Arc::clone(&index);
            let handle = thread::spawn(move || {
                for i in 0..100 {
                    let key = format!("key_{}", i).into_bytes();
                    let result = index_clone.get(&key);
                    assert!(result.is_some());
                }
            });
            handles.push(handle);
        }

        // Spawn writer threads
        for i in 0..5 {
            let index_clone = Arc::clone(&index);
            let handle = thread::spawn(move || {
                for j in 100..200 {
                    let key = format!("key_{}_{}", i, j).into_bytes();
                    let location = Location {
                        file_type: FileType::Wal,
                        file_id: (i * 100 + j) as u64,
                        offset: (i * 1000 + j * 10) as u64,
                        length: 20,
                    };
                    index_clone.insert(key, location);
                }
            });
            handles.push(handle);
        }

        for handle in handles {
            handle.join().unwrap();
        }
    }

    #[test]
    fn test_concurrent_remove() {
        let index = Arc::new(Index::new());

        // Pre-populate
        for i in 0..100 {
            let key = format!("key_{}", i).into_bytes();
            let location = Location {
                file_type: FileType::Sst,
                file_id: i as u64,
                offset: i as u64 * 100,
                length: 10,
            };
            index.insert(key, location);
        }

        let mut handles = vec![];

        // Spawn threads to remove keys
        for i in 0..10 {
            let index_clone = Arc::clone(&index);
            let handle = thread::spawn(move || {
                for j in 0..10 {
                    let key = format!("key_{}", i * 10 + j).into_bytes();
                    index_clone.remove(&key);
                }
            });
            handles.push(handle);
        }

        for handle in handles {
            handle.join().unwrap();
        }

        // Verify all keys were removed
        for i in 0..100 {
            let key = format!("key_{}", i).into_bytes();
            let result = index.get(&key);
            assert!(result.is_none());
        }
    }
}
