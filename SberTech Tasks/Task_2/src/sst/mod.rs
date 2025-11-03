use crate::checksum::ChecksumAlgorithm;
use crate::entry::SstEntry;
use crate::error::{Result, StorageError};
use crate::io_uring::IoUringContext;
use std::fs::{File, OpenOptions};
use std::io::{Read, Seek, SeekFrom, Write};
use std::path::PathBuf;
use std::sync::{Arc, RwLock};

mod bloom;
pub use bloom::BloomFilter;

/// SST file header size (64 bytes)
const HEADER_SIZE: usize = 64;
/// Data block size (64KB)
const DATA_BLOCK_SIZE: usize = 64 * 1024;

/// SST file metadata
#[derive(Debug, Clone)]
pub struct SstFile {
    pub id: u64,
    pub path: PathBuf,
    pub min_key: Vec<u8>,
    pub max_key: Vec<u8>,
    pub num_entries: u64,
    pub size: u64,
    pub bloom_filter: BloomFilter,
}

impl SstFile {
    /// Create a new SST file metadata
    pub fn new(
        id: u64,
        path: PathBuf,
        min_key: Vec<u8>,
        max_key: Vec<u8>,
        num_entries: u64,
        size: u64,
        bloom_filter: BloomFilter,
    ) -> Self {
        Self {
            id,
            path,
            min_key,
            max_key,
            num_entries,
            size,
            bloom_filter,
        }
    }

    /// Check if a key might exist in this SST file using bloom filter
    pub fn may_contain(&self, key: &[u8]) -> bool {
        self.bloom_filter.may_contain(key)
    }

    /// Check if a key is within the range of this SST file
    pub fn in_range(&self, key: &[u8]) -> bool {
        key >= self.min_key.as_slice() && key <= self.max_key.as_slice()
    }
}

/// SST file header
#[derive(Debug)]
struct SstHeader {
    magic: u32,           // Magic number for validation
    version: u32,         // File format version
    num_entries: u64,     // Number of entries in the file
    index_offset: u64,    // Offset to index block
    bloom_offset: u64,    // Offset to bloom filter
    min_key_len: u32,     // Length of min key
    max_key_len: u32,     // Length of max key
}

impl SstHeader {
    const MAGIC: u32 = 0x53535446; // "SSTF" in hex

    fn new(num_entries: u64, index_offset: u64, bloom_offset: u64, min_key_len: u32, max_key_len: u32) -> Self {
        Self {
            magic: Self::MAGIC,
            version: 1,
            num_entries,
            index_offset,
            bloom_offset,
            min_key_len,
            max_key_len,
        }
    }

    fn serialize(&self) -> Vec<u8> {
        let mut buf = vec![0u8; HEADER_SIZE];
        let mut offset = 0;

        buf[offset..offset + 4].copy_from_slice(&self.magic.to_le_bytes());
        offset += 4;
        buf[offset..offset + 4].copy_from_slice(&self.version.to_le_bytes());
        offset += 4;
        buf[offset..offset + 8].copy_from_slice(&self.num_entries.to_le_bytes());
        offset += 8;
        buf[offset..offset + 8].copy_from_slice(&self.index_offset.to_le_bytes());
        offset += 8;
        buf[offset..offset + 8].copy_from_slice(&self.bloom_offset.to_le_bytes());
        offset += 8;
        buf[offset..offset + 4].copy_from_slice(&self.min_key_len.to_le_bytes());
        offset += 4;
        buf[offset..offset + 4].copy_from_slice(&self.max_key_len.to_le_bytes());

        buf
    }

    fn deserialize(data: &[u8]) -> Result<Self> {
        if data.len() < HEADER_SIZE {
            return Err(StorageError::SerializationError(
                "Header data too short".to_string(),
            ));
        }

        let mut offset = 0;
        let magic = u32::from_le_bytes([data[offset], data[offset + 1], data[offset + 2], data[offset + 3]]);
        offset += 4;

        if magic != Self::MAGIC {
            return Err(StorageError::SerializationError(format!(
                "Invalid SST magic number: {:#x}",
                magic
            )));
        }

        let version = u32::from_le_bytes([data[offset], data[offset + 1], data[offset + 2], data[offset + 3]]);
        offset += 4;
        let num_entries = u64::from_le_bytes([
            data[offset], data[offset + 1], data[offset + 2], data[offset + 3],
            data[offset + 4], data[offset + 5], data[offset + 6], data[offset + 7],
        ]);
        offset += 8;
        let index_offset = u64::from_le_bytes([
            data[offset], data[offset + 1], data[offset + 2], data[offset + 3],
            data[offset + 4], data[offset + 5], data[offset + 6], data[offset + 7],
        ]);
        offset += 8;
        let bloom_offset = u64::from_le_bytes([
            data[offset], data[offset + 1], data[offset + 2], data[offset + 3],
            data[offset + 4], data[offset + 5], data[offset + 6], data[offset + 7],
        ]);
        offset += 8;
        let min_key_len = u32::from_le_bytes([data[offset], data[offset + 1], data[offset + 2], data[offset + 3]]);
        offset += 4;
        let max_key_len = u32::from_le_bytes([data[offset], data[offset + 1], data[offset + 2], data[offset + 3]]);

        // Validate key lengths (max 64KB per key is reasonable)
        const MAX_KEY_LEN: u32 = 64 * 1024;
        if min_key_len > MAX_KEY_LEN || max_key_len > MAX_KEY_LEN {
            return Err(StorageError::SerializationError(format!(
                "Invalid key lengths in SST header: min={}, max={} (max allowed: {})",
                min_key_len, max_key_len, MAX_KEY_LEN
            )));
        }

        Ok(Self {
            magic,
            version,
            num_entries,
            index_offset,
            bloom_offset,
            min_key_len,
            max_key_len,
        })
    }
}

/// Index entry mapping key range to data block offset
#[derive(Debug, Clone)]
struct IndexEntry {
    first_key: Vec<u8>,
    offset: u64,
    size: u32,
}

impl IndexEntry {
    fn serialize(&self) -> Vec<u8> {
        let key_len = self.first_key.len() as u32;
        let size = 4 + key_len as usize + 8 + 4;
        let mut buf = vec![0u8; size];
        let mut offset = 0;

        buf[offset..offset + 4].copy_from_slice(&key_len.to_le_bytes());
        offset += 4;
        buf[offset..offset + key_len as usize].copy_from_slice(&self.first_key);
        offset += key_len as usize;
        buf[offset..offset + 8].copy_from_slice(&self.offset.to_le_bytes());
        offset += 8;
        buf[offset..offset + 4].copy_from_slice(&self.size.to_le_bytes());

        buf
    }

    fn deserialize(data: &[u8]) -> Result<(Self, usize)> {
        if data.len() < 4 {
            return Err(StorageError::SerializationError(
                "Index entry data too short".to_string(),
            ));
        }

        let mut offset = 0;
        let key_len = u32::from_le_bytes([data[offset], data[offset + 1], data[offset + 2], data[offset + 3]]) as usize;
        offset += 4;

        // Validate key length (max 64KB is reasonable)
        const MAX_KEY_LEN: usize = 64 * 1024;
        if key_len > MAX_KEY_LEN {
            return Err(StorageError::SerializationError(format!(
                "Invalid key length in index entry: {} (max allowed: {})",
                key_len, MAX_KEY_LEN
            )));
        }

        if data.len() < offset + key_len + 8 + 4 {
            return Err(StorageError::SerializationError(
                "Index entry data too short for key".to_string(),
            ));
        }

        let first_key = data[offset..offset + key_len].to_vec();
        offset += key_len;

        let block_offset = u64::from_le_bytes([
            data[offset], data[offset + 1], data[offset + 2], data[offset + 3],
            data[offset + 4], data[offset + 5], data[offset + 6], data[offset + 7],
        ]);
        offset += 8;

        let size = u32::from_le_bytes([data[offset], data[offset + 1], data[offset + 2], data[offset + 3]]);
        offset += 4;

        Ok((
            Self {
                first_key,
                offset: block_offset,
                size,
            },
            offset,
        ))
    }
}

// Helper function to validate and read index data
fn read_index_data(f: &mut File, header: &SstHeader) -> Result<Vec<u8>> {
    // Seek to index offset
    f.seek(SeekFrom::Start(header.index_offset))?;
    
    // Calculate index size: from index_offset to end of file
    let file_size = f.metadata()?.len();
    let index_size = (file_size - header.index_offset) as usize;
    
    // Validate index size (max 10MB is reasonable)
    const MAX_INDEX_SIZE: usize = 10 * 1024 * 1024;
    if index_size > MAX_INDEX_SIZE {
        return Err(StorageError::SerializationError(format!(
            "Invalid index size in SST file: {} (max allowed: {})",
            index_size, MAX_INDEX_SIZE
        )));
    }
    
    let mut index_data = vec![0u8; index_size];
    f.read_exact(&mut index_data)?;
    Ok(index_data)
}

/// SST file manager
/// Uses RwLock for sst_files to allow concurrent reads during compaction
pub struct SstManager {
    data_dir: PathBuf,
    sst_files: Arc<RwLock<Vec<SstFile>>>,
    _io_uring: Arc<RwLock<IoUringContext>>,
    checksum_algo: ChecksumAlgorithm,
    next_id: Arc<RwLock<u64>>,
}

impl SstManager {
    /// Create a new SST manager
    pub fn new(data_dir: PathBuf, io_uring: Arc<RwLock<IoUringContext>>, checksum_algo: ChecksumAlgorithm) -> Self {
        Self {
            data_dir,
            sst_files: Arc::new(RwLock::new(Vec::new())),
            _io_uring: io_uring,
            checksum_algo,
            next_id: Arc::new(RwLock::new(0)),
        }
    }

    /// Write a new SST file from sorted entries
    pub async fn write_sst(&self, entries: Vec<(Vec<u8>, Option<Vec<u8>>)>) -> Result<SstFile> {
        if entries.is_empty() {
            return Err(StorageError::SerializationError(
                "Cannot write empty SST file".to_string(),
            ));
        }

        // Get next file ID
        let file_id = {
            let mut next_id = self.next_id.write().unwrap();
            let id = *next_id;
            *next_id += 1;
            id
        };

        let file_path = self.data_dir.join(format!("{:08}.sst", file_id));

        // Create file
        let mut file = OpenOptions::new()
            .create(true)
            .write(true)
            .truncate(true)
            .open(&file_path)?;

        // Track min/max keys
        let min_key = entries.first().unwrap().0.clone();
        let max_key = entries.last().unwrap().0.clone();

        // Create bloom filter
        let mut bloom_filter = BloomFilter::new(entries.len(), 0.01);
        for (key, _) in &entries {
            bloom_filter.insert(key);
        }

        // Write placeholder header and keys first to reserve space
        let data_start_offset = HEADER_SIZE as u64 + min_key.len() as u64 + max_key.len() as u64;
        
        // Write zeros to reserve space
        let placeholder = vec![0u8; data_start_offset as usize];
        file.write_all(&placeholder)?;
        
        // Now we're at data_start_offset
        assert_eq!(file.seek(SeekFrom::Current(0))?, data_start_offset);

        // Write data blocks and build index
        let mut index_entries = Vec::new();
        let mut current_block = Vec::new();
        let mut current_block_offset = data_start_offset;
        let mut first_key_in_block: Option<Vec<u8>> = None;

        for (key, value) in &entries {
            let entry = SstEntry::new(key.clone(), value.clone());
            let serialized = entry.serialize(self.checksum_algo);

            // Check if adding this entry would exceed block size
            if !current_block.is_empty() && current_block.len() + serialized.len() > DATA_BLOCK_SIZE {
                // Write current block
                let block_size = current_block.len() as u32;
                file.write_all(&current_block)?;

                // Add index entry
                index_entries.push(IndexEntry {
                    first_key: first_key_in_block.take().unwrap(),
                    offset: current_block_offset,
                    size: block_size,
                });

                // Start new block
                current_block_offset += block_size as u64;
                current_block.clear();
            }

            // Track first key in block
            if first_key_in_block.is_none() {
                first_key_in_block = Some(key.clone());
            }

            current_block.extend_from_slice(&serialized);
        }

        // Write final block
        if !current_block.is_empty() {
            let block_size = current_block.len() as u32;
            file.write_all(&current_block)?;

            index_entries.push(IndexEntry {
                first_key: first_key_in_block.unwrap(),
                offset: current_block_offset,
                size: block_size,
            });
        }

        // Write bloom filter
        let bloom_offset = file.seek(SeekFrom::Current(0))?;
        let bloom_data = bloom_filter.serialize();
        file.write_all(&bloom_data)?;

        // Write index block
        let index_offset = file.seek(SeekFrom::Current(0))?;
        for index_entry in &index_entries {
            file.write_all(&index_entry.serialize())?;
        }

        // Write header at the beginning
        file.seek(SeekFrom::Start(0))?;
        let header = SstHeader::new(
            entries.len() as u64,
            index_offset,
            bloom_offset,
            min_key.len() as u32,
            max_key.len() as u32,
        );
        file.write_all(&header.serialize())?;
        
        // Write min/max keys immediately after header
        file.write_all(&min_key)?;
        file.write_all(&max_key)?;

        // Get file size
        let file_size = file.seek(SeekFrom::End(0))?;

        // Sync to disk
        file.sync_all()?;

        let sst_file = SstFile::new(
            file_id,
            file_path,
            min_key,
            max_key,
            entries.len() as u64,
            file_size,
            bloom_filter,
        );

        // Add to tracked files
        self.sst_files.write().unwrap().push(sst_file.clone());

        Ok(sst_file)
    }

    /// Read a value from an SST file
    pub async fn read(&self, file: &SstFile, key: &[u8]) -> Result<Option<Vec<u8>>> {
        // Check bloom filter first
        if !file.may_contain(key) {
            return Ok(None);
        }

        // Check if key is in range
        if !file.in_range(key) {
            return Ok(None);
        }

        // Open file and read header
        let mut f = File::open(&file.path)?;
        let mut header_buf = vec![0u8; HEADER_SIZE];
        f.read_exact(&mut header_buf)?;
        let header = SstHeader::deserialize(&header_buf)?;

        // Read min/max keys
        let mut min_key_buf = vec![0u8; header.min_key_len as usize];
        f.read_exact(&mut min_key_buf)?;
        let mut max_key_buf = vec![0u8; header.max_key_len as usize];
        f.read_exact(&mut max_key_buf)?;

        // Read index block
        let index_data = read_index_data(&mut f, &header)?;

        // Parse index entries
        let mut index_entries = Vec::new();
        let mut offset = 0;
        while offset < index_data.len() {
            let (entry, bytes_read) = IndexEntry::deserialize(&index_data[offset..])?;
            index_entries.push(entry);
            offset += bytes_read;
        }

        // Find the data block that might contain the key
        let mut target_block: Option<&IndexEntry> = None;
        for entry in &index_entries {
            if key >= entry.first_key.as_slice() {
                target_block = Some(entry);
            } else {
                break;
            }
        }

        if target_block.is_none() {
            return Ok(None);
        }

        let block = target_block.unwrap();

        // Validate block size (max 4MB per block is reasonable)
        const MAX_BLOCK_SIZE: u32 = 4 * 1024 * 1024;
        if block.size > MAX_BLOCK_SIZE {
            return Err(StorageError::SerializationError(format!(
                "Invalid block size in SST file: {} (max allowed: {})",
                block.size, MAX_BLOCK_SIZE
            )));
        }

        // Read the data block
        f.seek(SeekFrom::Start(block.offset))?;
        let mut block_data = vec![0u8; block.size as usize];
        f.read_exact(&mut block_data)?;

        // Parse entries in the block
        let mut offset = 0;
        while offset < block_data.len() {
            if offset + 12 > block_data.len() {
                break;
            }

            match SstEntry::deserialize(&block_data[offset..], self.checksum_algo) {
                Ok(entry) => {
                    let entry_size = entry.serialized_size();

                    if entry.key == key {
                        return Ok(entry.value);
                    }

                    offset += entry_size;
                }
                Err(_) => {
                    // Deserialization failed, likely reached end of valid data
                    break;
                }
            }
        }

        Ok(None)
    }

    /// Scan a range of keys from an SST file
    pub async fn scan(&self, file: &SstFile, start: &[u8], end: &[u8]) -> Result<Vec<(Vec<u8>, Vec<u8>)>> {
        let mut results = Vec::new();

        // Open file and read header
        let mut f = File::open(&file.path)?;
        let mut header_buf = vec![0u8; HEADER_SIZE];
        f.read_exact(&mut header_buf)?;
        let header = SstHeader::deserialize(&header_buf)?;

        // Read min/max keys
        let mut min_key_buf = vec![0u8; header.min_key_len as usize];
        f.read_exact(&mut min_key_buf)?;
        let mut max_key_buf = vec![0u8; header.max_key_len as usize];
        f.read_exact(&mut max_key_buf)?;

        // Read index block
        let index_data = read_index_data(&mut f, &header)?;

        // Parse index entries
        let mut index_entries = Vec::new();
        let mut offset = 0;
        while offset < index_data.len() {
            let (entry, bytes_read) = IndexEntry::deserialize(&index_data[offset..])?;
            index_entries.push(entry);
            offset += bytes_read;
        }

        // Find relevant data blocks
        for block in &index_entries {
            // Skip blocks that are entirely before the start key
            if block.first_key.as_slice() < start {
                // Check if this block might contain keys in range
                // We need to read it to be sure
            }

            // Validate block size (max 4MB per block is reasonable)
            const MAX_BLOCK_SIZE: u32 = 4 * 1024 * 1024;
            if block.size > MAX_BLOCK_SIZE {
                return Err(StorageError::SerializationError(format!(
                    "Invalid block size in SST file: {} (max allowed: {})",
                    block.size, MAX_BLOCK_SIZE
                )));
            }
            
            // Read the data block
            f.seek(SeekFrom::Start(block.offset))?;
            let mut block_data = vec![0u8; block.size as usize];
            f.read_exact(&mut block_data)?;

            // Parse entries in the block
            let mut offset = 0;
            while offset < block_data.len() {
                if offset + 12 > block_data.len() {
                    break;
                }

                let entry = SstEntry::deserialize(&block_data[offset..], self.checksum_algo)?;
                let entry_size = entry.serialized_size();

                // Check if entry is in range
                let key_in_range = entry.key.as_slice() >= start && entry.key.as_slice() <= end;
                let key_past_end = entry.key.as_slice() > end;

                if key_in_range {
                    if let Some(value) = entry.value {
                        results.push((entry.key, value));
                    }
                } else if key_past_end {
                    return Ok(results);
                }

                offset += entry_size;
            }
        }

        Ok(results)
    }

    /// Get all SST files that overlap with the given key range
    pub fn get_overlapping_files(&self, start: &[u8], end: &[u8]) -> Vec<SstFile> {
        let files = self.sst_files.read().unwrap();
        files
            .iter()
            .filter(|f| {
                // Check if ranges overlap
                !(f.max_key.as_slice() < start || f.min_key.as_slice() > end)
            })
            .cloned()
            .collect()
    }

    /// Add an SST file to the manager
    pub fn add_file(&self, file: SstFile) {
        let mut files = self.sst_files.write().unwrap();
        files.push(file);
    }

    /// Remove an SST file from the manager
    pub fn remove_file(&self, file_id: u64) -> Result<()> {
        let mut files = self.sst_files.write().unwrap();
        files.retain(|f| f.id != file_id);
        Ok(())
    }

    /// Get all SST files
    pub fn get_all_files(&self) -> Vec<SstFile> {
        self.sst_files.read().unwrap().clone()
    }

    /// Load existing SST files from disk
    pub fn load_existing_files(&self) -> Result<()> {
        let mut files = Vec::new();
        let mut max_id = 0u64;

        for entry in std::fs::read_dir(&self.data_dir)? {
            let entry = entry?;
            let path = entry.path();

            if path.extension().and_then(|s| s.to_str()) == Some("sst") {
                // Parse file ID from filename
                if let Some(file_stem) = path.file_stem().and_then(|s| s.to_str()) {
                    if let Ok(file_id) = file_stem.parse::<u64>() {
                        max_id = max_id.max(file_id);

                        // Read file metadata
                        let mut f = File::open(&path)?;
                        let mut header_buf = vec![0u8; HEADER_SIZE];
                        f.read_exact(&mut header_buf)?;
                        let header = SstHeader::deserialize(&header_buf)?;

                        // Read min/max keys
                        let mut min_key = vec![0u8; header.min_key_len as usize];
                        f.read_exact(&mut min_key)?;
                        let mut max_key = vec![0u8; header.max_key_len as usize];
                        f.read_exact(&mut max_key)?;

                        // Read bloom filter (comes before index)
                        f.seek(SeekFrom::Start(header.bloom_offset))?;
                        let bloom_size = (header.index_offset - header.bloom_offset) as usize;
                        let mut bloom_data = vec![0u8; bloom_size];
                        f.read_exact(&mut bloom_data)?;
                        let bloom_filter = BloomFilter::deserialize(&bloom_data)?;

                        let file_size = f.metadata()?.len();

                        let sst_file = SstFile::new(
                            file_id,
                            path,
                            min_key,
                            max_key,
                            header.num_entries,
                            file_size,
                            bloom_filter,
                        );

                        files.push(sst_file);
                    }
                }
            }
        }

        // Update next ID
        *self.next_id.write().unwrap() = max_id + 1;

        // Update file list
        *self.sst_files.write().unwrap() = files;

        Ok(())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    fn create_test_manager() -> (SstManager, TempDir) {
        let temp_dir = TempDir::new().unwrap();
        let io_uring = Arc::new(RwLock::new(IoUringContext::new(32, false).unwrap()));
        let manager = SstManager::new(
            temp_dir.path().to_path_buf(),
            io_uring,
            ChecksumAlgorithm::CRC32,
        );
        (manager, temp_dir)
    }

    #[tokio::test]
    async fn test_write_and_read_sst() {
        let (manager, _temp_dir) = create_test_manager();

        let entries = vec![
            (b"key1".to_vec(), Some(b"value1".to_vec())),
            (b"key2".to_vec(), Some(b"value2".to_vec())),
            (b"key3".to_vec(), Some(b"value3".to_vec())),
        ];

        let sst_file = manager.write_sst(entries).await.unwrap();

        assert_eq!(sst_file.min_key, b"key1");
        assert_eq!(sst_file.max_key, b"key3");
        assert_eq!(sst_file.num_entries, 3);

        let value = manager.read(&sst_file, b"key2").await.unwrap();
        assert_eq!(value, Some(b"value2".to_vec()));

        let value = manager.read(&sst_file, b"key4").await.unwrap();
        assert_eq!(value, None);
    }

    #[tokio::test]
    async fn test_write_and_read_sst_large_values() {
        let (manager, _temp_dir) = create_test_manager();

        // Test with larger keys and values similar to memtable_flush test
        let mut entries = Vec::new();
        for i in 0..10 {
            let key = format!("key_{:04}", i).into_bytes();
            let value = vec![b'v'; 1000]; // 1KB value
            entries.push((key, Some(value)));
        }

        let sst_file = manager.write_sst(entries).await.unwrap();

        // Try to read the first key
        let test_key = b"key_0000";
        let value = manager.read(&sst_file, test_key).await.unwrap();
        assert!(value.is_some(), "Should find key_0000");
        assert_eq!(value.unwrap().len(), 1000);

        // Try to read a middle key
        let test_key = b"key_0005";
        let value = manager.read(&sst_file, test_key).await.unwrap();
        assert!(value.is_some(), "Should find key_0005");
        assert_eq!(value.unwrap().len(), 1000);
    }

    #[tokio::test]
    async fn test_sst_scan() {
        let (manager, _temp_dir) = create_test_manager();

        let entries = vec![
            (b"key1".to_vec(), Some(b"value1".to_vec())),
            (b"key2".to_vec(), Some(b"value2".to_vec())),
            (b"key3".to_vec(), Some(b"value3".to_vec())),
            (b"key4".to_vec(), Some(b"value4".to_vec())),
        ];

        let sst_file = manager.write_sst(entries).await.unwrap();

        let results = manager.scan(&sst_file, b"key2", b"key3").await.unwrap();
        assert_eq!(results.len(), 2);
        assert_eq!(results[0].0, b"key2");
        assert_eq!(results[1].0, b"key3");
    }

    #[tokio::test]
    async fn test_sst_tombstone() {
        let (manager, _temp_dir) = create_test_manager();

        let entries = vec![
            (b"key1".to_vec(), Some(b"value1".to_vec())),
            (b"key2".to_vec(), None), // Tombstone
            (b"key3".to_vec(), Some(b"value3".to_vec())),
        ];

        let sst_file = manager.write_sst(entries).await.unwrap();

        let value = manager.read(&sst_file, b"key2").await.unwrap();
        assert_eq!(value, None);
    }

    #[tokio::test]
    async fn test_get_overlapping_files() {
        let (manager, _temp_dir) = create_test_manager();

        let entries1 = vec![
            (b"a".to_vec(), Some(b"value1".to_vec())),
            (b"b".to_vec(), Some(b"value2".to_vec())),
        ];
        let _sst1 = manager.write_sst(entries1).await.unwrap();

        let entries2 = vec![
            (b"c".to_vec(), Some(b"value3".to_vec())),
            (b"d".to_vec(), Some(b"value4".to_vec())),
        ];
        let _sst2 = manager.write_sst(entries2).await.unwrap();

        let overlapping = manager.get_overlapping_files(b"b", b"c");
        assert_eq!(overlapping.len(), 2);
    }

    #[tokio::test]
    async fn test_bloom_filter_effectiveness() {
        let (manager, _temp_dir) = create_test_manager();

        let entries = vec![
            (b"key1".to_vec(), Some(b"value1".to_vec())),
            (b"key2".to_vec(), Some(b"value2".to_vec())),
            (b"key3".to_vec(), Some(b"value3".to_vec())),
        ];

        let sst_file = manager.write_sst(entries).await.unwrap();

        // Keys that exist should pass bloom filter
        assert!(sst_file.may_contain(b"key1"));
        assert!(sst_file.may_contain(b"key2"));
        assert!(sst_file.may_contain(b"key3"));

        // Non-existent key might pass (false positive) but likely won't
        // We can't assert false here due to false positive nature
    }

    #[tokio::test]
    async fn test_checksum_verification() {
        use std::io::{Seek, SeekFrom, Write};
        use std::fs::File;
        
        let (manager, _temp_dir) = create_test_manager();

        let entries = vec![
            (b"key1".to_vec(), Some(b"value1".to_vec())),
            (b"key2".to_vec(), Some(b"value2".to_vec())),
            (b"key3".to_vec(), Some(b"value3".to_vec())),
        ];

        let sst_file = manager.write_sst(entries).await.unwrap();

        // Verify we can read the data correctly first
        let value = manager.read(&sst_file, b"key2").await.unwrap();
        assert_eq!(value, Some(b"value2".to_vec()));

        // Get the file size to ensure we corrupt within bounds
        let file_size = std::fs::metadata(&sst_file.path).unwrap().len();
        
        // Corrupt a byte somewhere in the middle of the file (likely in data section)
        // This should cause checksum verification to fail
        {
            let mut file = File::options()
                .write(true)
                .open(&sst_file.path)
                .unwrap();
            
            // Corrupt a byte at position 200 (well past the header which is 64 bytes + min/max keys)
            let corrupt_pos = 200.min(file_size - 1);
            file.seek(SeekFrom::Start(corrupt_pos)).unwrap();
            file.write_all(&[0xFF]).unwrap();
            file.sync_all().unwrap();
        }

        // Reading should now fail due to checksum mismatch
        // Try reading all keys to see if any fail
        let result1 = manager.read(&sst_file, b"key1").await;
        let result2 = manager.read(&sst_file, b"key2").await;
        let result3 = manager.read(&sst_file, b"key3").await;
        
        // At least one should fail due to corruption
        assert!(
            result1.is_err() || result2.is_err() || result3.is_err(),
            "Expected at least one read to fail due to checksum mismatch"
        );
    }
}
