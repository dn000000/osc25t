use crate::checksum::ChecksumAlgorithm;
use crate::error::{Result, StorageError};
use std::time::{SystemTime, UNIX_EPOCH};

/// Page size for alignment (4KB)
pub const PAGE_SIZE: usize = 4096;

/// Operation type for WAL entries
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum OpType {
    Put = 1,
    Delete = 2,
}

impl OpType {
    /// Convert from u8 to OpType
    pub fn from_u8(value: u8) -> Result<Self> {
        match value {
            1 => Ok(OpType::Put),
            2 => Ok(OpType::Delete),
            _ => Err(StorageError::SerializationError(
                format!("Invalid OpType: {}", value)
            )),
        }
    }
}

/// Write-Ahead Log entry
#[derive(Debug, Clone)]
pub struct WalEntry {
    pub checksum: u32,
    pub timestamp: u64,
    pub sequence: u64,
    pub key: Vec<u8>,
    pub value: Vec<u8>,
    pub op_type: OpType,
}

impl WalEntry {
    /// Create a new WAL entry for a PUT operation
    pub fn new_put(key: Vec<u8>, value: Vec<u8>) -> Self {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_micros() as u64;
        
        Self {
            checksum: 0, // Will be computed during serialization
            timestamp,
            sequence: 0, // Will be set later
            key,
            value,
            op_type: OpType::Put,
        }
    }
    
    /// Create a new WAL entry for a DELETE operation
    pub fn new_delete(key: Vec<u8>) -> Self {
        let timestamp = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_micros() as u64;
        
        Self {
            checksum: 0, // Will be computed during serialization
            timestamp,
            sequence: 0, // Will be set later
            key,
            value: Vec::new(),
            op_type: OpType::Delete,
        }
    }
    
    /// Set the sequence number
    pub fn with_sequence(mut self, sequence: u64) -> Self {
        self.sequence = sequence;
        self
    }
    
    /// Serialize the WAL entry to bytes with 4KB alignment
    /// Format: [CRC32: 4B][Timestamp: 8B][Sequence: 8B][KeyLen: 4B][ValueLen: 4B][OpType: 1B][Padding: 3B][Key][Value][Padding to 4KB]
    pub fn serialize(&self, checksum_algo: ChecksumAlgorithm) -> Vec<u8> {
        let key_len = self.key.len() as u32;
        let value_len = self.value.len() as u32;
        
        // Calculate the size without padding
        let header_size = 4 + 8 + 8 + 4 + 4 + 1 + 3; // checksum + timestamp + sequence + key_len + value_len + op_type + padding
        let data_size = header_size + key_len as usize + value_len as usize;
        
        // Calculate aligned size (round up to next PAGE_SIZE boundary)
        let aligned_size = ((data_size + PAGE_SIZE - 1) / PAGE_SIZE) * PAGE_SIZE;
        
        // Create buffer with aligned size
        let mut buffer = vec![0u8; aligned_size];
        let mut offset = 0;
        
        // Reserve space for checksum (will be filled later)
        offset += 4;
        
        // Write timestamp
        buffer[offset..offset + 8].copy_from_slice(&self.timestamp.to_le_bytes());
        offset += 8;
        
        // Write sequence
        buffer[offset..offset + 8].copy_from_slice(&self.sequence.to_le_bytes());
        offset += 8;
        
        // Write key length
        buffer[offset..offset + 4].copy_from_slice(&key_len.to_le_bytes());
        offset += 4;
        
        // Write value length
        buffer[offset..offset + 4].copy_from_slice(&value_len.to_le_bytes());
        offset += 4;
        
        // Write op type
        buffer[offset] = self.op_type as u8;
        offset += 1;
        
        // Padding (3 bytes)
        offset += 3;
        
        // Write key
        buffer[offset..offset + key_len as usize].copy_from_slice(&self.key);
        offset += key_len as usize;
        
        // Write value
        buffer[offset..offset + value_len as usize].copy_from_slice(&self.value);
        offset += value_len as usize;
        
        // Compute checksum over actual data only (not padding)
        let checksum = checksum_algo.compute(&buffer[4..offset]);
        
        // Write checksum at the beginning
        buffer[0..4].copy_from_slice(&checksum.to_le_bytes());
        
        buffer
    }
    
    /// Deserialize a WAL entry from bytes
    pub fn deserialize(data: &[u8], checksum_algo: ChecksumAlgorithm) -> Result<Self> {
        if data.len() < 32 {
            return Err(StorageError::SerializationError(
                "Data too short for WAL entry".to_string()
            ));
        }
        
        let mut offset = 0;
        
        // Read checksum
        let checksum = u32::from_le_bytes([data[0], data[1], data[2], data[3]]);
        offset += 4;
        
        // Read timestamp
        let timestamp = u64::from_le_bytes([
            data[offset], data[offset + 1], data[offset + 2], data[offset + 3],
            data[offset + 4], data[offset + 5], data[offset + 6], data[offset + 7],
        ]);
        offset += 8;
        
        // Read sequence
        let sequence = u64::from_le_bytes([
            data[offset], data[offset + 1], data[offset + 2], data[offset + 3],
            data[offset + 4], data[offset + 5], data[offset + 6], data[offset + 7],
        ]);
        offset += 8;
        
        // Read key length
        let key_len = u32::from_le_bytes([
            data[offset], data[offset + 1], data[offset + 2], data[offset + 3],
        ]) as usize;
        offset += 4;
        
        // Read value length
        let value_len = u32::from_le_bytes([
            data[offset], data[offset + 1], data[offset + 2], data[offset + 3],
        ]) as usize;
        offset += 4;
        
        // Validate lengths (max 64KB per key/value is reasonable)
        const MAX_KEY_LEN: usize = 64 * 1024;
        const MAX_VALUE_LEN: usize = 1024 * 1024; // 1MB max value
        
        if key_len > MAX_KEY_LEN {
            return Err(StorageError::SerializationError(format!(
                "Invalid key length in WAL entry: {} (max allowed: {})",
                key_len, MAX_KEY_LEN
            )));
        }
        
        if value_len > MAX_VALUE_LEN {
            return Err(StorageError::SerializationError(format!(
                "Invalid value length in WAL entry: {} (max allowed: {})",
                value_len, MAX_VALUE_LEN
            )));
        }
        
        // Read op type
        let op_type = OpType::from_u8(data[offset])?;
        offset += 1;
        
        // Skip padding
        offset += 3;
        
        // Validate lengths
        if offset + key_len + value_len > data.len() {
            return Err(StorageError::SerializationError(
                "Invalid key/value lengths".to_string()
            ));
        }
        
        // Read key
        let key = data[offset..offset + key_len].to_vec();
        offset += key_len;
        
        // Read value
        let value = data[offset..offset + value_len].to_vec();
        offset += value_len;
        
        // Now verify checksum over the actual data (not padding)
        let data_end = 4 + 8 + 8 + 4 + 4 + 1 + 3 + key_len + value_len;
        checksum_algo.verify(&data[4..data_end], checksum)?;
        
        Ok(Self {
            checksum,
            timestamp,
            sequence,
            key,
            value,
            op_type,
        })
    }
    
    /// Get the serialized size with alignment
    pub fn serialized_size(&self) -> usize {
        let header_size = 4 + 8 + 8 + 4 + 4 + 1 + 3;
        let data_size = header_size + self.key.len() + self.value.len();
        ((data_size + PAGE_SIZE - 1) / PAGE_SIZE) * PAGE_SIZE
    }
}

/// Sorted String Table entry
#[derive(Debug, Clone)]
pub struct SstEntry {
    pub checksum: u32,
    pub key: Vec<u8>,
    pub value: Option<Vec<u8>>, // None for tombstones
}

impl SstEntry {
    /// Create a new SST entry
    pub fn new(key: Vec<u8>, value: Option<Vec<u8>>) -> Self {
        Self {
            checksum: 0, // Will be computed during serialization
            key,
            value,
        }
    }
    
    /// Serialize the SST entry to bytes
    /// Format: [CRC32: 4B][KeyLen: 4B][ValueLen: 4B][Key][Value]
    /// ValueLen is 0 for tombstones
    pub fn serialize(&self, checksum_algo: ChecksumAlgorithm) -> Vec<u8> {
        let key_len = self.key.len() as u32;
        let value_len = self.value.as_ref().map(|v| v.len() as u32).unwrap_or(0);
        
        let size = 4 + 4 + 4 + key_len as usize + value_len as usize;
        let mut buffer = vec![0u8; size];
        let mut offset = 0;
        
        // Reserve space for checksum
        offset += 4;
        
        // Write key length
        buffer[offset..offset + 4].copy_from_slice(&key_len.to_le_bytes());
        offset += 4;
        
        // Write value length
        buffer[offset..offset + 4].copy_from_slice(&value_len.to_le_bytes());
        offset += 4;
        
        // Write key
        buffer[offset..offset + key_len as usize].copy_from_slice(&self.key);
        offset += key_len as usize;
        
        // Write value if present
        if let Some(value) = &self.value {
            buffer[offset..offset + value_len as usize].copy_from_slice(value);
            offset += value_len as usize;
        }
        
        // Compute checksum only over actual data (not any potential padding)
        let checksum = checksum_algo.compute(&buffer[4..offset]);
        
        // Write checksum
        buffer[0..4].copy_from_slice(&checksum.to_le_bytes());
        
        buffer
    }
    
    /// Deserialize an SST entry from bytes
    pub fn deserialize(data: &[u8], checksum_algo: ChecksumAlgorithm) -> Result<Self> {
        if data.len() < 12 {
            return Err(StorageError::SerializationError(
                "Data too short for SST entry".to_string()
            ));
        }
        
        let mut offset = 0;
        
        // Read checksum
        let checksum = u32::from_le_bytes([data[0], data[1], data[2], data[3]]);
        offset += 4;
        
        // Read key length
        let key_len = u32::from_le_bytes([
            data[offset], data[offset + 1], data[offset + 2], data[offset + 3],
        ]) as usize;
        offset += 4;
        
        // Read value length
        let value_len = u32::from_le_bytes([
            data[offset], data[offset + 1], data[offset + 2], data[offset + 3],
        ]) as usize;
        offset += 4;
        
        // Validate lengths (max 64KB per key/value is reasonable)
        const MAX_KEY_LEN: usize = 64 * 1024;
        const MAX_VALUE_LEN: usize = 1024 * 1024; // 1MB max value
        
        if key_len > MAX_KEY_LEN {
            return Err(StorageError::SerializationError(format!(
                "Invalid key length in SST entry: {} (max allowed: {})",
                key_len, MAX_KEY_LEN
            )));
        }
        
        if value_len > MAX_VALUE_LEN {
            return Err(StorageError::SerializationError(format!(
                "Invalid value length in SST entry: {} (max allowed: {})",
                value_len, MAX_VALUE_LEN
            )));
        }
        
        // Validate lengths
        if offset + key_len + value_len > data.len() {
            return Err(StorageError::SerializationError(
                "Invalid key/value lengths".to_string()
            ));
        }
        
        // Read key
        let key = data[offset..offset + key_len].to_vec();
        offset += key_len;
        
        // Read value (None if value_len is 0, indicating tombstone)
        let value = if value_len > 0 {
            Some(data[offset..offset + value_len].to_vec())
        } else {
            None
        };
        offset += value_len;
        
        // Now verify checksum over the actual data
        let data_end = 4 + 4 + 4 + key_len + value_len;
        checksum_algo.verify(&data[4..data_end], checksum)?;
        
        Ok(Self {
            checksum,
            key,
            value,
        })
    }
    
    /// Get the serialized size
    pub fn serialized_size(&self) -> usize {
        let value_len = self.value.as_ref().map(|v| v.len()).unwrap_or(0);
        4 + 4 + 4 + self.key.len() + value_len
    }
    
    /// Check if this entry is a tombstone
    pub fn is_tombstone(&self) -> bool {
        self.value.is_none()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_wal_entry_put_serialization() {
        let entry = WalEntry::new_put(b"key1".to_vec(), b"value1".to_vec());
        let serialized = entry.serialize(ChecksumAlgorithm::CRC32);
        
        // Should be aligned to PAGE_SIZE
        assert_eq!(serialized.len() % PAGE_SIZE, 0);
        
        let deserialized = WalEntry::deserialize(&serialized, ChecksumAlgorithm::CRC32).unwrap();
        assert_eq!(deserialized.key, b"key1");
        assert_eq!(deserialized.value, b"value1");
        assert_eq!(deserialized.op_type, OpType::Put);
    }

    #[test]
    fn test_wal_entry_delete_serialization() {
        let entry = WalEntry::new_delete(b"key1".to_vec());
        let serialized = entry.serialize(ChecksumAlgorithm::CRC32);
        
        // Should be aligned to PAGE_SIZE
        assert_eq!(serialized.len() % PAGE_SIZE, 0);
        
        let deserialized = WalEntry::deserialize(&serialized, ChecksumAlgorithm::CRC32).unwrap();
        assert_eq!(deserialized.key, b"key1");
        assert_eq!(deserialized.value.len(), 0);
        assert_eq!(deserialized.op_type, OpType::Delete);
    }

    #[test]
    fn test_wal_entry_checksum_verification() {
        let entry = WalEntry::new_put(b"key1".to_vec(), b"value1".to_vec());
        let mut serialized = entry.serialize(ChecksumAlgorithm::CRC32);
        
        // Corrupt the data
        serialized[20] ^= 0xFF;
        
        // Should fail checksum verification
        assert!(WalEntry::deserialize(&serialized, ChecksumAlgorithm::CRC32).is_err());
    }

    #[test]
    fn test_wal_entry_alignment() {
        // Test with various sizes to ensure alignment
        let test_cases = vec![
            (b"k".to_vec(), b"v".to_vec()),
            (b"key".to_vec(), b"value".to_vec()),
            (vec![0u8; 100], vec![0u8; 200]),
            (vec![0u8; 1000], vec![0u8; 2000]),
        ];
        
        for (key, value) in test_cases {
            let entry = WalEntry::new_put(key.clone(), value.clone());
            let serialized = entry.serialize(ChecksumAlgorithm::CRC32);
            
            assert_eq!(serialized.len() % PAGE_SIZE, 0);
            assert_eq!(serialized.len(), entry.serialized_size());
        }
    }

    #[test]
    fn test_sst_entry_serialization() {
        let entry = SstEntry::new(b"key1".to_vec(), Some(b"value1".to_vec()));
        let serialized = entry.serialize(ChecksumAlgorithm::CRC32);
        
        let deserialized = SstEntry::deserialize(&serialized, ChecksumAlgorithm::CRC32).unwrap();
        assert_eq!(deserialized.key, b"key1");
        assert_eq!(deserialized.value, Some(b"value1".to_vec()));
        assert!(!deserialized.is_tombstone());
    }

    #[test]
    fn test_sst_entry_tombstone() {
        let entry = SstEntry::new(b"key1".to_vec(), None);
        let serialized = entry.serialize(ChecksumAlgorithm::CRC32);
        
        let deserialized = SstEntry::deserialize(&serialized, ChecksumAlgorithm::CRC32).unwrap();
        assert_eq!(deserialized.key, b"key1");
        assert_eq!(deserialized.value, None);
        assert!(deserialized.is_tombstone());
    }

    #[test]
    fn test_sst_entry_checksum_verification() {
        let entry = SstEntry::new(b"key1".to_vec(), Some(b"value1".to_vec()));
        let mut serialized = entry.serialize(ChecksumAlgorithm::CRC32);
        
        // Corrupt the data
        serialized[10] ^= 0xFF;
        
        // Should fail checksum verification
        assert!(SstEntry::deserialize(&serialized, ChecksumAlgorithm::CRC32).is_err());
    }

    #[test]
    fn test_xxh64_serialization() {
        let entry = WalEntry::new_put(b"key1".to_vec(), b"value1".to_vec());
        let serialized = entry.serialize(ChecksumAlgorithm::XXH64);
        
        let deserialized = WalEntry::deserialize(&serialized, ChecksumAlgorithm::XXH64).unwrap();
        assert_eq!(deserialized.key, b"key1");
        assert_eq!(deserialized.value, b"value1");
    }

    #[test]
    fn test_op_type_conversion() {
        assert_eq!(OpType::from_u8(1).unwrap(), OpType::Put);
        assert_eq!(OpType::from_u8(2).unwrap(), OpType::Delete);
        assert!(OpType::from_u8(3).is_err());
    }

    #[test]
    fn test_serialized_size() {
        let entry = WalEntry::new_put(b"key1".to_vec(), b"value1".to_vec());
        let serialized = entry.serialize(ChecksumAlgorithm::CRC32);
        assert_eq!(serialized.len(), entry.serialized_size());
        
        let sst_entry = SstEntry::new(b"key1".to_vec(), Some(b"value1".to_vec()));
        let sst_serialized = sst_entry.serialize(ChecksumAlgorithm::CRC32);
        assert_eq!(sst_serialized.len(), sst_entry.serialized_size());
    }
}
