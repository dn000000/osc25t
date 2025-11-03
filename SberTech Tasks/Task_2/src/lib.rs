//! # uringKV - High-Performance Key-Value Storage
//!
//! uringKV is a log-structured key-value storage system implemented in Rust,
//! leveraging Linux io_uring for efficient asynchronous I/O operations.
//!
//! ## Architecture
//!
//! The system follows LSM-tree (Log-Structured Merge-tree) principles:
//!
//! - **Write-Ahead Log (WAL)**: Ensures durability by logging all writes before acknowledgment
//! - **Memtable**: In-memory skip list buffer for recent writes
//! - **SST Files**: Immutable sorted string tables for persistent storage
//! - **Background Compaction**: Merges SST files and removes tombstones
//! - **io_uring**: Batched async I/O with fixed files/buffers for minimal syscall overhead
//!
//! ## Example Usage
//!
//! ```no_run
//! use uringkv::{Config, StorageEngine};
//! use std::path::PathBuf;
//!
//! #[tokio::main]
//! async fn main() -> Result<(), Box<dyn std::error::Error>> {
//!     // Create configuration
//!     let config = Config::new(PathBuf::from("./data"));
//!     
//!     // Initialize storage engine
//!     let engine = StorageEngine::new(config).await?;
//!     
//!     // PUT operation
//!     engine.put(b"key1", b"value1").await?;
//!     
//!     // GET operation
//!     let value = engine.get(b"key1").await?;
//!     assert_eq!(value, Some(b"value1".to_vec()));
//!     
//!     // DELETE operation
//!     engine.delete(b"key1").await?;
//!     
//!     // SCAN operation
//!     let results = engine.scan(b"key1", b"key9").await?;
//!     
//!     // Close engine
//!     engine.close().await?;
//!     
//!     Ok(())
//! }
//! ```
//!
//! ## Modules
//!
//! - [`engine`]: Core storage engine coordinating all operations
//! - [`wal`]: Write-ahead log manager for durability
//! - [`memtable`]: In-memory skip list buffer
//! - [`sst`]: Sorted string table file management
//! - [`index`]: In-memory key-to-location index
//! - [`io_uring`]: io_uring abstraction layer
//! - [`compaction`]: Background SST file compaction
//! - [`metrics`]: Performance metrics collection
//! - [`config`]: Configuration structures
//! - [`error`]: Error types and result aliases

/// Checksum utilities (CRC32, XXH64) for data integrity
pub mod checksum;

/// Configuration structures and validation
pub mod config;

/// Entry types for WAL and SST files
pub mod entry;

/// Core storage engine implementation
pub mod engine;

/// Write-ahead log manager
pub mod wal;

/// In-memory skip list memtable
pub mod memtable;

/// Sorted string table file management
pub mod sst;

/// In-memory key-to-location index
pub mod index;

/// io_uring abstraction layer for async I/O
pub mod io_uring;

/// Background compaction for SST files
pub mod compaction;

/// Performance metrics collection and reporting
pub mod metrics;

/// Command-line interface
pub mod cli;

/// Error types and result aliases
pub mod error;

// Re-export commonly used types
pub use config::Config;
pub use engine::StorageEngine;
pub use error::{Result, StorageError};
