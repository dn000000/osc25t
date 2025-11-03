use crate::error::{Result, StorageError};

/// Trait for checksum algorithms
pub trait Checksum {
    /// Compute checksum for the given data
    fn compute(&self, data: &[u8]) -> u32;
    
    /// Verify that the computed checksum matches the expected value
    fn verify(&self, data: &[u8], expected: u32) -> Result<()> {
        let actual = self.compute(data);
        if actual == expected {
            Ok(())
        } else {
            Err(StorageError::ChecksumMismatch { expected, actual })
        }
    }
}

/// CRC32 checksum implementation using crc32fast
#[derive(Debug, Clone, Copy)]
pub struct Crc32;

impl Checksum for Crc32 {
    fn compute(&self, data: &[u8]) -> u32 {
        crc32fast::hash(data)
    }
}

/// XXH64 checksum implementation using xxhash-rust
/// Returns the lower 32 bits of the 64-bit hash for compatibility
#[derive(Debug, Clone, Copy)]
pub struct Xxh64 {
    seed: u64,
}

impl Xxh64 {
    /// Create a new XXH64 hasher with the given seed
    pub fn new(seed: u64) -> Self {
        Self { seed }
    }
    
    /// Create a new XXH64 hasher with default seed (0)
    pub fn default() -> Self {
        Self { seed: 0 }
    }
}

impl Checksum for Xxh64 {
    fn compute(&self, data: &[u8]) -> u32 {
        use xxhash_rust::xxh64::xxh64;
        let hash = xxh64(data, self.seed);
        // Return lower 32 bits for compatibility with u32 checksum format
        (hash & 0xFFFFFFFF) as u32
    }
}

/// Enum to select checksum algorithm
#[derive(Debug, Clone, Copy, serde::Serialize, serde::Deserialize)]
pub enum ChecksumAlgorithm {
    CRC32,
    XXH64,
}

impl ChecksumAlgorithm {
    /// Compute checksum using the selected algorithm
    pub fn compute(&self, data: &[u8]) -> u32 {
        match self {
            ChecksumAlgorithm::CRC32 => Crc32.compute(data),
            ChecksumAlgorithm::XXH64 => Xxh64::default().compute(data),
        }
    }
    
    /// Verify checksum using the selected algorithm
    pub fn verify(&self, data: &[u8], expected: u32) -> Result<()> {
        match self {
            ChecksumAlgorithm::CRC32 => Crc32.verify(data, expected),
            ChecksumAlgorithm::XXH64 => Xxh64::default().verify(data, expected),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_crc32_compute() {
        let crc32 = Crc32;
        let data = b"hello world";
        let checksum = crc32.compute(data);
        
        // CRC32 should be deterministic
        assert_eq!(checksum, crc32.compute(data));
    }

    #[test]
    fn test_crc32_verify_success() {
        let crc32 = Crc32;
        let data = b"hello world";
        let checksum = crc32.compute(data);
        
        assert!(crc32.verify(data, checksum).is_ok());
    }

    #[test]
    fn test_crc32_verify_failure() {
        let crc32 = Crc32;
        let data = b"hello world";
        let wrong_checksum = 0x12345678;
        
        assert!(crc32.verify(data, wrong_checksum).is_err());
    }

    #[test]
    fn test_xxh64_compute() {
        let xxh64 = Xxh64::default();
        let data = b"hello world";
        let checksum = xxh64.compute(data);
        
        // XXH64 should be deterministic
        assert_eq!(checksum, xxh64.compute(data));
    }

    #[test]
    fn test_xxh64_verify_success() {
        let xxh64 = Xxh64::default();
        let data = b"hello world";
        let checksum = xxh64.compute(data);
        
        assert!(xxh64.verify(data, checksum).is_ok());
    }

    #[test]
    fn test_xxh64_verify_failure() {
        let xxh64 = Xxh64::default();
        let data = b"hello world";
        let wrong_checksum = 0x12345678;
        
        assert!(xxh64.verify(data, wrong_checksum).is_err());
    }

    #[test]
    fn test_xxh64_with_seed() {
        let xxh64_seed0 = Xxh64::new(0);
        let xxh64_seed1 = Xxh64::new(1);
        let data = b"hello world";
        
        // Different seeds should produce different checksums
        assert_ne!(xxh64_seed0.compute(data), xxh64_seed1.compute(data));
    }

    #[test]
    fn test_checksum_algorithm_crc32() {
        let algo = ChecksumAlgorithm::CRC32;
        let data = b"test data";
        let checksum = algo.compute(data);
        
        assert!(algo.verify(data, checksum).is_ok());
    }

    #[test]
    fn test_checksum_algorithm_xxh64() {
        let algo = ChecksumAlgorithm::XXH64;
        let data = b"test data";
        let checksum = algo.compute(data);
        
        assert!(algo.verify(data, checksum).is_ok());
    }

    #[test]
    fn test_different_algorithms_different_checksums() {
        let data = b"test data";
        let crc32_checksum = ChecksumAlgorithm::CRC32.compute(data);
        let xxh64_checksum = ChecksumAlgorithm::XXH64.compute(data);
        
        // Different algorithms should (likely) produce different checksums
        assert_ne!(crc32_checksum, xxh64_checksum);
    }
}
