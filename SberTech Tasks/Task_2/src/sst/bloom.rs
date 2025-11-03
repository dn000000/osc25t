use crate::error::{Result, StorageError};
use std::collections::hash_map::DefaultHasher;
use std::hash::{Hash, Hasher};

/// Simple Bloom filter implementation for key existence checks
#[derive(Debug, Clone)]
pub struct BloomFilter {
    bits: Vec<u8>,
    num_bits: usize,
    num_hashes: usize,
}

impl BloomFilter {
    /// Create a new Bloom filter with the given capacity and false positive rate
    pub fn new(capacity: usize, false_positive_rate: f64) -> Self {
        // Calculate optimal number of bits
        let num_bits = Self::optimal_num_bits(capacity, false_positive_rate);
        
        // Calculate optimal number of hash functions
        let num_hashes = Self::optimal_num_hashes(capacity, num_bits);
        
        let num_bytes = (num_bits + 7) / 8;
        
        Self {
            bits: vec![0u8; num_bytes],
            num_bits,
            num_hashes,
        }
    }
    
    /// Calculate optimal number of bits for the bloom filter
    fn optimal_num_bits(capacity: usize, false_positive_rate: f64) -> usize {
        let ln2_squared = std::f64::consts::LN_2 * std::f64::consts::LN_2;
        let bits = -(capacity as f64 * false_positive_rate.ln()) / ln2_squared;
        bits.ceil() as usize
    }
    
    /// Calculate optimal number of hash functions
    fn optimal_num_hashes(capacity: usize, num_bits: usize) -> usize {
        let hashes = (num_bits as f64 / capacity as f64) * std::f64::consts::LN_2;
        (hashes.ceil() as usize).max(1)
    }
    
    /// Insert a key into the bloom filter
    pub fn insert(&mut self, key: &[u8]) {
        for i in 0..self.num_hashes {
            let hash = self.hash(key, i);
            let bit_index = (hash % self.num_bits as u64) as usize;
            self.set_bit(bit_index);
        }
    }
    
    /// Check if a key may be in the set
    /// Returns true if the key might be present (with possible false positives)
    /// Returns false if the key is definitely not present
    pub fn may_contain(&self, key: &[u8]) -> bool {
        for i in 0..self.num_hashes {
            let hash = self.hash(key, i);
            let bit_index = (hash % self.num_bits as u64) as usize;
            if !self.get_bit(bit_index) {
                return false;
            }
        }
        true
    }
    
    /// Hash a key with a given seed
    fn hash(&self, key: &[u8], seed: usize) -> u64 {
        let mut hasher = DefaultHasher::new();
        key.hash(&mut hasher);
        seed.hash(&mut hasher);
        hasher.finish()
    }
    
    /// Set a bit at the given index
    fn set_bit(&mut self, index: usize) {
        let byte_index = index / 8;
        let bit_index = index % 8;
        self.bits[byte_index] |= 1 << bit_index;
    }
    
    /// Get a bit at the given index
    fn get_bit(&self, index: usize) -> bool {
        let byte_index = index / 8;
        let bit_index = index % 8;
        (self.bits[byte_index] & (1 << bit_index)) != 0
    }
    
    /// Serialize the bloom filter to bytes
    pub fn serialize(&self) -> Vec<u8> {
        let mut buf = Vec::new();
        
        // Write num_bits
        buf.extend_from_slice(&(self.num_bits as u64).to_le_bytes());
        
        // Write num_hashes
        buf.extend_from_slice(&(self.num_hashes as u32).to_le_bytes());
        
        // Write bits length
        buf.extend_from_slice(&(self.bits.len() as u32).to_le_bytes());
        
        // Write bits
        buf.extend_from_slice(&self.bits);
        
        buf
    }
    
    /// Deserialize a bloom filter from bytes
    pub fn deserialize(data: &[u8]) -> Result<Self> {
        if data.len() < 16 {
            return Err(StorageError::SerializationError(
                "Bloom filter data too short".to_string(),
            ));
        }
        
        let mut offset = 0;
        
        // Read num_bits
        let num_bits = u64::from_le_bytes([
            data[offset], data[offset + 1], data[offset + 2], data[offset + 3],
            data[offset + 4], data[offset + 5], data[offset + 6], data[offset + 7],
        ]) as usize;
        offset += 8;
        
        // Read num_hashes
        let num_hashes = u32::from_le_bytes([
            data[offset], data[offset + 1], data[offset + 2], data[offset + 3],
        ]) as usize;
        offset += 4;
        
        // Read bits length
        let bits_len = u32::from_le_bytes([
            data[offset], data[offset + 1], data[offset + 2], data[offset + 3],
        ]) as usize;
        offset += 4;
        
        if data.len() < offset + bits_len {
            return Err(StorageError::SerializationError(
                "Bloom filter bits data too short".to_string(),
            ));
        }
        
        // Read bits
        let bits = data[offset..offset + bits_len].to_vec();
        
        Ok(Self {
            bits,
            num_bits,
            num_hashes,
        })
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_bloom_filter_insert_and_check() {
        let mut bloom = BloomFilter::new(100, 0.01);
        
        bloom.insert(b"key1");
        bloom.insert(b"key2");
        bloom.insert(b"key3");
        
        assert!(bloom.may_contain(b"key1"));
        assert!(bloom.may_contain(b"key2"));
        assert!(bloom.may_contain(b"key3"));
    }

    #[test]
    fn test_bloom_filter_negative() {
        let mut bloom = BloomFilter::new(100, 0.01);
        
        bloom.insert(b"key1");
        bloom.insert(b"key2");
        
        // These keys were not inserted, but bloom filter might return true (false positive)
        // We can't assert false here, but we can test that inserted keys are always found
        assert!(bloom.may_contain(b"key1"));
        assert!(bloom.may_contain(b"key2"));
    }

    #[test]
    fn test_bloom_filter_serialization() {
        let mut bloom = BloomFilter::new(100, 0.01);
        
        bloom.insert(b"key1");
        bloom.insert(b"key2");
        bloom.insert(b"key3");
        
        let serialized = bloom.serialize();
        let deserialized = BloomFilter::deserialize(&serialized).unwrap();
        
        assert_eq!(deserialized.num_bits, bloom.num_bits);
        assert_eq!(deserialized.num_hashes, bloom.num_hashes);
        assert_eq!(deserialized.bits, bloom.bits);
        
        assert!(deserialized.may_contain(b"key1"));
        assert!(deserialized.may_contain(b"key2"));
        assert!(deserialized.may_contain(b"key3"));
    }

    #[test]
    fn test_bloom_filter_optimal_parameters() {
        let bloom = BloomFilter::new(1000, 0.01);
        
        // Verify that parameters are reasonable
        assert!(bloom.num_bits > 0);
        assert!(bloom.num_hashes > 0);
        assert!(bloom.bits.len() > 0);
    }

    #[test]
    fn test_bloom_filter_false_positive_rate() {
        let mut bloom = BloomFilter::new(100, 0.01);
        
        // Insert 100 keys
        for i in 0..100 {
            bloom.insert(format!("key{}", i).as_bytes());
        }
        
        // Check that all inserted keys are found
        for i in 0..100 {
            assert!(bloom.may_contain(format!("key{}", i).as_bytes()));
        }
        
        // Check false positive rate with non-inserted keys
        let mut false_positives = 0;
        let test_count = 1000;
        for i in 100..100 + test_count {
            if bloom.may_contain(format!("key{}", i).as_bytes()) {
                false_positives += 1;
            }
        }
        
        let false_positive_rate = false_positives as f64 / test_count as f64;
        
        // The actual false positive rate should be close to the target (0.01)
        // We allow some variance due to randomness
        assert!(false_positive_rate < 0.05, "False positive rate too high: {}", false_positive_rate);
    }
}
