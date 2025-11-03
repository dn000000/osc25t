use crate::config::CompactionStrategy;
use crate::error::Result;
use crate::sst::{SstFile, SstManager};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tokio::task::JoinHandle;

/// Background compactor for SST files
pub struct Compactor {
    sst_manager: Arc<SstManager>,
    strategy: CompactionStrategy,
    running: Arc<AtomicBool>,
    handle: Option<JoinHandle<()>>,
}

impl Compactor {
    /// Create a new compactor with the given strategy
    pub fn new(sst_manager: Arc<SstManager>, strategy: CompactionStrategy) -> Self {
        Self {
            sst_manager,
            strategy,
            running: Arc::new(AtomicBool::new(false)),
            handle: None,
        }
    }

    /// Start the background compaction thread
    pub fn start(&mut self) {
        if self.running.load(Ordering::SeqCst) {
            return; // Already running
        }

        self.running.store(true, Ordering::SeqCst);
        
        let sst_manager = self.sst_manager.clone();
        let strategy = self.strategy.clone();
        let running = self.running.clone();

        let handle = tokio::spawn(async move {
            Self::compact_loop(sst_manager, strategy, running).await;
        });

        self.handle = Some(handle);
    }

    /// Stop the background compaction thread
    pub fn stop(&mut self) {
        self.running.store(false, Ordering::SeqCst);
        
        if let Some(handle) = self.handle.take() {
            handle.abort();
        }
    }

    /// Main compaction loop that runs in the background
    async fn compact_loop(
        sst_manager: Arc<SstManager>,
        strategy: CompactionStrategy,
        running: Arc<AtomicBool>,
    ) {
        while running.load(Ordering::SeqCst) {
            // Check for compaction work
            let files_to_compact = Self::select_files_for_compaction_impl(&sst_manager, &strategy);
            
            if !files_to_compact.is_empty() {
                // Perform compaction
                match Self::merge_sst_files_impl(&sst_manager, files_to_compact).await {
                    Ok(new_file) => {
                        // Compaction successful
                        tracing::info!("Compaction completed, created SST file {}", new_file.id);
                    }
                    Err(e) => {
                        tracing::error!("Compaction failed: {:?}", e);
                    }
                }
            }

            // Sleep before next check (10 seconds)
            tokio::time::sleep(tokio::time::Duration::from_secs(10)).await;
        }
    }

    /// Select files for compaction based on strategy
    fn select_files_for_compaction_impl(
        sst_manager: &Arc<SstManager>,
        strategy: &CompactionStrategy,
    ) -> Vec<SstFile> {
        let all_files = sst_manager.get_all_files();
        
        if all_files.is_empty() {
            return Vec::new();
        }

        match strategy {
            CompactionStrategy::SizeTiered { size_ratio, min_threshold } => {
                Self::select_size_tiered(&all_files, *size_ratio, *min_threshold)
            }
            CompactionStrategy::Leveled { .. } => {
                // Leveled compaction not implemented yet, return empty
                Vec::new()
            }
        }
    }

    /// Select files for size-tiered compaction
    /// Groups files by similar size and selects a group when threshold is reached
    fn select_size_tiered(
        files: &[SstFile],
        size_ratio: f64,
        min_threshold: usize,
    ) -> Vec<SstFile> {
        if files.len() < min_threshold {
            return Vec::new();
        }

        // Sort files by size
        let mut sorted_files = files.to_vec();
        sorted_files.sort_by_key(|f| f.size);

        // Group files by similar size
        let mut groups: Vec<Vec<SstFile>> = Vec::new();
        let mut current_group = vec![sorted_files[0].clone()];
        let mut current_size = sorted_files[0].size;

        for file in sorted_files.iter().skip(1) {
            let ratio = file.size as f64 / current_size as f64;
            
            // If file size is within ratio, add to current group
            if ratio <= size_ratio {
                current_group.push(file.clone());
            } else {
                // Start new group
                if current_group.len() >= min_threshold {
                    groups.push(current_group);
                }
                current_group = vec![file.clone()];
                current_size = file.size;
            }
        }

        // Add last group if it meets threshold
        if current_group.len() >= min_threshold {
            groups.push(current_group);
        }

        // Return the first group that meets the threshold
        if let Some(group) = groups.first() {
            group.clone()
        } else {
            Vec::new()
        }
    }

    /// Merge SST files into a single new SST file
    /// Performs multi-way merge, removes tombstones, and keeps only latest version of each key
    /// 
    /// Non-blocking design:
    /// - Works on copies of SST file metadata (files parameter)
    /// - Reads from physical files without holding locks
    /// - Atomically updates SST file list via add_file/remove_file
    /// - SstManager uses RwLock allowing concurrent reads during compaction
    async fn merge_sst_files_impl(
        sst_manager: &Arc<SstManager>,
        files: Vec<SstFile>,
    ) -> Result<SstFile> {
        use std::collections::BTreeMap;

        if files.is_empty() {
            return Err(crate::error::StorageError::SerializationError(
                "Cannot merge empty file list".to_string(),
            ));
        }

        // Track file IDs to delete after successful merge
        let file_ids_to_delete: Vec<u64> = files.iter().map(|f| f.id).collect();

        // Read all entries from all files and merge them
        // Use BTreeMap to maintain sorted order and handle duplicates
        let mut merged_entries: BTreeMap<Vec<u8>, (Option<Vec<u8>>, u64)> = BTreeMap::new();

        for (file_idx, sst_file) in files.iter().enumerate() {
            // Read all entries from this SST file
            let entries = Self::read_all_entries_from_sst(sst_file)?;
            
            // Add entries to merged map
            // Use file index as a simple "timestamp" - later files override earlier ones
            for (key, value) in entries {
                merged_entries
                    .entry(key)
                    .and_modify(|(v, idx)| {
                        // Keep entry from later file (higher index)
                        if file_idx as u64 > *idx {
                            *v = value.clone();
                            *idx = file_idx as u64;
                        }
                    })
                    .or_insert((value, file_idx as u64));
            }
        }

        // Filter out tombstones and convert to format expected by write_sst
        let final_entries: Vec<(Vec<u8>, Option<Vec<u8>>)> = merged_entries
            .into_iter()
            .filter_map(|(key, (value, _))| {
                // Remove tombstones during compaction
                if value.is_none() {
                    None
                } else {
                    Some((key, value))
                }
            })
            .collect();

        // If no entries remain after filtering tombstones, we still need to handle this
        if final_entries.is_empty() {
            // Delete old files and return early
            for file_id in file_ids_to_delete {
                sst_manager.remove_file(file_id)?;
                // Also delete the physical file
                if let Some(file) = files.iter().find(|f| f.id == file_id) {
                    let _ = std::fs::remove_file(&file.path);
                }
            }
            return Err(crate::error::StorageError::SerializationError(
                "No entries remaining after compaction".to_string(),
            ));
        }

        // Write new merged SST file
        let new_file = sst_manager.write_sst(final_entries).await?;

        // Delete old SST files
        for file_id in file_ids_to_delete {
            sst_manager.remove_file(file_id)?;
            // Also delete the physical file
            if let Some(file) = files.iter().find(|f| f.id == file_id) {
                let _ = std::fs::remove_file(&file.path);
            }
        }

        Ok(new_file)
    }

    /// Read all entries from an SST file
    fn read_all_entries_from_sst(sst_file: &SstFile) -> Result<Vec<(Vec<u8>, Option<Vec<u8>>)>> {
        use std::fs::File;
        use std::io::Read;
        use crate::entry::SstEntry;
        use crate::checksum::ChecksumAlgorithm;

        const HEADER_SIZE: usize = 64;

        let mut file = File::open(&sst_file.path)?;
        let mut entries = Vec::new();

        // Read header
        let mut header_buf = vec![0u8; HEADER_SIZE];
        file.read_exact(&mut header_buf)?;

        // Parse header to get bloom and index offsets
        let mut offset = 8; // Skip magic (4) and version (4)
        let num_entries = u64::from_le_bytes([
            header_buf[offset], header_buf[offset + 1], header_buf[offset + 2], header_buf[offset + 3],
            header_buf[offset + 4], header_buf[offset + 5], header_buf[offset + 6], header_buf[offset + 7],
        ]);
        offset += 8; // now at 16
        let _index_offset = u64::from_le_bytes([
            header_buf[offset], header_buf[offset + 1], header_buf[offset + 2], header_buf[offset + 3],
            header_buf[offset + 4], header_buf[offset + 5], header_buf[offset + 6], header_buf[offset + 7],
        ]);
        offset += 8; // now at 24
        let bloom_offset = u64::from_le_bytes([
            header_buf[offset], header_buf[offset + 1], header_buf[offset + 2], header_buf[offset + 3],
            header_buf[offset + 4], header_buf[offset + 5], header_buf[offset + 6], header_buf[offset + 7],
        ]);
        offset += 8; // now at 32

        // Read min/max keys lengths
        let min_key_len = u32::from_le_bytes([
            header_buf[offset], header_buf[offset + 1], header_buf[offset + 2], header_buf[offset + 3],
        ]) as usize;
        offset += 4;
        let max_key_len = u32::from_le_bytes([
            header_buf[offset], header_buf[offset + 1], header_buf[offset + 2], header_buf[offset + 3],
        ]) as usize;

        // Read min/max keys
        let mut min_key_buf = vec![0u8; min_key_len];
        file.read_exact(&mut min_key_buf)?;
        let mut max_key_buf = vec![0u8; max_key_len];
        file.read_exact(&mut max_key_buf)?;

        // Now we're at the start of data section
        // Data section goes from here to bloom_offset
        let data_start = HEADER_SIZE as u64 + min_key_len as u64 + max_key_len as u64;
        let file_size = file.metadata()?.len();
        
        // Validate that bloom_offset is after data start and within file
        if bloom_offset <= data_start {
            return Err(crate::error::StorageError::SerializationError(
                format!("Invalid SST file structure: bloom_offset ({}) is before or at data start ({})", 
                    bloom_offset, data_start)
            ));
        }
        
        if bloom_offset > file_size {
            return Err(crate::error::StorageError::SerializationError(
                format!("Invalid SST file structure: bloom_offset ({}) is beyond file size ({})", 
                    bloom_offset, file_size)
            ));
        }
        
        let data_size = (bloom_offset - data_start) as usize;
        
        // Validate data size is reasonable
        if data_size == 0 {
            return Ok(Vec::new());
        }
        
        let mut data_buf = vec![0u8; data_size];
        file.read_exact(&mut data_buf)?;

        // Parse entries from data blocks
        let mut data_offset = 0;
        while data_offset < data_buf.len() && entries.len() < num_entries as usize {
            if data_offset + 12 > data_buf.len() {
                break;
            }

            match SstEntry::deserialize(&data_buf[data_offset..], ChecksumAlgorithm::CRC32) {
                Ok(entry) => {
                    let entry_size = entry.serialized_size();
                    entries.push((entry.key, entry.value));
                    data_offset += entry_size;
                }
                Err(_) => {
                    // If we can't deserialize, we've likely reached the end of valid data
                    break;
                }
            }
        }

        Ok(entries)
    }
}

impl Drop for Compactor {
    fn drop(&mut self) {
        self.stop();
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::checksum::ChecksumAlgorithm;
    use crate::config::CompactionStrategy;
    use crate::io_uring::IoUringContext;
    use std::sync::RwLock;
    use tempfile::TempDir;

    fn create_test_sst_manager() -> (Arc<SstManager>, TempDir) {
        let temp_dir = TempDir::new().unwrap();
        let io_uring = Arc::new(RwLock::new(IoUringContext::new(32, false).unwrap()));
        let manager = Arc::new(SstManager::new(
            temp_dir.path().to_path_buf(),
            io_uring,
            ChecksumAlgorithm::CRC32,
        ));
        (manager, temp_dir)
    }

    #[tokio::test]
    async fn test_file_selection_size_tiered() {
        let (sst_manager, _temp_dir) = create_test_sst_manager();

        // Create SST files with similar sizes
        let entries1 = vec![
            (b"key1".to_vec(), Some(b"value1".to_vec())),
            (b"key2".to_vec(), Some(b"value2".to_vec())),
        ];
        sst_manager.write_sst(entries1).await.unwrap();

        let entries2 = vec![
            (b"key3".to_vec(), Some(b"value3".to_vec())),
            (b"key4".to_vec(), Some(b"value4".to_vec())),
        ];
        sst_manager.write_sst(entries2).await.unwrap();

        let entries3 = vec![
            (b"key5".to_vec(), Some(b"value5".to_vec())),
            (b"key6".to_vec(), Some(b"value6".to_vec())),
        ];
        sst_manager.write_sst(entries3).await.unwrap();

        let entries4 = vec![
            (b"key7".to_vec(), Some(b"value7".to_vec())),
            (b"key8".to_vec(), Some(b"value8".to_vec())),
        ];
        sst_manager.write_sst(entries4).await.unwrap();

        // Test file selection with size-tiered strategy
        let _strategy = CompactionStrategy::SizeTiered {
            size_ratio: 2.0,
            min_threshold: 4,
        };

        let files = sst_manager.get_all_files();
        let selected = Compactor::select_size_tiered(&files, 2.0, 4);

        // Should select files since we have 4 files of similar size
        assert_eq!(selected.len(), 4);
    }

    #[tokio::test]
    async fn test_file_selection_below_threshold() {
        let (sst_manager, _temp_dir) = create_test_sst_manager();

        // Create only 2 SST files
        let entries1 = vec![
            (b"key1".to_vec(), Some(b"value1".to_vec())),
        ];
        sst_manager.write_sst(entries1).await.unwrap();

        let entries2 = vec![
            (b"key2".to_vec(), Some(b"value2".to_vec())),
        ];
        sst_manager.write_sst(entries2).await.unwrap();

        let _strategy = CompactionStrategy::SizeTiered {
            size_ratio: 2.0,
            min_threshold: 4,
        };

        let files = sst_manager.get_all_files();
        let selected = Compactor::select_size_tiered(&files, 2.0, 4);

        // Should not select files since we're below threshold
        assert_eq!(selected.len(), 0);
    }

    #[tokio::test]
    async fn test_merge_with_tombstone_removal() {
        let (sst_manager, _temp_dir) = create_test_sst_manager();

        // Create first SST with regular entries
        let entries1 = vec![
            (b"key1".to_vec(), Some(b"value1".to_vec())),
            (b"key2".to_vec(), Some(b"value2".to_vec())),
            (b"key3".to_vec(), Some(b"value3".to_vec())),
        ];
        let sst1 = sst_manager.write_sst(entries1).await.unwrap();

        // Create second SST with tombstone for key2
        let entries2 = vec![
            (b"key2".to_vec(), None), // Tombstone
            (b"key4".to_vec(), Some(b"value4".to_vec())),
        ];
        let sst2 = sst_manager.write_sst(entries2).await.unwrap();

        // Merge the files
        let files_to_merge = vec![sst1, sst2];
        let merged = Compactor::merge_sst_files_impl(&sst_manager, files_to_merge)
            .await
            .unwrap();

        // Verify merged file doesn't contain key2 (tombstone removed)
        let value = sst_manager.read(&merged, b"key2").await.unwrap();
        assert_eq!(value, None);

        // Verify other keys are present
        let value1 = sst_manager.read(&merged, b"key1").await.unwrap();
        assert_eq!(value1, Some(b"value1".to_vec()));

        let value3 = sst_manager.read(&merged, b"key3").await.unwrap();
        assert_eq!(value3, Some(b"value3".to_vec()));

        let value4 = sst_manager.read(&merged, b"key4").await.unwrap();
        assert_eq!(value4, Some(b"value4".to_vec()));
    }

    #[tokio::test]
    async fn test_merge_keeps_latest_version() {
        let (sst_manager, _temp_dir) = create_test_sst_manager();

        // Create first SST with original value
        let entries1 = vec![
            (b"key1".to_vec(), Some(b"value1_old".to_vec())),
            (b"key2".to_vec(), Some(b"value2".to_vec())),
        ];
        let sst1 = sst_manager.write_sst(entries1).await.unwrap();

        // Create second SST with updated value for key1
        let entries2 = vec![
            (b"key1".to_vec(), Some(b"value1_new".to_vec())),
            (b"key3".to_vec(), Some(b"value3".to_vec())),
        ];
        let sst2 = sst_manager.write_sst(entries2).await.unwrap();

        // Merge the files
        let files_to_merge = vec![sst1, sst2];
        let merged = Compactor::merge_sst_files_impl(&sst_manager, files_to_merge)
            .await
            .unwrap();

        // Verify merged file has the latest version of key1
        let value = sst_manager.read(&merged, b"key1").await.unwrap();
        assert_eq!(value, Some(b"value1_new".to_vec()));
    }

    #[tokio::test]
    async fn test_concurrent_operations_during_compaction() {
        let (sst_manager, _temp_dir) = create_test_sst_manager();

        // Create multiple SST files
        for i in 0..4 {
            let entries = vec![
                (format!("key{}", i * 2).into_bytes(), Some(format!("value{}", i * 2).into_bytes())),
                (format!("key{}", i * 2 + 1).into_bytes(), Some(format!("value{}", i * 2 + 1).into_bytes())),
            ];
            sst_manager.write_sst(entries).await.unwrap();
        }

        // Start compaction in background
        let sst_manager_clone = sst_manager.clone();
        let compaction_handle = tokio::spawn(async move {
            let files = sst_manager_clone.get_all_files();
            if files.len() >= 4 {
                let files_to_compact = files[0..4].to_vec();
                Compactor::merge_sst_files_impl(&sst_manager_clone, files_to_compact)
                    .await
                    .ok();
            }
        });

        // Perform concurrent reads
        let read_handle = tokio::spawn(async move {
            for _i in 0..8 {
                let _ = sst_manager.get_all_files();
                tokio::time::sleep(tokio::time::Duration::from_millis(10)).await;
            }
        });

        // Wait for both to complete
        let _ = tokio::join!(compaction_handle, read_handle);
    }
}
