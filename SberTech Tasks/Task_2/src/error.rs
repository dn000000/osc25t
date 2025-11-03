//! Error types for uringKV.
//!
//! This module defines all error types that can occur during storage operations.

use std::path::PathBuf;
use thiserror::Error;

/// Result type alias for uringKV operations.
///
/// This is a convenience alias for `Result<T, StorageError>`.
pub type Result<T> = std::result::Result<T, StorageError>;

/// Error types for storage operations.
///
/// All errors that can occur during uringKV operations are represented
/// by this enum. Most errors are recoverable, allowing the system to
/// continue operating.
#[derive(Error, Debug)]
pub enum StorageError {
    /// I/O error from the operating system.
    ///
    /// This includes file system errors, permission errors, and device errors.
    #[error("I/O error: {0}")]
    IoError(#[from] std::io::Error),

    /// Data corruption detected in a file.
    ///
    /// This error occurs when corrupted data is detected during recovery
    /// or normal operations. The system will skip corrupted entries and
    /// continue with valid data.
    #[error("Corrupted data in file {file:?} at offset {offset}")]
    CorruptedData {
        /// Path to the file containing corrupted data
        file: PathBuf,
        /// Byte offset where corruption was detected
        offset: u64
    },

    /// Checksum verification failed.
    ///
    /// This error indicates that data integrity check failed, suggesting
    /// data corruption or torn writes.
    #[error("Checksum mismatch: expected {expected:#x}, got {actual:#x}")]
    ChecksumMismatch {
        /// Expected checksum value
        expected: u32,
        /// Actual checksum value computed from data
        actual: u32
    },

    /// Key not found in storage.
    ///
    /// This error is returned when a GET operation is performed on a
    /// non-existent key.
    #[error("Key not found: {key:?}")]
    KeyNotFound {
        /// The key that was not found
        key: Vec<u8>
    },

    /// WAL segment is full and cannot accept more writes.
    ///
    /// This error triggers WAL segment rotation.
    #[error("WAL is full")]
    WalFull,

    /// Background compaction operation failed.
    ///
    /// Compaction failures are logged but do not prevent normal operations.
    /// The system will retry compaction later.
    #[error("Compaction failed: {0}")]
    CompactionFailed(String),

    /// Configuration validation failed.
    ///
    /// This error occurs when invalid configuration parameters are provided.
    #[error("Configuration error: {0}")]
    ConfigError(String),

    /// io_uring operation failed.
    ///
    /// This includes errors from io_uring initialization or operation submission.
    #[error("io_uring error: {0}")]
    IoUringError(String),

    /// Serialization or deserialization failed.
    ///
    /// This error occurs when converting data structures to/from bytes.
    #[error("Serialization error: {0}")]
    SerializationError(String),

    /// JSON parsing or serialization failed.
    ///
    /// This error occurs when reading or writing configuration files.
    #[error("JSON error: {0}")]
    JsonError(#[from] serde_json::Error),
}
