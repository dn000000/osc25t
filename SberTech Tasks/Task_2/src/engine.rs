use crate::compaction::Compactor;
use crate::config::Config;
use crate::entry::{OpType, WalEntry};
use crate::error::Result;
use crate::index::{FileType, Index, Location};
use crate::io_uring::IoUringContext;
use crate::memtable::Memtable;
use crate::metrics::Metrics;
use crate::sst::SstManager;
use crate::wal::WalManager;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Arc, Mutex, RwLock};
use std::time::Instant;

/// Main storage engine coordinating all operations.
///
/// The `StorageEngine` is the primary interface for interacting with uringKV.
/// It coordinates all components including WAL, memtable, SST files, index,
/// and background compaction.
///
/// # Architecture
///
/// - **WAL**: All writes are logged to the write-ahead log before acknowledgment
/// - **Memtable**: Recent writes are buffered in an in-memory skip list
/// - **SST Files**: When memtable is full, data is flushed to immutable SST files
/// - **Index**: In-memory index tracks key locations for fast lookups
/// - **Compaction**: Background thread merges SST files and removes tombstones
///
/// # Example
///
/// ```no_run
/// use uringkv::{Config, StorageEngine};
/// use std::path::PathBuf;
///
/// #[tokio::main]
/// async fn main() -> Result<(), Box<dyn std::error::Error>> {
///     let config = Config::new(PathBuf::from("./data"));
///     let engine = StorageEngine::new(config).await?;
///     
///     engine.put(b"key", b"value").await?;
///     let value = engine.get(b"key").await?;
///     
///     engine.close().await?;
///     Ok(())
/// }
/// ```
pub struct StorageEngine {
    _config: Config,
    wal: Arc<WalManager>,
    memtable: Arc<RwLock<Memtable>>,
    sst_manager: Arc<SstManager>,
    index: Arc<Index>,
    _io_uring: Arc<Mutex<IoUringContext>>,
    sequence: Arc<AtomicU64>,
    compactor: Arc<Mutex<Compactor>>,
    metrics: Arc<Metrics>,
}

impl StorageEngine {
    /// Creates a new storage engine with the given configuration.
    ///
    /// This method initializes all components and performs crash recovery
    /// by replaying WAL entries and rebuilding the index from SST files.
    ///
    /// # Arguments
    ///
    /// * `config` - Configuration for the storage engine
    ///
    /// # Returns
    ///
    /// Returns a `Result` containing the initialized `StorageEngine` or an error.
    ///
    /// # Errors
    ///
    /// Returns an error if:
    /// - Directory creation fails
    /// - io_uring initialization fails
    /// - WAL recovery fails
    /// - SST file loading fails
    ///
    /// # Example
    ///
    /// ```no_run
    /// use uringkv::{Config, StorageEngine};
    /// use std::path::PathBuf;
    ///
    /// #[tokio::main]
    /// async fn main() -> Result<(), Box<dyn std::error::Error>> {
    ///     let config = Config::new(PathBuf::from("./data"))
    ///         .with_memtable_size(64 * 1024 * 1024)
    ///         .with_queue_depth(256);
    ///     
    ///     let engine = StorageEngine::new(config).await?;
    ///     Ok(())
    /// }
    /// ```
    pub async fn new(config: Config) -> Result<Self> {
        // Create data directories
        std::fs::create_dir_all(&config.data_dir)?;
        std::fs::create_dir_all(config.data_dir.join("wal"))?;
        std::fs::create_dir_all(config.data_dir.join("sst"))?;

        // Initialize io_uring context
        let io_uring = Arc::new(Mutex::new(IoUringContext::new(
            config.queue_depth,
            config.enable_sqpoll,
        )?));

        // Initialize WAL manager
        let mut wal = WalManager::new(config.clone(), io_uring.clone()).await?;

        // Initialize memtable
        let memtable = Arc::new(RwLock::new(Memtable::new(config.memtable_size)));

        // Initialize SST manager
        let sst_dir = config.data_dir.join("sst");
        let sst_io_uring = Arc::new(RwLock::new(IoUringContext::new(
            config.queue_depth,
            config.enable_sqpoll,
        )?));
        let sst_manager = Arc::new(SstManager::new(
            sst_dir,
            sst_io_uring,
            config.checksum_algorithm,
        ));

        // Load existing SST files
        sst_manager.load_existing_files()?;

        // Initialize index
        let index = Arc::new(Index::new());

        // Initialize metrics
        let metrics = Arc::new(Metrics::new());

        // Set metrics in WAL manager
        wal.set_metrics(metrics.clone());
        let wal = Arc::new(wal);

        // Perform crash recovery
        let sequence = Arc::new(AtomicU64::new(0));
        Self::recover(&wal, &memtable, &index, &sequence, &sst_manager).await?;

        // Initialize and start compactor
        let mut compactor = Compactor::new(
            sst_manager.clone(),
            config.compaction_strategy.clone(),
        );
        compactor.start();
        let compactor = Arc::new(Mutex::new(compactor));

        Ok(Self {
            _config: config,
            wal,
            memtable,
            sst_manager,
            index,
            _io_uring: io_uring,
            sequence,
            compactor,
            metrics,
        })
    }

    /// Perform crash recovery by replaying WAL entries and rebuilding index from SST files
    async fn recover(
        wal: &Arc<WalManager>,
        memtable: &Arc<RwLock<Memtable>>,
        index: &Arc<Index>,
        sequence: &Arc<AtomicU64>,
        sst_manager: &Arc<SstManager>,
    ) -> Result<()> {
        tracing::info!("Starting crash recovery...");
        
        // Step 1: Rebuild index from SST files
        Self::rebuild_index_from_sst(index, sst_manager).await?;
        
        // Step 2: Recover WAL entries
        let entries = wal.recover().await?;
        tracing::info!("Recovered {} WAL entries", entries.len());

        let mut max_seq = 0u64;
        let mut recovered_count = 0u64;
        let memtable_write = memtable.write().unwrap();

        // Step 3: Replay entries to rebuild memtable and update index
        for entry in entries {
            max_seq = max_seq.max(entry.sequence);

            match entry.op_type {
                OpType::Put => {
                    memtable_write.put(entry.key.clone(), entry.value.clone(), entry.sequence);

                    // Update index with memtable location (overrides SST location if exists)
                    index.insert(
                        entry.key,
                        Location {
                            file_type: FileType::Memtable,
                            file_id: 0,
                            offset: 0,
                            length: entry.value.len() as u32,
                        },
                    );
                    recovered_count += 1;
                }
                OpType::Delete => {
                    memtable_write.delete(entry.key.clone(), entry.sequence);

                    // Update index with tombstone (overrides SST location if exists)
                    index.insert(
                        entry.key,
                        Location {
                            file_type: FileType::Memtable,
                            file_id: 0,
                            offset: 0,
                            length: 0,
                        },
                    );
                    recovered_count += 1;
                }
            }
        }

        drop(memtable_write);

        // Set sequence to max recovered sequence + 1
        sequence.store(max_seq + 1, Ordering::SeqCst);
        
        tracing::info!(
            "Crash recovery complete: {} operations replayed, sequence reset to {}",
            recovered_count,
            max_seq + 1
        );

        Ok(())
    }

    /// Rebuild index from all SST files on disk
    /// Note: We don't load individual SST keys into the index during recovery.
    /// SST files are already tracked by the SST manager with bloom filters and metadata.
    /// The index is primarily used for memtable entries. For SST lookups, we rely on
    /// the SST manager's file list, bloom filters, and binary search within files.
    async fn rebuild_index_from_sst(
        _index: &Arc<Index>,
        sst_manager: &Arc<SstManager>,
    ) -> Result<()> {
        let sst_files = sst_manager.get_all_files();
        tracing::info!("Rebuilding index from {} SST files", sst_files.len());
        
        let mut total_keys = 0u64;
        for sst_file in &sst_files {
            total_keys += sst_file.num_entries;
        }
        
        tracing::info!(
            "Index rebuild complete: {} SST files covering ~{} keys (SST keys not loaded into index)",
            sst_files.len(),
            total_keys
        );
        Ok(())
    }

    /// Inserts or updates a key-value pair in the storage.
    ///
    /// The operation follows these steps:
    /// 1. Append to WAL for durability
    /// 2. Sync WAL to disk
    /// 3. Update memtable
    /// 4. Update index
    /// 5. Trigger flush if memtable is full
    ///
    /// # Arguments
    ///
    /// * `key` - The key to insert or update
    /// * `value` - The value to associate with the key
    ///
    /// # Returns
    ///
    /// Returns `Ok(())` on success or an error if the operation fails.
    ///
    /// # Errors
    ///
    /// Returns an error if:
    /// - WAL append fails
    /// - WAL sync fails
    /// - Memtable flush fails
    ///
    /// # Example
    ///
    /// ```no_run
    /// # use uringkv::{Config, StorageEngine};
    /// # use std::path::PathBuf;
    /// # #[tokio::main]
    /// # async fn main() -> Result<(), Box<dyn std::error::Error>> {
    /// # let config = Config::new(PathBuf::from("./data"));
    /// # let engine = StorageEngine::new(config).await?;
    /// engine.put(b"user:1", b"Alice").await?;
    /// engine.put(b"user:2", b"Bob").await?;
    /// # Ok(())
    /// # }
    /// ```
    pub async fn put(&self, key: &[u8], value: &[u8]) -> Result<()> {
        let start = Instant::now();
        
        // Track memory allocation for key and value copies
        self.metrics.increment_allocations();
        
        // Get next sequence number
        let seq = self.sequence.fetch_add(1, Ordering::SeqCst);

        // Create WAL entry
        let wal_entry = WalEntry::new_put(key.to_vec(), value.to_vec()).with_sequence(seq);

        // Append to WAL
        let offset = self.wal.append(wal_entry).await?;

        // Sync WAL
        self.wal.sync().await?;

        // Update memtable
        {
            let memtable = self.memtable.read().unwrap();
            memtable.put(key.to_vec(), value.to_vec(), seq);
        }

        // Update index with memtable location
        self.index.insert(
            key.to_vec(),
            Location {
                file_type: FileType::Memtable,
                file_id: 0,
                offset,
                length: value.len() as u32,
            },
        );

        // Check if memtable is full and trigger flush
        {
            let memtable = self.memtable.read().unwrap();
            if memtable.is_full() {
                drop(memtable);
                self.flush_memtable().await?;
            }
        }

        // Record metrics
        self.metrics.record_latency("put", start.elapsed());
        self.metrics.increment_throughput();

        Ok(())
    }

    /// Retrieves the value associated with a key.
    ///
    /// The lookup follows this order:
    /// 1. Check memtable (most recent writes)
    /// 2. Check index for memtable location
    /// 3. Search SST files (newest to oldest) using bloom filters
    ///
    /// # Arguments
    ///
    /// * `key` - The key to look up
    ///
    /// # Returns
    ///
    /// Returns `Ok(Some(value))` if the key exists, `Ok(None)` if not found,
    /// or an error if the operation fails.
    ///
    /// # Errors
    ///
    /// Returns an error if:
    /// - SST file read fails
    /// - Checksum verification fails
    ///
    /// # Example
    ///
    /// ```no_run
    /// # use uringkv::{Config, StorageEngine};
    /// # use std::path::PathBuf;
    /// # #[tokio::main]
    /// # async fn main() -> Result<(), Box<dyn std::error::Error>> {
    /// # let config = Config::new(PathBuf::from("./data"));
    /// # let engine = StorageEngine::new(config).await?;
    /// engine.put(b"key", b"value").await?;
    /// 
    /// let value = engine.get(b"key").await?;
    /// assert_eq!(value, Some(b"value".to_vec()));
    /// 
    /// let missing = engine.get(b"nonexistent").await?;
    /// assert_eq!(missing, None);
    /// # Ok(())
    /// # }
    /// ```
    pub async fn get(&self, key: &[u8]) -> Result<Option<Vec<u8>>> {
        let start = Instant::now();
        
        // Check memtable first
        {
            let memtable = self.memtable.read().unwrap();
            if let Some(entry) = memtable.get(key) {
                self.metrics.record_latency("get", start.elapsed());
                self.metrics.increment_throughput();
                return Ok(entry.value);
            }
        }

        // Note: We don't check the index here because after flush, keys may still
        // be marked as Memtable in the index but actually be in SST files.
        // We rely on SST bloom filters and range checks for efficient lookups.

        // Search through SST files (newest to oldest for better performance)
        // SST files are checked using bloom filters first, then actual reads
        let sst_files = self.sst_manager.get_all_files();
        for sst_file in sst_files.iter().rev() {
            // Check if key might be in this file using bloom filter and range
            if sst_file.in_range(key) && sst_file.may_contain(key) {
                if let Some(value) = self.sst_manager.read(&sst_file, key).await? {
                    self.metrics.record_latency("get", start.elapsed());
                    self.metrics.increment_throughput();
                    return Ok(Some(value));
                }
            }
        }

        // Key not found
        self.metrics.record_latency("get", start.elapsed());
        self.metrics.increment_throughput();
        Ok(None)
    }

    /// Deletes a key from the storage by inserting a tombstone.
    ///
    /// The operation follows these steps:
    /// 1. Append delete operation to WAL
    /// 2. Sync WAL to disk
    /// 3. Insert tombstone in memtable
    /// 4. Update index with tombstone marker
    ///
    /// Note: The actual data is not immediately removed. Tombstones are
    /// removed during compaction.
    ///
    /// # Arguments
    ///
    /// * `key` - The key to delete
    ///
    /// # Returns
    ///
    /// Returns `Ok(())` on success or an error if the operation fails.
    ///
    /// # Errors
    ///
    /// Returns an error if:
    /// - WAL append fails
    /// - WAL sync fails
    ///
    /// # Example
    ///
    /// ```no_run
    /// # use uringkv::{Config, StorageEngine};
    /// # use std::path::PathBuf;
    /// # #[tokio::main]
    /// # async fn main() -> Result<(), Box<dyn std::error::Error>> {
    /// # let config = Config::new(PathBuf::from("./data"));
    /// # let engine = StorageEngine::new(config).await?;
    /// engine.put(b"key", b"value").await?;
    /// engine.delete(b"key").await?;
    /// 
    /// let value = engine.get(b"key").await?;
    /// assert_eq!(value, None);
    /// # Ok(())
    /// # }
    /// ```
    pub async fn delete(&self, key: &[u8]) -> Result<()> {
        let start = Instant::now();
        
        // Track memory allocation for key copy
        self.metrics.increment_allocations();
        
        // Get next sequence number
        let seq = self.sequence.fetch_add(1, Ordering::SeqCst);

        // Create WAL entry for delete
        let wal_entry = WalEntry::new_delete(key.to_vec()).with_sequence(seq);

        // Append to WAL
        let offset = self.wal.append(wal_entry).await?;

        // Sync WAL
        self.wal.sync().await?;

        // Insert tombstone in memtable
        {
            let memtable = self.memtable.read().unwrap();
            memtable.delete(key.to_vec(), seq);
        }

        // Update index with tombstone location
        self.index.insert(
            key.to_vec(),
            Location {
                file_type: FileType::Memtable,
                file_id: 0,
                offset,
                length: 0,
            },
        );

        // Check if memtable is full and trigger flush
        {
            let memtable = self.memtable.read().unwrap();
            if memtable.is_full() {
                drop(memtable);
                self.flush_memtable().await?;
            }
        }

        // Record metrics
        self.metrics.record_latency("delete", start.elapsed());
        self.metrics.increment_throughput();

        Ok(())
    }

    /// Performs a range query over keys.
    ///
    /// Returns all key-value pairs where `start <= key < end` in lexicographic order.
    /// The operation performs a multi-way merge of memtable and SST files,
    /// with newer entries overriding older ones. Tombstones are filtered out.
    ///
    /// # Arguments
    ///
    /// * `start` - Start of the key range (inclusive)
    /// * `end` - End of the key range (exclusive)
    ///
    /// # Returns
    ///
    /// Returns a vector of key-value pairs in sorted order, or an error if
    /// the operation fails.
    ///
    /// # Errors
    ///
    /// Returns an error if:
    /// - SST file read fails
    /// - Checksum verification fails
    ///
    /// # Example
    ///
    /// ```no_run
    /// # use uringkv::{Config, StorageEngine};
    /// # use std::path::PathBuf;
    /// # #[tokio::main]
    /// # async fn main() -> Result<(), Box<dyn std::error::Error>> {
    /// # let config = Config::new(PathBuf::from("./data"));
    /// # let engine = StorageEngine::new(config).await?;
    /// engine.put(b"user:1", b"Alice").await?;
    /// engine.put(b"user:2", b"Bob").await?;
    /// engine.put(b"user:3", b"Charlie").await?;
    /// 
    /// // Scan all users
    /// let users = engine.scan(b"user:", b"user:zzzz").await?;
    /// assert_eq!(users.len(), 3);
    /// # Ok(())
    /// # }
    /// ```
    pub async fn scan(&self, start: &[u8], end: &[u8]) -> Result<Vec<(Vec<u8>, Vec<u8>)>> {
        let scan_start = Instant::now();
        
        use std::collections::BTreeMap;

        // Collect entries from memtable
        let memtable_entries = {
            let memtable = self.memtable.read().unwrap();
            memtable.scan(start, end)
        };

        // Identify overlapping SST files
        let sst_files = self.sst_manager.get_overlapping_files(start, end);

        // Collect entries from SST files
        let mut sst_entries = Vec::new();
        for sst_file in sst_files {
            let entries = self.sst_manager.scan(&sst_file, start, end).await?;
            sst_entries.extend(entries);
        }

        // Perform multi-way merge using BTreeMap to maintain sorted order
        // and handle duplicates (keeping the latest version)
        let mut merged = BTreeMap::new();

        // Add SST entries first (older data)
        for (key, value) in sst_entries {
            merged.insert(key, Some(value));
        }

        // Add memtable entries (newer data, overrides SST entries)
        for (key, value) in memtable_entries {
            merged.insert(key, Some(value));
        }

        // Check for tombstones in memtable and mark them
        {
            let memtable = self.memtable.read().unwrap();
            for key in merged.keys().cloned().collect::<Vec<_>>() {
                if let Some(entry) = memtable.get(&key) {
                    if entry.value.is_none() {
                        // This is a tombstone, remove from results
                        merged.remove(&key);
                    }
                }
            }
        }

        // Convert to result vector, skipping tombstones
        let results: Vec<(Vec<u8>, Vec<u8>)> = merged
            .into_iter()
            .filter_map(|(k, v)| v.map(|val| (k, val)))
            .collect();

        // Record metrics
        self.metrics.record_latency("scan", scan_start.elapsed());
        self.metrics.increment_throughput();

        Ok(results)
    }

    /// Gracefully closes the storage engine.
    ///
    /// This method:
    /// 1. Stops the background compaction thread
    /// 2. Flushes memtable to SST if needed
    /// 3. Syncs WAL to ensure all data is persisted
    ///
    /// # Returns
    ///
    /// Returns `Ok(())` on success or an error if any operation fails.
    ///
    /// # Errors
    ///
    /// Returns an error if:
    /// - Memtable flush fails
    /// - WAL sync fails
    ///
    /// # Example
    ///
    /// ```no_run
    /// # use uringkv::{Config, StorageEngine};
    /// # use std::path::PathBuf;
    /// # #[tokio::main]
    /// # async fn main() -> Result<(), Box<dyn std::error::Error>> {
    /// # let config = Config::new(PathBuf::from("./data"));
    /// let engine = StorageEngine::new(config).await?;
    /// 
    /// // Perform operations...
    /// 
    /// // Gracefully close
    /// engine.close().await?;
    /// # Ok(())
    /// # }
    /// ```
    pub async fn close(&self) -> Result<()> {
        // Stop compactor
        {
            let mut compactor = self.compactor.lock().unwrap();
            compactor.stop();
        }

        // Flush memtable if needed
        let memtable = self.memtable.read().unwrap();
        if memtable.is_full() {
            drop(memtable);
            self.flush_memtable().await?;
        }

        // Sync WAL
        self.wal.sync().await?;

        Ok(())
    }

    /// Returns a reference to the metrics collector.
    ///
    /// Use this to access performance metrics such as latency percentiles
    /// and throughput counters.
    ///
    /// # Example
    ///
    /// ```no_run
    /// # use uringkv::{Config, StorageEngine};
    /// # use std::path::PathBuf;
    /// # #[tokio::main]
    /// # async fn main() -> Result<(), Box<dyn std::error::Error>> {
    /// # let config = Config::new(PathBuf::from("./data"));
    /// let engine = StorageEngine::new(config).await?;
    /// 
    /// // Perform operations...
    /// engine.put(b"key", b"value").await?;
    /// 
    /// // Get metrics
    /// let metrics = engine.metrics();
    /// let (p50, p95, p99) = metrics.get_percentiles("put");
    /// println!("PUT latency - p50: {}μs, p95: {}μs, p99: {}μs", p50, p95, p99);
    /// # Ok(())
    /// # }
    /// ```
    pub fn metrics(&self) -> &Arc<Metrics> {
        &self.metrics
    }

    /// Flush memtable to SST file
    async fn flush_memtable(&self) -> Result<()> {
        // Get all entries from memtable (including tombstones)
        let entries = {
            let memtable = self.memtable.read().unwrap();
            memtable.get_all_entries()
        };

        // Only flush if there are entries
        if !entries.is_empty() {
            // Write new SST file
            // The SST manager will track this file with bloom filters and metadata
            let _sst_file = self.sst_manager.write_sst(entries.clone()).await?;
            
            // Note: We don't add individual keys to the index anymore.
            // SST lookups use bloom filters and file metadata instead.
            // This prevents memory overflow when dealing with large SST files.
        }

        // Clear memtable after successful flush
        {
            let mut memtable = self.memtable.write().unwrap();
            memtable.clear();
        }

        Ok(())
    }
}




#[cfg(test)]
mod tests {
    use super::*;
    use crate::checksum::ChecksumAlgorithm;
    use crate::config::{CompactionStrategy, Config};
    use tempfile::TempDir;

    async fn create_test_engine() -> (StorageEngine, TempDir) {
        let temp_dir = TempDir::new().unwrap();
        let config = Config::new(temp_dir.path().to_path_buf())
            .with_wal_segment_size(1024 * 1024) // 1MB
            .with_memtable_size(64 * 1024)       // 64KB for easier testing
            .with_queue_depth(32)
            .with_compaction_strategy(CompactionStrategy::SizeTiered {
                size_ratio: 2.0,
                min_threshold: 4,
            })
            .with_checksum_algorithm(ChecksumAlgorithm::CRC32)
            .with_group_commit_interval(10);
        let engine = StorageEngine::new(config).await.unwrap();
        (engine, temp_dir)
    }

    #[tokio::test]
    async fn test_put_and_get() {
        let (engine, _temp_dir) = create_test_engine().await;

        // Test basic PUT and GET
        engine.put(b"key1", b"value1").await.unwrap();
        let result = engine.get(b"key1").await.unwrap();
        assert_eq!(result, Some(b"value1".to_vec()));

        // Test GET for non-existent key
        let result = engine.get(b"nonexistent").await.unwrap();
        assert_eq!(result, None);
    }

    #[tokio::test]
    async fn test_delete_with_tombstone() {
        let (engine, _temp_dir) = create_test_engine().await;

        // PUT a key
        engine.put(b"key1", b"value1").await.unwrap();
        assert_eq!(engine.get(b"key1").await.unwrap(), Some(b"value1".to_vec()));

        // DELETE the key
        engine.delete(b"key1").await.unwrap();

        // GET should return None
        let result = engine.get(b"key1").await.unwrap();
        assert_eq!(result, None);
    }

    #[tokio::test]
    async fn test_scan_operation() {
        let (engine, _temp_dir) = create_test_engine().await;

        // Insert multiple keys
        engine.put(b"key1", b"value1").await.unwrap();
        engine.put(b"key2", b"value2").await.unwrap();
        engine.put(b"key3", b"value3").await.unwrap();
        engine.put(b"key5", b"value5").await.unwrap();

        // Scan from key1 to key4
        let results = engine.scan(b"key1", b"key4").await.unwrap();
        
        assert_eq!(results.len(), 3);
        assert_eq!(results[0].0, b"key1");
        assert_eq!(results[0].1, b"value1");
        assert_eq!(results[1].0, b"key2");
        assert_eq!(results[1].1, b"value2");
        assert_eq!(results[2].0, b"key3");
        assert_eq!(results[2].1, b"value3");
    }

    #[tokio::test]
    async fn test_scan_with_tombstones() {
        let (engine, _temp_dir) = create_test_engine().await;

        // Insert keys
        engine.put(b"key1", b"value1").await.unwrap();
        engine.put(b"key2", b"value2").await.unwrap();
        engine.put(b"key3", b"value3").await.unwrap();

        // Delete key2
        engine.delete(b"key2").await.unwrap();

        // Scan should skip the deleted key
        let results = engine.scan(b"key1", b"key4").await.unwrap();
        
        assert_eq!(results.len(), 2);
        assert_eq!(results[0].0, b"key1");
        assert_eq!(results[1].0, b"key3");
    }

    #[tokio::test]
    async fn test_memtable_flush() {
        let (engine, _temp_dir) = create_test_engine().await;

        // Insert enough data to trigger flush (memtable size is 64KB)
        for i in 0..100 {
            let key = format!("key_{:04}", i);
            let value = vec![b'v'; 1000]; // 1KB value
            engine.put(key.as_bytes(), &value).await.unwrap();
        }

        // Give some time for async flush to complete
        tokio::time::sleep(tokio::time::Duration::from_millis(500)).await;

        // Check SST files
        let sst_files = engine.sst_manager.get_all_files();
        eprintln!("Number of SST files: {}", sst_files.len());
        for sst in &sst_files {
            eprintln!("SST {}: {} entries, min={:?}, max={:?}", 
                sst.id, sst.num_entries,
                String::from_utf8_lossy(&sst.min_key),
                String::from_utf8_lossy(&sst.max_key)
            );
            
            // Try to read key_0000 directly
            match engine.sst_manager.read(sst, b"key_0000").await {
                Ok(Some(v)) => eprintln!("  Successfully read key_0000, value len={}", v.len()),
                Ok(None) => eprintln!("  key_0000 not found in SST"),
                Err(e) => eprintln!("  Error reading key_0000: {:?}", e),
            }
        }

        // Check memtable
        let memtable = engine.memtable.read().unwrap();
        let memtable_entries = memtable.get_all_entries();
        eprintln!("Memtable has {} entries", memtable_entries.len());
        if memtable_entries.len() > 0 {
            eprintln!("First memtable key: {:?}", String::from_utf8_lossy(&memtable_entries[0].0));
            eprintln!("Last memtable key: {:?}", String::from_utf8_lossy(&memtable_entries[memtable_entries.len()-1].0));
        }
        drop(memtable);

        // Verify all keys can still be retrieved
        for i in 0..100 {
            let key = format!("key_{:04}", i);
            let result = engine.get(key.as_bytes()).await.unwrap();
            assert!(result.is_some(), "Key {} should be found", key);
            assert_eq!(result.unwrap().len(), 1000);
        }
    }

    #[tokio::test]
    async fn test_crash_recovery() {
        let temp_dir = TempDir::new().unwrap();
        let data_dir = temp_dir.path().to_path_buf();

        // Create engine and insert data
        {
            let config = Config::new(data_dir.clone())
                .with_wal_segment_size(1024 * 1024)
                .with_memtable_size(64 * 1024)
                .with_queue_depth(32)
                .with_compaction_strategy(CompactionStrategy::SizeTiered {
                    size_ratio: 2.0,
                    min_threshold: 4,
                })
                .with_checksum_algorithm(ChecksumAlgorithm::CRC32)
                .with_group_commit_interval(10);
            let engine = StorageEngine::new(config).await.unwrap();

            engine.put(b"key1", b"value1").await.unwrap();
            engine.put(b"key2", b"value2").await.unwrap();
            engine.delete(b"key1").await.unwrap();
            
            // Close engine
            engine.close().await.unwrap();
        }

        // Reopen engine (simulating crash recovery)
        {
            let config = Config::new(data_dir.clone())
                .with_wal_segment_size(1024 * 1024)
                .with_memtable_size(64 * 1024)
                .with_queue_depth(32)
                .with_compaction_strategy(CompactionStrategy::SizeTiered {
                    size_ratio: 2.0,
                    min_threshold: 4,
                })
                .with_checksum_algorithm(ChecksumAlgorithm::CRC32)
                .with_group_commit_interval(10);
            let engine = StorageEngine::new(config).await.unwrap();

            // Verify data was recovered
            assert_eq!(engine.get(b"key1").await.unwrap(), None); // Was deleted
            assert_eq!(engine.get(b"key2").await.unwrap(), Some(b"value2".to_vec()));
        }
    }

    #[tokio::test]
    async fn test_crash_recovery_with_sst_files() {
        let temp_dir = TempDir::new().unwrap();
        let data_dir = temp_dir.path().to_path_buf();

        // Create engine and insert enough data to trigger flush to SST
        {
            let config = Config::new(data_dir.clone())
                .with_wal_segment_size(1024 * 1024)
                .with_memtable_size(10 * 1024) // Small memtable to trigger flush
                .with_queue_depth(32)
                .with_compaction_strategy(CompactionStrategy::SizeTiered {
                    size_ratio: 2.0,
                    min_threshold: 4,
                })
                .with_checksum_algorithm(ChecksumAlgorithm::CRC32)
                .with_group_commit_interval(10);
            let engine = StorageEngine::new(config).await.unwrap();

            // Insert data that will be flushed to SST
            for i in 0..20 {
                let key = format!("sst_key_{:03}", i);
                let value = vec![b'v'; 500]; // 500 bytes per value
                engine.put(key.as_bytes(), &value).await.unwrap();
            }

            // Insert more data that stays in WAL/memtable
            engine.put(b"wal_key1", b"wal_value1").await.unwrap();
            engine.put(b"wal_key2", b"wal_value2").await.unwrap();
            
            // Close engine
            engine.close().await.unwrap();
        }

        // Reopen engine (simulating crash recovery)
        {
            let config = Config::new(data_dir.clone())
                .with_wal_segment_size(1024 * 1024)
                .with_memtable_size(10 * 1024)
                .with_queue_depth(32)
                .with_compaction_strategy(CompactionStrategy::SizeTiered {
                    size_ratio: 2.0,
                    min_threshold: 4,
                })
                .with_checksum_algorithm(ChecksumAlgorithm::CRC32)
                .with_group_commit_interval(10);
            let engine = StorageEngine::new(config).await.unwrap();

            // Verify SST data was recovered
            for i in 0..20 {
                let key = format!("sst_key_{:03}", i);
                let result = engine.get(key.as_bytes()).await.unwrap();
                assert!(result.is_some(), "Key {} should be recovered from SST", key);
                assert_eq!(result.unwrap().len(), 500);
            }

            // Verify WAL data was recovered
            assert_eq!(engine.get(b"wal_key1").await.unwrap(), Some(b"wal_value1".to_vec()));
            assert_eq!(engine.get(b"wal_key2").await.unwrap(), Some(b"wal_value2".to_vec()));
        }
    }

    #[tokio::test]
    async fn test_crash_recovery_with_corrupted_wal() {
        use std::fs::OpenOptions;
        use std::io::Write;
        
        let temp_dir = TempDir::new().unwrap();
        let data_dir = temp_dir.path().to_path_buf();

        // Create engine and insert data
        {
            let config = Config::new(data_dir.clone())
                .with_wal_segment_size(1024 * 1024)
                .with_memtable_size(64 * 1024)
                .with_queue_depth(32)
                .with_compaction_strategy(CompactionStrategy::SizeTiered {
                    size_ratio: 2.0,
                    min_threshold: 4,
                })
                .with_checksum_algorithm(ChecksumAlgorithm::CRC32)
                .with_group_commit_interval(10);
            let engine = StorageEngine::new(config).await.unwrap();

            // Insert multiple entries
            engine.put(b"key1", b"value1").await.unwrap();
            engine.put(b"key2", b"value2").await.unwrap();
            engine.put(b"key3", b"value3").await.unwrap();
            
            // Close engine
            engine.close().await.unwrap();
        }

        // Corrupt the WAL file
        {
            let wal_dir = data_dir.join("wal");
            let wal_files: Vec<_> = std::fs::read_dir(&wal_dir)
                .unwrap()
                .filter_map(|e| e.ok())
                .filter(|e| e.path().extension().and_then(|s| s.to_str()) == Some("wal"))
                .collect();
            
            assert!(!wal_files.is_empty(), "Should have at least one WAL file");
            
            let wal_path = wal_files[0].path();
            let mut file = OpenOptions::new().write(true).open(&wal_path).unwrap();
            
            // Corrupt data at offset 8192 (second page)
            file.seek(SeekFrom::Start(8192)).unwrap();
            file.write_all(&[0xFF; 1024]).unwrap();
            file.sync_all().unwrap();
        }

        // Reopen engine (should skip corrupted entries and recover valid ones)
        {
            let config = Config::new(data_dir.clone())
                .with_wal_segment_size(1024 * 1024)
                .with_memtable_size(64 * 1024)
                .with_queue_depth(32)
                .with_compaction_strategy(CompactionStrategy::SizeTiered {
                    size_ratio: 2.0,
                    min_threshold: 4,
                })
                .with_checksum_algorithm(ChecksumAlgorithm::CRC32)
                .with_group_commit_interval(10);
            let engine = StorageEngine::new(config).await.unwrap();

            // First entry should be recovered (before corruption)
            assert_eq!(engine.get(b"key1").await.unwrap(), Some(b"value1".to_vec()));
            
            // Other entries might not be recovered depending on where corruption occurred
            // But the engine should start successfully without crashing
        }
    }

    #[tokio::test]
    async fn test_crash_recovery_with_torn_writes() {
        use std::fs::OpenOptions;
        use std::io::Write;
        
        let temp_dir = TempDir::new().unwrap();
        let data_dir = temp_dir.path().to_path_buf();

        // Create engine and insert data
        {
            let config = Config::new(data_dir.clone())
                .with_wal_segment_size(1024 * 1024)
                .with_memtable_size(64 * 1024)
                .with_queue_depth(32)
                .with_compaction_strategy(CompactionStrategy::SizeTiered {
                    size_ratio: 2.0,
                    min_threshold: 4,
                })
                .with_checksum_algorithm(ChecksumAlgorithm::CRC32)
                .with_group_commit_interval(10);
            let engine = StorageEngine::new(config).await.unwrap();

            // Insert entries
            engine.put(b"key1", b"value1").await.unwrap();
            engine.put(b"key2", b"value2").await.unwrap();
            
            // Close engine
            engine.close().await.unwrap();
        }

        // Simulate torn write by truncating the WAL file in the middle of an entry
        {
            let wal_dir = data_dir.join("wal");
            let wal_files: Vec<_> = std::fs::read_dir(&wal_dir)
                .unwrap()
                .filter_map(|e| e.ok())
                .filter(|e| e.path().extension().and_then(|s| s.to_str()) == Some("wal"))
                .collect();
            
            if !wal_files.is_empty() {
                let wal_path = wal_files[0].path();
                let file = OpenOptions::new().write(true).open(&wal_path).unwrap();
                
                // Truncate to partial entry (e.g., 4100 bytes - in the middle of second entry)
                file.set_len(4100).unwrap();
                file.sync_all().unwrap();
            }
        }

        // Reopen engine (should handle torn write gracefully)
        {
            let config = Config::new(data_dir.clone())
                .with_wal_segment_size(1024 * 1024)
                .with_memtable_size(64 * 1024)
                .with_queue_depth(32)
                .with_compaction_strategy(CompactionStrategy::SizeTiered {
                    size_ratio: 2.0,
                    min_threshold: 4,
                })
                .with_checksum_algorithm(ChecksumAlgorithm::CRC32)
                .with_group_commit_interval(10);
            let engine = StorageEngine::new(config).await.unwrap();

            // First entry should be recovered
            assert_eq!(engine.get(b"key1").await.unwrap(), Some(b"value1".to_vec()));
            
            // Second entry might not be recovered due to torn write
            // But engine should start successfully
        }
    }

    #[tokio::test]
    async fn test_crash_recovery_restores_all_committed_data() {
        let temp_dir = TempDir::new().unwrap();
        let data_dir = temp_dir.path().to_path_buf();

        let test_data: Vec<(Vec<u8>, Vec<u8>)> = (0..50)
            .map(|i| {
                (
                    format!("key_{:03}", i).into_bytes(),
                    format!("value_{:03}", i).into_bytes(),
                )
            })
            .collect();

        // Create engine and insert data
        {
            let config = Config::new(data_dir.clone())
                .with_wal_segment_size(1024 * 1024)
                .with_memtable_size(64 * 1024)
                .with_queue_depth(32)
                .with_compaction_strategy(CompactionStrategy::SizeTiered {
                    size_ratio: 2.0,
                    min_threshold: 4,
                })
                .with_checksum_algorithm(ChecksumAlgorithm::CRC32)
                .with_group_commit_interval(10);
            let engine = StorageEngine::new(config).await.unwrap();

            // Insert all test data
            for (key, value) in &test_data {
                engine.put(key, value).await.unwrap();
            }
            
            // Close engine properly (simulating clean shutdown)
            engine.close().await.unwrap();
        }

        // Reopen engine and verify all data is recovered
        {
            let config = Config::new(data_dir.clone())
                .with_wal_segment_size(1024 * 1024)
                .with_memtable_size(64 * 1024)
                .with_queue_depth(32)
                .with_compaction_strategy(CompactionStrategy::SizeTiered {
                    size_ratio: 2.0,
                    min_threshold: 4,
                })
                .with_checksum_algorithm(ChecksumAlgorithm::CRC32)
                .with_group_commit_interval(10);
            let engine = StorageEngine::new(config).await.unwrap();

            // Verify all committed data is recovered
            for (key, expected_value) in &test_data {
                let result = engine.get(key).await.unwrap();
                assert_eq!(
                    result,
                    Some(expected_value.clone()),
                    "Key {:?} should be recovered with correct value",
                    String::from_utf8_lossy(key)
                );
            }
        }
    }

    #[tokio::test]
    async fn test_crash_recovery_sequence_number() {
        let temp_dir = TempDir::new().unwrap();
        let data_dir = temp_dir.path().to_path_buf();

        // Create engine and insert data
        {
            let config = Config::new(data_dir.clone())
                .with_wal_segment_size(1024 * 1024)
                .with_memtable_size(64 * 1024)
                .with_queue_depth(32)
                .with_compaction_strategy(CompactionStrategy::SizeTiered {
                    size_ratio: 2.0,
                    min_threshold: 4,
                })
                .with_checksum_algorithm(ChecksumAlgorithm::CRC32)
                .with_group_commit_interval(10);
            let engine = StorageEngine::new(config).await.unwrap();

            // Insert 10 entries
            for i in 0..10 {
                let key = format!("key_{}", i);
                let value = format!("value_{}", i);
                engine.put(key.as_bytes(), value.as_bytes()).await.unwrap();
            }
            
            engine.close().await.unwrap();
        }

        // Reopen and insert more data
        {
            let config = Config::new(data_dir.clone())
                .with_wal_segment_size(1024 * 1024)
                .with_memtable_size(64 * 1024)
                .with_queue_depth(32)
                .with_compaction_strategy(CompactionStrategy::SizeTiered {
                    size_ratio: 2.0,
                    min_threshold: 4,
                })
                .with_checksum_algorithm(ChecksumAlgorithm::CRC32)
                .with_group_commit_interval(10);
            let engine = StorageEngine::new(config).await.unwrap();

            // Insert more entries (sequence should continue from where it left off)
            for i in 10..20 {
                let key = format!("key_{}", i);
                let value = format!("value_{}", i);
                engine.put(key.as_bytes(), value.as_bytes()).await.unwrap();
            }

            // Verify all data is present
            for i in 0..20 {
                let key = format!("key_{}", i);
                let expected_value = format!("value_{}", i);
                let result = engine.get(key.as_bytes()).await.unwrap();
                assert_eq!(result, Some(expected_value.into_bytes()));
            }
        }
    }

    #[tokio::test]
    async fn test_update_existing_key() {
        let (engine, _temp_dir) = create_test_engine().await;

        // Insert a key
        engine.put(b"key1", b"value1").await.unwrap();
        assert_eq!(engine.get(b"key1").await.unwrap(), Some(b"value1".to_vec()));

        // Update the key
        engine.put(b"key1", b"value2").await.unwrap();
        assert_eq!(engine.get(b"key1").await.unwrap(), Some(b"value2".to_vec()));
    }

    #[tokio::test]
    async fn test_multiple_operations() {
        let (engine, _temp_dir) = create_test_engine().await;

        // Perform a mix of operations
        engine.put(b"a", b"1").await.unwrap();
        engine.put(b"b", b"2").await.unwrap();
        engine.put(b"c", b"3").await.unwrap();
        engine.delete(b"b").await.unwrap();
        engine.put(b"d", b"4").await.unwrap();
        engine.put(b"a", b"5").await.unwrap(); // Update

        // Verify final state
        assert_eq!(engine.get(b"a").await.unwrap(), Some(b"5".to_vec()));
        assert_eq!(engine.get(b"b").await.unwrap(), None);
        assert_eq!(engine.get(b"c").await.unwrap(), Some(b"3".to_vec()));
        assert_eq!(engine.get(b"d").await.unwrap(), Some(b"4".to_vec()));
    }
}
