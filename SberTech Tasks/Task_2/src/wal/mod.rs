use crate::config::Config;
use crate::entry::{WalEntry, PAGE_SIZE};
use crate::error::{Result, StorageError};
use crate::io_uring::IoUringContext;
use crate::metrics::Metrics;
use std::fs::{File, OpenOptions};
use std::os::unix::io::AsRawFd;
use std::path::{Path, PathBuf};
use std::sync::{Arc, Mutex};
use std::time::Duration;
use tokio::sync::Notify;

/// WAL segment representing a single WAL file
pub struct WalSegment {
    /// Segment file ID
    file_id: u32,
    /// Path to the segment file
    path: PathBuf,
    /// File handle
    file: File,
    /// Current write offset in the segment
    offset: u64,
    /// Buffer for batching writes before flush
    buffer: Vec<u8>,
    /// Maximum segment size
    max_size: u64,
}

impl WalSegment {
    /// Create a new WAL segment
    pub fn create(data_dir: &Path, file_id: u32, max_size: u64) -> Result<Self> {
        let path = data_dir.join(format!("{:08}.wal", file_id));
        
        let file = OpenOptions::new()
            .create(true)
            .write(true)
            .read(true)
            .open(&path)?;
        
        Ok(Self {
            file_id,
            path,
            file,
            offset: 0,
            buffer: Vec::new(),
            max_size,
        })
    }
    
    /// Open an existing WAL segment
    pub fn open(path: PathBuf, max_size: u64) -> Result<Self> {
        let file = OpenOptions::new()
            .write(true)
            .read(true)
            .open(&path)?;
        
        // Extract file_id from filename
        let file_name = path.file_stem()
            .and_then(|s| s.to_str())
            .ok_or_else(|| StorageError::ConfigError("Invalid WAL filename".to_string()))?;
        
        let file_id = file_name.parse::<u32>()
            .map_err(|_| StorageError::ConfigError("Invalid WAL file ID".to_string()))?;
        
        // Get current file size as offset
        let metadata = file.metadata()?;
        let offset = metadata.len();
        
        Ok(Self {
            file_id,
            path,
            file,
            offset,
            buffer: Vec::new(),
            max_size,
        })
    }
    
    /// Append data to the buffer
    pub fn append_to_buffer(&mut self, data: Vec<u8>) {
        self.buffer.extend_from_slice(&data);
    }
    
    /// Flush the buffer to disk using standard I/O (more reliable for testing)
    pub async fn flush(&mut self, _io_uring: &mut IoUringContext) -> Result<()> {
        use std::io::{Write, Seek, SeekFrom};
        
        if self.buffer.is_empty() {
            return Ok(());
        }
        
        // Use standard I/O for writes (more reliable than io_uring for WAL)
        self.file.seek(SeekFrom::Start(self.offset))?;
        self.file.write_all(&self.buffer)?;
        self.file.flush()?;  // Ensure data is written to OS buffers
        self.file.sync_all()?;  // Force sync to disk immediately
        
        self.offset += self.buffer.len() as u64;
        self.buffer.clear();
        
        Ok(())
    }
    
    /// Sync the segment to disk
    pub async fn sync(&self, io_uring: &mut IoUringContext) -> Result<()> {
        let fd = self.file.as_raw_fd();
        io_uring.fdatasync(fd).await
    }
    
    /// Check if the segment is full
    pub fn is_full(&self) -> bool {
        self.offset + self.buffer.len() as u64 >= self.max_size
    }
    
    /// Get the current offset
    pub fn offset(&self) -> u64 {
        self.offset
    }
    
    /// Get the file ID
    pub fn file_id(&self) -> u32 {
        self.file_id
    }
    
    /// Get the path
    pub fn path(&self) -> &Path {
        &self.path
    }
    
    /// Get the file handle
    pub fn file(&self) -> &File {
        &self.file
    }
}

/// Group commit mechanism for batching fsync operations
pub struct GroupCommit {
    /// Pending operations waiting for commit
    pending: Arc<Mutex<Vec<Arc<Notify>>>>,
    /// Commit interval
    _interval: Duration,
    /// Flag to indicate if commit thread is running
    _running: Arc<Mutex<bool>>,
}

impl GroupCommit {
    /// Create a new GroupCommit
    pub fn new(interval_ms: u64) -> Self {
        Self {
            pending: Arc::new(Mutex::new(Vec::new())),
            _interval: Duration::from_millis(interval_ms),
            _running: Arc::new(Mutex::new(false)),
        }
    }
    
    /// Register an operation for group commit
    pub fn register(&self) -> Arc<Notify> {
        let notify = Arc::new(Notify::new());
        let mut pending = self.pending.lock().unwrap();
        pending.push(notify.clone());
        notify
    }
    
    /// Commit all pending operations
    pub fn commit_all(&self) {
        let mut pending = self.pending.lock().unwrap();
        for notify in pending.drain(..) {
            notify.notify_one();
        }
    }
    
    /// Get the number of pending operations
    pub fn pending_count(&self) -> usize {
        self.pending.lock().unwrap().len()
    }
}

/// WAL manager for write-ahead logging
pub struct WalManager {
    /// Current active segment
    current_segment: Arc<Mutex<WalSegment>>,
    /// All segment paths
    segments: Arc<Mutex<Vec<PathBuf>>>,
    /// Data directory
    data_dir: PathBuf,
    /// Maximum segment size
    segment_size: u64,
    /// io_uring context
    io_uring: Arc<Mutex<IoUringContext>>,
    /// Group commit mechanism
    group_commit: Arc<GroupCommit>,
    /// Configuration
    config: Config,
    /// Next segment ID
    next_segment_id: Arc<Mutex<u32>>,
    /// Metrics collector (optional for backward compatibility)
    metrics: Option<Arc<Metrics>>,
}

impl WalManager {
    /// Create a new WAL manager
    pub async fn new(config: Config, io_uring: Arc<Mutex<IoUringContext>>) -> Result<Self> {
        let wal_dir = config.data_dir.join("wal");
        std::fs::create_dir_all(&wal_dir)?;
        
        // Find existing segments
        let mut segments = Vec::new();
        let mut max_id = 0u32;
        
        if let Ok(entries) = std::fs::read_dir(&wal_dir) {
            for entry in entries.flatten() {
                let path = entry.path();
                if path.extension().and_then(|s| s.to_str()) == Some("wal") {
                    segments.push(path.clone());
                    
                    // Extract file ID
                    if let Some(file_name) = path.file_stem().and_then(|s| s.to_str()) {
                        if let Ok(id) = file_name.parse::<u32>() {
                            max_id = max_id.max(id);
                        }
                    }
                }
            }
        }
        
        // Sort segments by ID
        segments.sort();
        
        // Create or open the current segment
        let next_id = max_id + 1;
        let current_segment = if let Some(last_segment) = segments.last() {
            let segment = WalSegment::open(last_segment.clone(), config.wal_segment_size)?;
            if segment.is_full() {
                // Create a new segment if the last one is full
                WalSegment::create(&wal_dir, next_id, config.wal_segment_size)?
            } else {
                segment
            }
        } else {
            WalSegment::create(&wal_dir, next_id, config.wal_segment_size)?
        };
        
        let group_commit = Arc::new(GroupCommit::new(config.group_commit_interval_ms));
        
        Ok(Self {
            current_segment: Arc::new(Mutex::new(current_segment)),
            segments: Arc::new(Mutex::new(segments)),
            data_dir: wal_dir,
            segment_size: config.wal_segment_size,
            io_uring,
            group_commit,
            config,
            next_segment_id: Arc::new(Mutex::new(next_id + 1)),
            metrics: None,
        })
    }
    
    /// Set the metrics collector for tracking fsync operations
    pub fn set_metrics(&mut self, metrics: Arc<Metrics>) {
        self.metrics = Some(metrics);
    }
    
    /// Append a WAL entry
    pub async fn append(&self, entry: WalEntry) -> Result<u64> {
        let serialized = entry.serialize(self.config.checksum_algorithm);
        
        let mut segment = self.current_segment.lock().unwrap();
        
        // Check if we need to rotate
        if segment.is_full() {
            drop(segment);
            self.rotate_segment().await?;
            segment = self.current_segment.lock().unwrap();
        }
        
        let offset = segment.offset() + segment.buffer.len() as u64;
        segment.append_to_buffer(serialized);
        
        Ok(offset)
    }
    
    /// Sync the current segment with group commit
    pub async fn sync(&self) -> Result<()> {
        // Register for group commit
        let notify = self.group_commit.register();
        
        // Flush buffer to disk
        {
            let mut segment = self.current_segment.lock().unwrap();
            let mut io_uring = self.io_uring.lock().unwrap();
            segment.flush(&mut io_uring).await?;
        }
        
        // Check if we should trigger commit
        if self.group_commit.pending_count() >= 1 {
            // Perform sync
            let segment = self.current_segment.lock().unwrap();
            let mut io_uring = self.io_uring.lock().unwrap();
            segment.sync(&mut io_uring).await?;
            
            // Track fdatasync call in metrics
            if let Some(metrics) = &self.metrics {
                metrics.increment_fdatasync();
            }
            
            // Notify all pending operations
            self.group_commit.commit_all();
        } else {
            // Wait for group commit
            notify.notified().await;
        }
        
        Ok(())
    }
    
    /// Rotate to a new segment
    async fn rotate_segment(&self) -> Result<()> {
        let mut segment = self.current_segment.lock().unwrap();
        
        // Flush current segment
        let mut io_uring = self.io_uring.lock().unwrap();
        segment.flush(&mut io_uring).await?;
        segment.sync(&mut io_uring).await?;
        
        // Track fdatasync call in metrics
        if let Some(metrics) = &self.metrics {
            metrics.increment_fdatasync();
        }
        
        drop(io_uring);
        
        // Add current segment to segments list
        let mut segments = self.segments.lock().unwrap();
        segments.push(segment.path().to_path_buf());
        
        // Create new segment
        let mut next_id = self.next_segment_id.lock().unwrap();
        let new_segment = WalSegment::create(&self.data_dir, *next_id, self.segment_size)?;
        *next_id += 1;
        
        *segment = new_segment;
        
        Ok(())
    }
    
    /// Recover WAL entries from all segments
    pub async fn recover(&self) -> Result<Vec<WalEntry>> {
        // Ensure current segment file is fully synced to disk
        {
            let current_segment = self.current_segment.lock().unwrap();
            current_segment.file().sync_all()?;
        }
        
        let segments = self.segments.lock().unwrap().clone();
        let mut entries = Vec::new();
        
        for segment_path in segments {
            let segment_entries = self.recover_segment(&segment_path).await?;
            entries.extend(segment_entries);
        }
        
        // Also recover from current segment
        let current_segment = self.current_segment.lock().unwrap();
        let current_entries = self.recover_segment(current_segment.path()).await?;
        entries.extend(current_entries);
        
        Ok(entries)
    }
    
    /// Recover entries from a single segment
    async fn recover_segment(&self, path: &Path) -> Result<Vec<WalEntry>> {
        use std::io::Read;
        use std::fs::File;
        
        tracing::info!("Recovering WAL segment: {:?}", path);
        
        // Open file and ensure all data is synced
        let file = File::open(path)?;
        file.sync_all()?;  // Ensure all data is flushed to disk
        drop(file);
        
        // Reopen and read the entire file into memory for recovery
        let mut file = OpenOptions::new().read(true).open(path)?;
        let metadata = file.metadata()?;
        let file_size = metadata.len();
        
        if file_size == 0 {
            tracing::info!("WAL segment is empty, skipping");
            return Ok(Vec::new());
        }
        
        let mut file_data = Vec::new();
        file.read_to_end(&mut file_data)?;
        tracing::debug!("WAL segment has {} bytes", file_data.len());
        
        let mut entries = Vec::new();
        let mut offset = 0usize;
        let mut corruption_count = 0u32;
        
        while offset < file_data.len() {
            // Calculate how much data is remaining
            let remaining = file_data.len() - offset;
            
            // We need at least the header to determine entry size
            if remaining < 24 {
                tracing::debug!("Not enough data for header at offset {}, stopping recovery", offset);
                break;
            }
            
            // Try to deserialize entry from remaining data
            let slice = &file_data[offset..];
            
            match WalEntry::deserialize(slice, self.config.checksum_algorithm) {
                Ok(entry) => {
                    let entry_size = entry.serialized_size();
                    tracing::debug!(
                        "Recovered entry at offset {}: key={:?}, op={:?}, seq={}",
                        offset,
                        String::from_utf8_lossy(&entry.key),
                        entry.op_type,
                        entry.sequence
                    );
                    entries.push(entry);
                    offset += entry_size;
                }
                Err(e) => {
                    // Log corruption warning and skip to next page boundary
                    corruption_count += 1;
                    tracing::warn!(
                        "WAL corruption detected at offset {} in {:?}: {:?}",
                        offset,
                        path,
                        e
                    );
                    
                    // Skip corrupted entries with invalid checksums
                    // Continue recovery with valid entries by moving to next page boundary
                    let next_page = ((offset / PAGE_SIZE) + 1) * PAGE_SIZE;
                    tracing::warn!(
                        "Skipping corrupted data from offset {} to {}, continuing recovery",
                        offset,
                        next_page
                    );
                    offset = next_page;
                }
            }
        }
        
        if corruption_count > 0 {
            tracing::warn!(
                "WAL segment {:?} had {} corrupted entries that were skipped",
                path,
                corruption_count
            );
        }
        
        tracing::info!(
            "Recovered {} valid entries from WAL segment {:?}",
            entries.len(),
            path
        );
        Ok(entries)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::checksum::ChecksumAlgorithm;
    use crate::entry::{OpType, WalEntry};
    use tempfile::TempDir;

    /// Helper function to create a test config
    fn create_test_config(data_dir: PathBuf) -> Config {
        Config::new(data_dir)
            .with_wal_segment_size(1024 * 1024) // 1MB for testing
            .with_queue_depth(32)
            .with_group_commit_interval(10)
    }

    /// Helper function to create a test WAL manager
    async fn create_test_wal_manager(temp_dir: &TempDir) -> WalManager {
        let config = create_test_config(temp_dir.path().to_path_buf());
        let io_uring = Arc::new(Mutex::new(IoUringContext::new(32, false).unwrap()));
        WalManager::new(config, io_uring).await.unwrap()
    }

    #[tokio::test]
    async fn test_wal_append_and_sync() {
        let temp_dir = TempDir::new().unwrap();
        let wal_manager = create_test_wal_manager(&temp_dir).await;

        // Create a PUT entry
        let entry = WalEntry::new_put(b"test_key".to_vec(), b"test_value".to_vec());
        let serialized = entry.serialize(ChecksumAlgorithm::CRC32);
        eprintln!("Entry serialized size: {} bytes", serialized.len());
        eprintln!("Entry checksum: {}", entry.checksum);
        
        // Append the entry
        let offset = wal_manager.append(entry.clone()).await.unwrap();
        assert_eq!(offset, 0); // First entry should be at offset 0

        // Sync the entry
        wal_manager.sync().await.unwrap();
        
        // Check what's actually in the file
        let current_segment = wal_manager.current_segment.lock().unwrap();
        let path = current_segment.path().to_path_buf();
        drop(current_segment);
        
        use std::io::Read;
        let mut file = std::fs::File::open(&path).unwrap();
        let mut file_data = Vec::new();
        file.read_to_end(&mut file_data).unwrap();
        eprintln!("File contains {} bytes", file_data.len());
        eprintln!("First 32 bytes: {:?}", &file_data[0..32.min(file_data.len())]);

        // Verify the entry was written by recovering
        let recovered = wal_manager.recover().await.unwrap();
        eprintln!("Recovered {} entries", recovered.len());
        assert_eq!(recovered.len(), 1);
        assert_eq!(recovered[0].key, b"test_key");
        assert_eq!(recovered[0].value, b"test_value");
        assert_eq!(recovered[0].op_type, OpType::Put);
    }

    #[tokio::test]
    async fn test_wal_append_multiple_entries() {
        let temp_dir = TempDir::new().unwrap();
        let wal_manager = create_test_wal_manager(&temp_dir).await;

        // Append just 2 entries for simpler debugging
        let entry1 = WalEntry::new_put(b"key_0".to_vec(), b"value_0".to_vec());
        let entry2 = WalEntry::new_put(b"key_1".to_vec(), b"value_1".to_vec());
        
        let ser1 = entry1.serialize(ChecksumAlgorithm::CRC32);
        let ser2 = entry2.serialize(ChecksumAlgorithm::CRC32);
        eprintln!("Entry 1 first 32 bytes: {:?}", &ser1[0..32]);
        eprintln!("Entry 2 first 32 bytes: {:?}", &ser2[0..32]);
        
        wal_manager.append(entry1).await.unwrap();
        wal_manager.append(entry2).await.unwrap();

        // Sync all entries
        wal_manager.sync().await.unwrap();
        
        // Check what's in the file
        let current_segment = wal_manager.current_segment.lock().unwrap();
        let path = current_segment.path().to_path_buf();
        drop(current_segment);
        
        use std::io::Read;
        let mut file = std::fs::File::open(&path).unwrap();
        let mut file_data = Vec::new();
        file.read_to_end(&mut file_data).unwrap();
        eprintln!("File size: {} bytes", file_data.len());
        eprintln!("File entry 1 first 32 bytes: {:?}", &file_data[0..32]);
        eprintln!("File entry 2 first 32 bytes: {:?}", &file_data[4096..4128]);

        // Recover and verify
        let recovered = wal_manager.recover().await.unwrap();
        eprintln!("Recovered {} entries", recovered.len());
        assert_eq!(recovered.len(), 2);
        assert_eq!(recovered[0].key, b"key_0");
        assert_eq!(recovered[1].key, b"key_1");
    }

    #[tokio::test]
    async fn test_wal_delete_operation() {
        let temp_dir = TempDir::new().unwrap();
        let wal_manager = create_test_wal_manager(&temp_dir).await;

        // Append a PUT entry
        let put_entry = WalEntry::new_put(b"key1".to_vec(), b"value1".to_vec());
        wal_manager.append(put_entry).await.unwrap();

        // Append a DELETE entry
        let delete_entry = WalEntry::new_delete(b"key1".to_vec());
        wal_manager.append(delete_entry).await.unwrap();

        // Sync
        wal_manager.sync().await.unwrap();

        // Recover and verify
        let recovered = wal_manager.recover().await.unwrap();
        assert_eq!(recovered.len(), 2);
        assert_eq!(recovered[0].op_type, OpType::Put);
        assert_eq!(recovered[1].op_type, OpType::Delete);
        assert_eq!(recovered[1].key, b"key1");
        assert_eq!(recovered[1].value.len(), 0);
    }

    #[tokio::test]
    async fn test_wal_segment_rotation() {
        let temp_dir = TempDir::new().unwrap();
        let config = create_test_config(temp_dir.path().to_path_buf())
            .with_wal_segment_size(8192); // Small segment size to trigger rotation
        let io_uring = Arc::new(Mutex::new(IoUringContext::new(32, false).unwrap()));
        let wal_manager = WalManager::new(config, io_uring).await.unwrap();

        // Append entries until segment rotates
        // Each entry is aligned to 4KB, so 2 entries should fill 8KB segment
        let entry1 = WalEntry::new_put(b"key1".to_vec(), b"value1".to_vec());
        wal_manager.append(entry1).await.unwrap();
        wal_manager.sync().await.unwrap();

        let entry2 = WalEntry::new_put(b"key2".to_vec(), b"value2".to_vec());
        wal_manager.append(entry2).await.unwrap();
        wal_manager.sync().await.unwrap();

        // This should trigger rotation
        let entry3 = WalEntry::new_put(b"key3".to_vec(), b"value3".to_vec());
        wal_manager.append(entry3).await.unwrap();
        wal_manager.sync().await.unwrap();

        // Verify all entries can be recovered
        let recovered = wal_manager.recover().await.unwrap();
        assert_eq!(recovered.len(), 3);
        assert_eq!(recovered[0].key, b"key1");
        assert_eq!(recovered[1].key, b"key2");
        assert_eq!(recovered[2].key, b"key3");

        // Verify multiple segment files exist
        let wal_dir = temp_dir.path().join("wal");
        let entries: Vec<_> = std::fs::read_dir(&wal_dir)
            .unwrap()
            .filter_map(|e| e.ok())
            .filter(|e| e.path().extension().and_then(|s| s.to_str()) == Some("wal"))
            .collect();
        assert!(entries.len() >= 2, "Expected at least 2 WAL segments");
    }

    #[tokio::test]
    async fn test_wal_recovery_with_corrupted_entries() {
        let temp_dir = TempDir::new().unwrap();
        let wal_manager = create_test_wal_manager(&temp_dir).await;

        // Append valid entries
        let entry1 = WalEntry::new_put(b"key1".to_vec(), b"value1".to_vec());
        wal_manager.append(entry1).await.unwrap();
        wal_manager.sync().await.unwrap();

        let entry2 = WalEntry::new_put(b"key2".to_vec(), b"value2".to_vec());
        wal_manager.append(entry2).await.unwrap();
        wal_manager.sync().await.unwrap();

        // Corrupt the WAL file by writing garbage data
        let current_segment = wal_manager.current_segment.lock().unwrap();
        let wal_path = current_segment.path().to_path_buf();
        drop(current_segment);

        // Write corrupted data at a page boundary
        let mut file = OpenOptions::new().write(true).open(&wal_path).unwrap();
        use std::io::{Seek, SeekFrom, Write};
        file.seek(SeekFrom::Start(8192)).unwrap(); // Skip first two entries
        file.write_all(&[0xFF; 4096]).unwrap(); // Write garbage
        drop(file);

        // Append another valid entry after corruption
        let entry3 = WalEntry::new_put(b"key3".to_vec(), b"value3".to_vec());
        wal_manager.append(entry3).await.unwrap();
        wal_manager.sync().await.unwrap();

        // Recover - should skip corrupted entry and recover valid ones
        let recovered = wal_manager.recover().await.unwrap();
        
        // We should recover at least the first 2 valid entries
        // The third entry might not be recovered if it's after corruption
        assert!(recovered.len() >= 2);
        assert_eq!(recovered[0].key, b"key1");
        assert_eq!(recovered[1].key, b"key2");
    }

    #[tokio::test]
    async fn test_wal_recovery_empty_segment() {
        let temp_dir = TempDir::new().unwrap();
        let wal_manager = create_test_wal_manager(&temp_dir).await;

        // Don't append anything, just recover
        let recovered = wal_manager.recover().await.unwrap();
        assert_eq!(recovered.len(), 0);
    }

    #[tokio::test]
    async fn test_group_commit_batching() {
        let temp_dir = TempDir::new().unwrap();
        let wal_manager = create_test_wal_manager(&temp_dir).await;

        // Append multiple entries
        let entry1 = WalEntry::new_put(b"key1".to_vec(), b"value1".to_vec());
        let entry2 = WalEntry::new_put(b"key2".to_vec(), b"value2".to_vec());
        let entry3 = WalEntry::new_put(b"key3".to_vec(), b"value3".to_vec());

        wal_manager.append(entry1).await.unwrap();
        wal_manager.append(entry2).await.unwrap();
        wal_manager.append(entry3).await.unwrap();

        // Sync should batch all pending operations
        wal_manager.sync().await.unwrap();

        // Verify all entries were written
        let recovered = wal_manager.recover().await.unwrap();
        assert_eq!(recovered.len(), 3);
    }

    #[tokio::test]
    async fn test_group_commit_pending_count() {
        let group_commit = GroupCommit::new(10);

        assert_eq!(group_commit.pending_count(), 0);

        let _notify1 = group_commit.register();
        assert_eq!(group_commit.pending_count(), 1);

        let _notify2 = group_commit.register();
        assert_eq!(group_commit.pending_count(), 2);

        group_commit.commit_all();
        assert_eq!(group_commit.pending_count(), 0);
    }

    #[tokio::test]
    async fn test_wal_segment_creation() {
        let temp_dir = TempDir::new().unwrap();
        let wal_dir = temp_dir.path().join("wal");
        std::fs::create_dir_all(&wal_dir).unwrap();

        let segment = WalSegment::create(&wal_dir, 1, 1024 * 1024).unwrap();
        
        assert_eq!(segment.file_id(), 1);
        assert_eq!(segment.offset(), 0);
        assert!(!segment.is_full());
        assert!(segment.path().exists());
    }

    #[tokio::test]
    async fn test_wal_segment_open_existing() {
        let temp_dir = TempDir::new().unwrap();
        let wal_dir = temp_dir.path().join("wal");
        std::fs::create_dir_all(&wal_dir).unwrap();

        // Create a segment
        let mut segment = WalSegment::create(&wal_dir, 1, 1024 * 1024).unwrap();
        let path = segment.path().to_path_buf();

        // Write some data
        let mut io_uring = IoUringContext::new(32, false).unwrap();
        segment.append_to_buffer(vec![1, 2, 3, 4]);
        segment.flush(&mut io_uring).await.unwrap();
        drop(segment);

        // Open the existing segment
        let opened_segment = WalSegment::open(path, 1024 * 1024).unwrap();
        assert_eq!(opened_segment.file_id(), 1);
        assert_eq!(opened_segment.offset(), 4); // Should have the written data
    }

    #[tokio::test]
    async fn test_wal_segment_is_full() {
        let temp_dir = TempDir::new().unwrap();
        let wal_dir = temp_dir.path().join("wal");
        std::fs::create_dir_all(&wal_dir).unwrap();

        let mut segment = WalSegment::create(&wal_dir, 1, 100).unwrap();
        
        assert!(!segment.is_full());

        // Add data to buffer that exceeds max_size
        segment.append_to_buffer(vec![0u8; 101]);
        assert!(segment.is_full());
    }

    #[tokio::test]
    async fn test_wal_with_xxh64_checksum() {
        let temp_dir = TempDir::new().unwrap();
        let config = create_test_config(temp_dir.path().to_path_buf())
            .with_checksum_algorithm(ChecksumAlgorithm::XXH64);
        let io_uring = Arc::new(Mutex::new(IoUringContext::new(32, false).unwrap()));
        let wal_manager = WalManager::new(config, io_uring).await.unwrap();

        // Append entry with XXH64 checksum
        let entry = WalEntry::new_put(b"key1".to_vec(), b"value1".to_vec());
        wal_manager.append(entry).await.unwrap();
        wal_manager.sync().await.unwrap();

        // Recover and verify
        let recovered = wal_manager.recover().await.unwrap();
        assert_eq!(recovered.len(), 1);
        assert_eq!(recovered[0].key, b"key1");
        assert_eq!(recovered[0].value, b"value1");
    }

    #[tokio::test]
    async fn test_wal_large_entries() {
        let temp_dir = TempDir::new().unwrap();
        let wal_manager = create_test_wal_manager(&temp_dir).await;

        // Create large entries (1KB key, 10KB value)
        let large_key = vec![b'k'; 1024];
        let large_value = vec![b'v'; 10240];
        let entry = WalEntry::new_put(large_key.clone(), large_value.clone());

        wal_manager.append(entry).await.unwrap();
        wal_manager.sync().await.unwrap();

        // Recover and verify
        let recovered = wal_manager.recover().await.unwrap();
        assert_eq!(recovered.len(), 1);
        assert_eq!(recovered[0].key, large_key);
        assert_eq!(recovered[0].value, large_value);
    }

    #[tokio::test]
    async fn test_wal_concurrent_appends() {
        let temp_dir = TempDir::new().unwrap();
        let wal_manager = create_test_wal_manager(&temp_dir).await;

        // Append entries sequentially (simulating concurrent behavior)
        // Note: True concurrent testing would require tokio::sync::Mutex instead of std::sync::Mutex
        for i in 0..10 {
            let key = format!("key_{}", i).into_bytes();
            let value = format!("value_{}", i).into_bytes();
            let entry = WalEntry::new_put(key, value);
            wal_manager.append(entry).await.unwrap();
        }

        // Sync and recover
        wal_manager.sync().await.unwrap();
        let recovered = wal_manager.recover().await.unwrap();
        
        // All 10 entries should be recovered
        assert_eq!(recovered.len(), 10);
    }

    #[tokio::test]
    async fn test_wal_recovery_preserves_order() {
        let temp_dir = TempDir::new().unwrap();
        let wal_manager = create_test_wal_manager(&temp_dir).await;

        // Append entries in specific order
        for i in 0..5 {
            let entry = WalEntry::new_put(
                format!("key_{}", i).into_bytes(),
                format!("value_{}", i).into_bytes(),
            );
            wal_manager.append(entry).await.unwrap();
        }
        wal_manager.sync().await.unwrap();

        // Recover and verify order is preserved
        let recovered = wal_manager.recover().await.unwrap();
        assert_eq!(recovered.len(), 5);
        
        for i in 0..5 {
            let expected_key = format!("key_{}", i).into_bytes();
            assert_eq!(recovered[i].key, expected_key);
        }
    }
}
