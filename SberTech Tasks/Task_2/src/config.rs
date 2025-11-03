use crate::checksum::ChecksumAlgorithm;
use crate::error::{Result, StorageError};
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

/// Compaction strategy for SST files.
///
/// Compaction merges multiple SST files to reclaim space and improve read performance.
/// Two strategies are supported:
///
/// - **Size-Tiered**: Groups files by similar size and merges them when threshold is reached.
///   Good for write-heavy workloads.
/// - **Leveled**: Organizes files into levels with increasing size. Good for read-heavy workloads.
#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum CompactionStrategy {
    /// Size-tiered compaction: merge files of similar size.
    ///
    /// Files are grouped by size, and when enough files of similar size exist,
    /// they are merged into a larger file. This strategy minimizes write amplification.
    SizeTiered {
        /// Size ratio threshold for triggering compaction (must be >= 1.0).
        /// A value of 1.2 means files within 20% of each other's size are considered similar.
        size_ratio: f64,
        /// Minimum number of files to trigger compaction (must be >= 2).
        min_threshold: usize,
    },
    /// Leveled compaction: organize files into levels.
    ///
    /// Files are organized into levels, with each level being larger than the previous.
    /// This strategy provides better read performance at the cost of higher write amplification.
    Leveled {
        /// Size multiplier between levels (must be >= 2).
        /// A value of 10 means each level is 10x larger than the previous.
        level_size_multiplier: usize,
        /// Maximum number of levels (must be >= 2).
        max_levels: usize,
    },
}

impl Default for CompactionStrategy {
    fn default() -> Self {
        CompactionStrategy::SizeTiered {
            size_ratio: 1.2,
            min_threshold: 4,
        }
    }
}

/// Configuration for the storage engine.
///
/// This structure contains all configurable parameters for uringKV.
/// Use the builder pattern methods to customize settings.
///
/// # Example
///
/// ```
/// use uringkv::Config;
/// use std::path::PathBuf;
///
/// let config = Config::new(PathBuf::from("./data"))
///     .with_wal_segment_size(256 * 1024 * 1024)  // 256MB
///     .with_memtable_size(128 * 1024 * 1024)     // 128MB
///     .with_queue_depth(512);
///
/// assert!(config.validate().is_ok());
/// ```
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Config {
    /// Directory for storing data files.
    ///
    /// This directory will contain subdirectories for WAL and SST files.
    pub data_dir: PathBuf,
    
    /// Maximum size of a WAL segment in bytes (default: 128MB).
    ///
    /// When a segment reaches this size, a new segment is created.
    /// Valid range: 1MB - 1GB.
    pub wal_segment_size: u64,
    
    /// Maximum size of memtable in bytes (default: 64MB).
    ///
    /// When memtable reaches this size, it is flushed to an SST file.
    /// Valid range: 1MB - 512MB.
    pub memtable_size: u64,
    
    /// io_uring queue depth (default: 256).
    ///
    /// Number of I/O operations that can be queued simultaneously.
    /// Higher values allow more parallelism but use more memory.
    /// Valid range: 1 - 4096.
    pub queue_depth: u32,
    
    /// Compaction strategy for SST files.
    ///
    /// Determines how SST files are merged during background compaction.
    pub compaction_strategy: CompactionStrategy,
    
    /// Enable SQPOLL mode for io_uring (default: false).
    ///
    /// When enabled, io_uring uses kernel-side polling to reduce syscall overhead.
    /// Requires additional kernel resources.
    pub enable_sqpoll: bool,
    
    /// Checksum algorithm to use for data integrity.
    ///
    /// All WAL and SST entries are protected with checksums.
    pub checksum_algorithm: ChecksumAlgorithm,
    
    /// Group commit interval in milliseconds (default: 10ms).
    ///
    /// Multiple write operations within this interval are batched into
    /// a single fsync call. Lower values reduce latency but decrease throughput.
    /// Valid range: 1ms - 1000ms.
    pub group_commit_interval_ms: u64,
}

impl Config {
    /// Creates a new configuration with the given data directory and default values.
    ///
    /// # Arguments
    ///
    /// * `data_dir` - Path to the directory where data files will be stored
    ///
    /// # Default Values
    ///
    /// - WAL segment size: 128MB
    /// - Memtable size: 64MB
    /// - Queue depth: 256
    /// - Compaction: Size-tiered (ratio: 1.2, threshold: 4)
    /// - SQPOLL: Disabled
    /// - Checksum: CRC32
    /// - Group commit interval: 10ms
    ///
    /// # Example
    ///
    /// ```
    /// use uringkv::Config;
    /// use std::path::PathBuf;
    ///
    /// let config = Config::new(PathBuf::from("./data"));
    /// assert_eq!(config.queue_depth, 256);
    /// ```
    pub fn new(data_dir: PathBuf) -> Self {
        Self {
            data_dir,
            wal_segment_size: 128 * 1024 * 1024,  // 128MB
            memtable_size: 64 * 1024 * 1024,       // 64MB
            queue_depth: 256,
            compaction_strategy: CompactionStrategy::default(),
            enable_sqpoll: false,
            checksum_algorithm: ChecksumAlgorithm::CRC32,
            group_commit_interval_ms: 10,
        }
    }
    
    /// Validates the configuration parameters.
    ///
    /// Checks that all parameters are within valid ranges and constraints.
    ///
    /// # Returns
    ///
    /// Returns `Ok(())` if configuration is valid, or an error describing
    /// the validation failure.
    ///
    /// # Errors
    ///
    /// Returns `ConfigError` if any parameter is invalid:
    /// - Empty data directory
    /// - WAL segment size < 1MB or > 1GB
    /// - Memtable size < 1MB or > 512MB
    /// - Queue depth < 1 or > 4096
    /// - Group commit interval < 1ms or > 1000ms
    /// - Invalid compaction strategy parameters
    ///
    /// # Example
    ///
    /// ```
    /// use uringkv::Config;
    /// use std::path::PathBuf;
    ///
    /// let config = Config::new(PathBuf::from("./data"));
    /// assert!(config.validate().is_ok());
    ///
    /// let invalid = Config::new(PathBuf::from("./data"))
    ///     .with_queue_depth(0);  // Invalid
    /// assert!(invalid.validate().is_err());
    /// ```
    pub fn validate(&self) -> Result<()> {
        // Validate data directory
        if self.data_dir.as_os_str().is_empty() {
            return Err(StorageError::ConfigError(
                "data_dir cannot be empty".to_string()
            ));
        }
        
        // Validate WAL segment size (minimum 1MB, maximum 1GB)
        if self.wal_segment_size < 1024 * 1024 {
            return Err(StorageError::ConfigError(
                "wal_segment_size must be at least 1MB".to_string()
            ));
        }
        if self.wal_segment_size > 1024 * 1024 * 1024 {
            return Err(StorageError::ConfigError(
                "wal_segment_size cannot exceed 1GB".to_string()
            ));
        }
        
        // Validate memtable size (minimum 1MB, maximum 512MB)
        if self.memtable_size < 1024 * 1024 {
            return Err(StorageError::ConfigError(
                "memtable_size must be at least 1MB".to_string()
            ));
        }
        if self.memtable_size > 512 * 1024 * 1024 {
            return Err(StorageError::ConfigError(
                "memtable_size cannot exceed 512MB".to_string()
            ));
        }
        
        // Validate queue depth (minimum 1, maximum 4096)
        if self.queue_depth < 1 {
            return Err(StorageError::ConfigError(
                "queue_depth must be at least 1".to_string()
            ));
        }
        if self.queue_depth > 4096 {
            return Err(StorageError::ConfigError(
                "queue_depth cannot exceed 4096".to_string()
            ));
        }
        
        // Validate group commit interval (minimum 1ms, maximum 1000ms)
        if self.group_commit_interval_ms < 1 {
            return Err(StorageError::ConfigError(
                "group_commit_interval_ms must be at least 1".to_string()
            ));
        }
        if self.group_commit_interval_ms > 1000 {
            return Err(StorageError::ConfigError(
                "group_commit_interval_ms cannot exceed 1000".to_string()
            ));
        }
        
        // Validate compaction strategy
        match &self.compaction_strategy {
            CompactionStrategy::SizeTiered { size_ratio, min_threshold } => {
                if *size_ratio < 1.0 {
                    return Err(StorageError::ConfigError(
                        "size_ratio must be at least 1.0".to_string()
                    ));
                }
                if *min_threshold < 2 {
                    return Err(StorageError::ConfigError(
                        "min_threshold must be at least 2".to_string()
                    ));
                }
            }
            CompactionStrategy::Leveled { level_size_multiplier, max_levels } => {
                if *level_size_multiplier < 2 {
                    return Err(StorageError::ConfigError(
                        "level_size_multiplier must be at least 2".to_string()
                    ));
                }
                if *max_levels < 2 {
                    return Err(StorageError::ConfigError(
                        "max_levels must be at least 2".to_string()
                    ));
                }
            }
        }
        
        Ok(())
    }
    
    /// Set WAL segment size
    pub fn with_wal_segment_size(mut self, size: u64) -> Self {
        self.wal_segment_size = size;
        self
    }
    
    /// Set memtable size
    pub fn with_memtable_size(mut self, size: u64) -> Self {
        self.memtable_size = size;
        self
    }
    
    /// Set queue depth
    pub fn with_queue_depth(mut self, depth: u32) -> Self {
        self.queue_depth = depth;
        self
    }
    
    /// Set compaction strategy
    pub fn with_compaction_strategy(mut self, strategy: CompactionStrategy) -> Self {
        self.compaction_strategy = strategy;
        self
    }
    
    /// Enable SQPOLL mode
    pub fn with_sqpoll(mut self, enable: bool) -> Self {
        self.enable_sqpoll = enable;
        self
    }
    
    /// Set checksum algorithm
    pub fn with_checksum_algorithm(mut self, algorithm: ChecksumAlgorithm) -> Self {
        self.checksum_algorithm = algorithm;
        self
    }
    
    /// Set group commit interval
    pub fn with_group_commit_interval(mut self, interval_ms: u64) -> Self {
        self.group_commit_interval_ms = interval_ms;
        self
    }
}

impl Default for Config {
    fn default() -> Self {
        Self::new(PathBuf::from("./data"))
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_config_default_values() {
        let config = Config::new(PathBuf::from("/tmp/test"));
        
        assert_eq!(config.wal_segment_size, 128 * 1024 * 1024);
        assert_eq!(config.memtable_size, 64 * 1024 * 1024);
        assert_eq!(config.queue_depth, 256);
        assert_eq!(config.enable_sqpoll, false);
        assert_eq!(config.group_commit_interval_ms, 10);
    }

    #[test]
    fn test_config_validation_success() {
        let config = Config::new(PathBuf::from("/tmp/test"));
        assert!(config.validate().is_ok());
    }

    #[test]
    fn test_config_validation_empty_data_dir() {
        let config = Config::new(PathBuf::from(""));
        assert!(config.validate().is_err());
    }

    #[test]
    fn test_config_validation_wal_segment_too_small() {
        let config = Config::new(PathBuf::from("/tmp/test"))
            .with_wal_segment_size(1024); // 1KB, too small
        assert!(config.validate().is_err());
    }

    #[test]
    fn test_config_validation_wal_segment_too_large() {
        let config = Config::new(PathBuf::from("/tmp/test"))
            .with_wal_segment_size(2 * 1024 * 1024 * 1024); // 2GB, too large
        assert!(config.validate().is_err());
    }

    #[test]
    fn test_config_validation_memtable_too_small() {
        let config = Config::new(PathBuf::from("/tmp/test"))
            .with_memtable_size(1024); // 1KB, too small
        assert!(config.validate().is_err());
    }

    #[test]
    fn test_config_validation_queue_depth_zero() {
        let config = Config::new(PathBuf::from("/tmp/test"))
            .with_queue_depth(0);
        assert!(config.validate().is_err());
    }

    #[test]
    fn test_config_validation_queue_depth_too_large() {
        let config = Config::new(PathBuf::from("/tmp/test"))
            .with_queue_depth(5000);
        assert!(config.validate().is_err());
    }

    #[test]
    fn test_config_builder_pattern() {
        let config = Config::new(PathBuf::from("/tmp/test"))
            .with_wal_segment_size(256 * 1024 * 1024)
            .with_memtable_size(128 * 1024 * 1024)
            .with_queue_depth(512)
            .with_sqpoll(true)
            .with_group_commit_interval(20);
        
        assert_eq!(config.wal_segment_size, 256 * 1024 * 1024);
        assert_eq!(config.memtable_size, 128 * 1024 * 1024);
        assert_eq!(config.queue_depth, 512);
        assert_eq!(config.enable_sqpoll, true);
        assert_eq!(config.group_commit_interval_ms, 20);
        assert!(config.validate().is_ok());
    }

    #[test]
    fn test_compaction_strategy_size_tiered_validation() {
        let config = Config::new(PathBuf::from("/tmp/test"))
            .with_compaction_strategy(CompactionStrategy::SizeTiered {
                size_ratio: 0.5, // Invalid: less than 1.0
                min_threshold: 4,
            });
        assert!(config.validate().is_err());
    }

    #[test]
    fn test_compaction_strategy_leveled_validation() {
        let config = Config::new(PathBuf::from("/tmp/test"))
            .with_compaction_strategy(CompactionStrategy::Leveled {
                level_size_multiplier: 1, // Invalid: less than 2
                max_levels: 5,
            });
        assert!(config.validate().is_err());
    }
}
