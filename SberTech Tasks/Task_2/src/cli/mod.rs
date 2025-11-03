use clap::{Parser, Subcommand};
use std::path::PathBuf;
use crate::error::Result;

#[derive(Parser)]
#[command(name = "uringkv")]
#[command(about = "High-performance key-value storage using io_uring", long_about = None)]
pub struct Command {
    #[command(subcommand)]
    pub command: Commands,
}

#[derive(Subcommand)]
pub enum Commands {
    /// Initialize storage at specified path
    Init {
        /// Data directory path
        #[arg(short, long)]
        path: PathBuf,
        
        /// io_uring queue depth
        #[arg(short, long, default_value = "256")]
        queue_depth: u32,
        
        /// WAL segment size in MB
        #[arg(short, long, default_value = "128")]
        segment_size: u64,
        
        /// Enable SQPOLL mode for io_uring
        #[arg(long, default_value = "false")]
        enable_sqpoll: bool,
    },
    
    /// Put a key-value pair
    Put {
        /// Key to store
        key: String,
        
        /// Value to store
        value: String,
        
        /// Data directory path
        #[arg(short, long, default_value = "./data")]
        path: PathBuf,
    },
    
    /// Get value for a key
    Get {
        /// Key to retrieve
        key: String,
        
        /// Data directory path
        #[arg(short, long, default_value = "./data")]
        path: PathBuf,
    },
    
    /// Delete a key
    Delete {
        /// Key to delete
        key: String,
        
        /// Data directory path
        #[arg(short, long, default_value = "./data")]
        path: PathBuf,
    },
    
    /// Scan key range
    Scan {
        /// Start key (inclusive)
        start: String,
        
        /// End key (exclusive)
        end: String,
        
        /// Data directory path
        #[arg(short, long, default_value = "./data")]
        path: PathBuf,
    },
    
    /// Run benchmark
    Bench {
        /// Number of keys
        #[arg(short, long, default_value = "1000000")]
        keys: u64,
        
        /// Read percentage (0-100)
        #[arg(short, long, default_value = "70")]
        read_pct: u8,
        
        /// Write percentage (0-100)
        #[arg(short, long, default_value = "30")]
        write_pct: u8,
        
        /// Duration in seconds
        #[arg(short, long, default_value = "60")]
        duration: u64,
        
        /// Data directory path
        #[arg(short, long, default_value = "./data")]
        path: PathBuf,
    },
    
    /// Display performance metrics
    Metrics {
        /// Data directory path
        #[arg(short, long)]
        path: PathBuf,
    },
}

pub async fn execute_command(cmd: Command) -> Result<()> {
    match cmd.command {
        Commands::Init { path, queue_depth, segment_size, enable_sqpoll } => {
            execute_init_command(path, queue_depth, segment_size, enable_sqpoll).await
        }
        Commands::Put { key, value, path } => {
            execute_put_command(key, value, path).await
        }
        Commands::Get { key, path } => {
            execute_get_command(key, path).await
        }
        Commands::Delete { key, path } => {
            execute_delete_command(key, path).await
        }
        Commands::Scan { start, end, path } => {
            execute_scan_command(start, end, path).await
        }
        Commands::Bench { keys, read_pct, write_pct, duration, path } => {
            execute_bench_command(keys, read_pct, write_pct, duration, path).await
        }
        Commands::Metrics { path } => {
            execute_metrics_command(path).await
        }
    }
}

async fn execute_init_command(
    path: PathBuf,
    queue_depth: u32,
    segment_size: u64,
    enable_sqpoll: bool,
) -> Result<()> {
    use crate::config::{Config, CompactionStrategy};
    use crate::checksum::ChecksumAlgorithm;
    
    println!("Initializing uringKV storage at: {}", path.display());
    
    // Create data directory structure
    std::fs::create_dir_all(&path)?;
    std::fs::create_dir_all(path.join("wal"))?;
    std::fs::create_dir_all(path.join("sst"))?;
    
    println!("  ✓ Created data directory structure");
    
    // Create configuration
    let config = Config::new(path.clone())
        .with_wal_segment_size(segment_size * 1024 * 1024) // Convert MB to bytes
        .with_memtable_size(64 * 1024 * 1024)
        .with_queue_depth(queue_depth)
        .with_compaction_strategy(CompactionStrategy::SizeTiered {
            size_ratio: 2.0,
            min_threshold: 4,
        })
        .with_checksum_algorithm(ChecksumAlgorithm::CRC32)
        .with_group_commit_interval(10)
        .with_sqpoll(enable_sqpoll);
    
    // Validate configuration
    config.validate()?;
    
    // Save configuration file
    let config_path = path.join("config.json");
    let config_json = serde_json::to_string_pretty(&config)?;
    std::fs::write(&config_path, config_json)?;
    
    println!("  ✓ Created configuration file: {}", config_path.display());
    println!("\nConfiguration:");
    println!("  WAL segment size: {} MB", segment_size);
    println!("  Memtable size: 64 MB");
    println!("  Queue depth: {}", queue_depth);
    println!("  SQPOLL mode: {}", if enable_sqpoll { "enabled" } else { "disabled" });
    println!("\nStorage initialized successfully!");
    
    Ok(())
}

async fn execute_put_command(key: String, value: String, path: PathBuf) -> Result<()> {
    use crate::engine::StorageEngine;
    
    // Load configuration
    let config = load_config_from_path(path)?;
    
    // Open storage engine
    let engine = StorageEngine::new(config).await?;
    
    // Perform PUT operation
    engine.put(key.as_bytes(), value.as_bytes()).await?;
    
    println!("✓ Put key: {}", key);
    
    // Close engine
    engine.close().await?;
    
    Ok(())
}

async fn execute_get_command(key: String, path: PathBuf) -> Result<()> {
    use crate::engine::StorageEngine;
    
    // Load configuration
    let config = load_config_from_path(path)?;
    
    // Open storage engine
    let engine = StorageEngine::new(config).await?;
    
    // Perform GET operation
    match engine.get(key.as_bytes()).await? {
        Some(value) => {
            let value_str = String::from_utf8_lossy(&value);
            println!("{}", value_str);
        }
        None => {
            println!("Key not found: {}", key);
        }
    }
    
    // Close engine
    engine.close().await?;
    
    Ok(())
}

async fn execute_delete_command(key: String, path: PathBuf) -> Result<()> {
    use crate::engine::StorageEngine;
    
    // Load configuration
    let config = load_config_from_path(path)?;
    
    // Open storage engine
    let engine = StorageEngine::new(config).await?;
    
    // Perform DELETE operation
    engine.delete(key.as_bytes()).await?;
    
    println!("✓ Deleted key: {}", key);
    
    // Close engine
    engine.close().await?;
    
    Ok(())
}

async fn execute_scan_command(start: String, end: String, path: PathBuf) -> Result<()> {
    use crate::engine::StorageEngine;
    
    // Load configuration
    let config = load_config_from_path(path)?;
    
    // Open storage engine
    let engine = StorageEngine::new(config).await?;
    
    // Perform SCAN operation
    let results = engine.scan(start.as_bytes(), end.as_bytes()).await?;
    
    println!("Found {} entries:", results.len());
    for (key, value) in results {
        let key_str = String::from_utf8_lossy(&key);
        let value_str = String::from_utf8_lossy(&value);
        println!("  {} = {}", key_str, value_str);
    }
    
    // Close engine
    engine.close().await?;
    
    Ok(())
}

async fn execute_bench_command(
    keys: u64,
    read_pct: u8,
    write_pct: u8,
    duration: u64,
    path: PathBuf,
) -> Result<()> {
    use crate::engine::StorageEngine;
    use std::time::{Duration, Instant};
    use rand::Rng;
    
    // Validate percentages
    if read_pct + write_pct != 100 {
        return Err(crate::error::StorageError::ConfigError(
            format!("Read and write percentages must sum to 100 (got {})", read_pct + write_pct)
        ));
    }
    
    println!("=== uringKV Benchmark ===");
    println!("Configuration:");
    println!("  Total keys: {}", keys);
    println!("  Read percentage: {}%", read_pct);
    println!("  Write percentage: {}%", write_pct);
    println!("  Duration: {} seconds", duration);
    println!("  Data path: {}", path.display());
    println!();
    
    // Load configuration
    let config = load_config_from_path(path)?;
    
    // Open storage engine
    let engine = StorageEngine::new(config).await?;
    
    println!("Populating initial data...");
    
    // Pre-populate with initial keys
    for i in 0..keys {
        let key = format!("bench_key_{:010}", i);
        let value = format!("bench_value_{:010}", i);
        engine.put(key.as_bytes(), value.as_bytes()).await?;
        
        if (i + 1) % 10000 == 0 {
            println!("  Populated {} / {} keys", i + 1, keys);
        }
    }
    
    println!("✓ Initial data populated\n");
    println!("Running benchmark...");
    
    let start_time = Instant::now();
    let duration_secs = Duration::from_secs(duration);
    let mut rng = rand::thread_rng();
    let mut operation_count = 0u64;
    let mut read_count = 0u64;
    let mut write_count = 0u64;
    
    while start_time.elapsed() < duration_secs {
        // Decide operation type based on percentages
        let op_type = rng.gen_range(0..100);
        
        if op_type < read_pct {
            // Perform read operation
            let key_idx = rng.gen_range(0..keys);
            let key = format!("bench_key_{:010}", key_idx);
            let _ = engine.get(key.as_bytes()).await?;
            read_count += 1;
        } else {
            // Perform write operation
            let key_idx = rng.gen_range(0..keys);
            let key = format!("bench_key_{:010}", key_idx);
            let value = format!("updated_value_{:010}_{}", key_idx, operation_count);
            engine.put(key.as_bytes(), value.as_bytes()).await?;
            write_count += 1;
        }
        
        operation_count += 1;
        
        // Print progress every 10000 operations
        if operation_count % 10000 == 0 {
            let elapsed = start_time.elapsed().as_secs_f64();
            let ops_per_sec = operation_count as f64 / elapsed;
            print!("\r  Operations: {} | Throughput: {:.0} ops/sec", operation_count, ops_per_sec);
            use std::io::Write;
            std::io::stdout().flush().unwrap();
        }
    }
    
    println!("\n\n=== Benchmark Results ===");
    
    let elapsed = start_time.elapsed().as_secs_f64();
    let throughput = operation_count as f64 / elapsed;
    
    println!("Duration: {:.2} seconds", elapsed);
    println!("Total operations: {}", operation_count);
    println!("  Reads: {} ({:.1}%)", read_count, (read_count as f64 / operation_count as f64) * 100.0);
    println!("  Writes: {} ({:.1}%)", write_count, (write_count as f64 / operation_count as f64) * 100.0);
    println!("Throughput: {:.0} ops/sec", throughput);
    println!();
    
    // Get metrics from engine
    let report = engine.metrics().report();
    
    println!("Latency Percentiles (microseconds):");
    for (operation, (p50, p95, p99)) in &report.operation_latencies {
        println!("  {}:", operation);
        println!("    p50: {:.2} µs", p50);
        println!("    p95: {:.2} µs", p95);
        println!("    p99: {:.2} µs", p99);
    }
    println!();
    
    println!("System Metrics:");
    println!("  Memory allocations: {}", report.allocations);
    println!("  fsync calls: {}", report.fsync_count);
    println!("  fdatasync calls: {}", report.fdatasync_count);
    
    // Close engine
    engine.close().await?;
    
    Ok(())
}

async fn execute_metrics_command(path: PathBuf) -> Result<()> {
    use crate::config::{Config, CompactionStrategy};
    use crate::engine::StorageEngine;
    use crate::checksum::ChecksumAlgorithm;
    
    // Create a config and open the storage engine
    let config = Config::new(path)
        .with_wal_segment_size(128 * 1024 * 1024)
        .with_memtable_size(64 * 1024 * 1024)
        .with_queue_depth(256)
        .with_compaction_strategy(CompactionStrategy::SizeTiered {
            size_ratio: 2.0,
            min_threshold: 4,
        })
        .with_checksum_algorithm(ChecksumAlgorithm::CRC32)
        .with_group_commit_interval(10);
    
    let engine = StorageEngine::new(config).await?;
    
    // Get metrics report
    let report = engine.metrics().report();
    
    // Display metrics
    println!("=== uringKV Performance Metrics ===\n");
    
    println!("Throughput:");
    println!("  Total operations: {}", report.throughput);
    println!();
    
    println!("Operation Latencies (microseconds):");
    for (operation, (p50, p95, p99)) in &report.operation_latencies {
        println!("  {}:", operation);
        println!("    p50: {:.2} µs", p50);
        println!("    p95: {:.2} µs", p95);
        println!("    p99: {:.2} µs", p99);
    }
    println!();
    
    println!("System Metrics:");
    println!("  Memory allocations: {}", report.allocations);
    println!("  fsync calls: {}", report.fsync_count);
    println!("  fdatasync calls: {}", report.fdatasync_count);
    println!();
    
    // Close the engine
    engine.close().await?;
    
    Ok(())
}

/// Load configuration from the default data directory
fn _load_config() -> Result<crate::config::Config> {
    load_config_from_path(PathBuf::from("./data"))
}

fn load_config_from_path(data_dir: PathBuf) -> Result<crate::config::Config> {
    use crate::error::StorageError;
    
    let config_path = data_dir.join("config.json");
    
    if config_path.exists() {
        let config_json = std::fs::read_to_string(&config_path)?;
        let config: crate::config::Config = serde_json::from_str(&config_json)?;
        Ok(config)
    } else {
        Err(StorageError::ConfigError(
            format!("Configuration file not found at {}. Run 'uringkv init --path {}' first.", 
                config_path.display(), data_dir.display())
        ))
    }
}


#[cfg(test)]
mod tests {
    use super::*;
    use tempfile::TempDir;

    #[tokio::test]
    async fn test_init_command() {
        let temp_dir = TempDir::new().unwrap();
        let path = temp_dir.path().to_path_buf();
        
        // Execute init command
        let result = execute_init_command(path.clone(), 256, 128, false).await;
        assert!(result.is_ok());
        
        // Verify directory structure was created
        assert!(path.join("wal").exists());
        assert!(path.join("sst").exists());
        assert!(path.join("config.json").exists());
        
        // Verify config file content
        let config_json = std::fs::read_to_string(path.join("config.json")).unwrap();
        let config: crate::config::Config = serde_json::from_str(&config_json).unwrap();
        assert_eq!(config.queue_depth, 256);
        assert_eq!(config.wal_segment_size, 128 * 1024 * 1024);
    }

    #[tokio::test]
    async fn test_put_and_get_commands() {
        let temp_dir = TempDir::new().unwrap();
        let path = temp_dir.path().to_path_buf();
        
        // Initialize storage
        execute_init_command(path.clone(), 256, 128, false).await.unwrap();
        
        // Change to temp directory for config loading
        let original_dir = std::env::current_dir().unwrap();
        std::env::set_current_dir(&temp_dir).unwrap();
        
        // Execute put command
        let result = execute_put_command("test_key".to_string(), "test_value".to_string(), path.clone()).await;
        assert!(result.is_ok());
        
        // Execute get command
        let result = execute_get_command("test_key".to_string(), path.clone()).await;
        assert!(result.is_ok());
        
        // Restore original directory
        std::env::set_current_dir(original_dir).unwrap();
    }

    #[tokio::test]
    async fn test_delete_command() {
        let temp_dir = TempDir::new().unwrap();
        let path = temp_dir.path().to_path_buf();
        
        // Initialize storage
        execute_init_command(path.clone(), 256, 128, false).await.unwrap();
        
        // Change to temp directory for config loading
        let original_dir = std::env::current_dir().unwrap();
        std::env::set_current_dir(&temp_dir).unwrap();
        
        // Put a key
        execute_put_command("test_key".to_string(), "test_value".to_string(), path.clone()).await.unwrap();
        
        // Delete the key
        let result = execute_delete_command("test_key".to_string(), path.clone()).await;
        assert!(result.is_ok());
        
        // Restore original directory
        std::env::set_current_dir(original_dir).unwrap();
    }

    #[tokio::test]
    async fn test_scan_command() {
        let temp_dir = TempDir::new().unwrap();
        let path = temp_dir.path().to_path_buf();
        
        // Initialize storage
        execute_init_command(path.clone(), 256, 128, false).await.unwrap();
        
        // Change to temp directory for config loading
        let original_dir = std::env::current_dir().unwrap();
        std::env::set_current_dir(&temp_dir).unwrap();
        
        // Put multiple keys
        execute_put_command("key1".to_string(), "value1".to_string(), path.clone()).await.unwrap();
        execute_put_command("key2".to_string(), "value2".to_string(), path.clone()).await.unwrap();
        execute_put_command("key3".to_string(), "value3".to_string(), path.clone()).await.unwrap();
        
        // Execute scan command
        let result = execute_scan_command("key1".to_string(), "key4".to_string(), path.clone()).await;
        assert!(result.is_ok());
        
        // Restore original directory
        std::env::set_current_dir(original_dir).unwrap();
    }

    #[tokio::test]
    async fn test_bench_command_validation() {
        // Test invalid percentages
        let temp_dir = TempDir::new().unwrap();
        let path = temp_dir.path().to_path_buf();
        
        // Initialize storage
        execute_init_command(path.clone(), 256, 128, false).await.unwrap();
        
        // Change to temp directory for config loading
        let original_dir = std::env::current_dir().unwrap();
        std::env::set_current_dir(&temp_dir).unwrap();
        
        // Create data directory and copy config
        // Test with invalid percentages (should fail)
        let result = execute_bench_command(100, 50, 30, 1, path.clone()).await;
        assert!(result.is_err());
        
        // Restore original directory
        std::env::set_current_dir(original_dir).unwrap();
    }

    #[test]
    fn test_command_parsing() {
        // Test init command parsing
        let args = vec!["uringkv", "init", "--path", "/tmp/test", "--queue-depth", "512"];
        let cmd = Command::try_parse_from(args);
        assert!(cmd.is_ok());
        
        // Test put command parsing
        let args = vec!["uringkv", "put", "mykey", "myvalue"];
        let cmd = Command::try_parse_from(args);
        assert!(cmd.is_ok());
        
        // Test get command parsing
        let args = vec!["uringkv", "get", "mykey"];
        let cmd = Command::try_parse_from(args);
        assert!(cmd.is_ok());
        
        // Test delete command parsing
        let args = vec!["uringkv", "delete", "mykey"];
        let cmd = Command::try_parse_from(args);
        assert!(cmd.is_ok());
        
        // Test scan command parsing
        let args = vec!["uringkv", "scan", "start_key", "end_key"];
        let cmd = Command::try_parse_from(args);
        assert!(cmd.is_ok());
        
        // Test bench command parsing
        let args = vec!["uringkv", "bench", "--keys", "1000", "--read-pct", "70", "--write-pct", "30", "--duration", "10"];
        let cmd = Command::try_parse_from(args);
        assert!(cmd.is_ok());
    }
}
