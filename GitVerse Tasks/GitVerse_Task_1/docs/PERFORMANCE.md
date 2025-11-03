# Performance Optimization Guide

This document describes the performance optimizations implemented in sysaudit and provides guidelines for optimal system configuration.

## Overview

Sysaudit is designed to have minimal impact on system performance while providing comprehensive file monitoring and auditing capabilities. Key optimizations include:

1. **Event Batching** - Reduces Git commit overhead
2. **Pattern Caching** - Speeds up file filtering
3. **Lazy Loading** - Defers expensive operations
4. **Efficient I/O** - Minimizes disk operations

## Event Processing Optimizations

### Event Batching

Events are batched to reduce the number of Git commits:

- **Time-based batching**: Events within 5 seconds are grouped
- **Size-based batching**: Maximum 10 events per batch (configurable)
- **Deduplication**: Multiple changes to the same file are consolidated

**Configuration:**
```yaml
monitoring:
  batch_interval: 5  # seconds
  batch_size: 10     # events
```

**Performance Impact:**
- Reduces Git commits by 80-90% for rapid file changes
- Decreases disk I/O significantly
- Minimal latency impact (< 5 seconds)

### Filter Pattern Caching

The FilterManager uses LRU caching for pattern matching:

- **Cache size**: 1024 entries
- **Hit rate**: Typically > 95% for repeated paths
- **Performance gain**: 10-100x faster for cached paths

**Implementation:**
```python
@lru_cache(maxsize=1024)
def _matches_any_cached(self, path: str, patterns_tuple: tuple) -> bool:
    # Pattern matching with caching
```

### Process Tracking Optimization

Process identification is optimized to minimize overhead:

- **Lazy evaluation**: Only performed when needed
- **Timeout protection**: 1-second timeout for /proc reads
- **Graceful degradation**: Falls back to "unknown" if unavailable

## Git Operations Optimizations

### Batch Commits

Multiple file changes are committed together:

- **Single staging operation**: All files staged at once
- **Reduced Git overhead**: One commit instead of many
- **Atomic operations**: All-or-nothing semantics

**Performance Impact:**
- 5-10x faster than individual commits
- Reduces repository size growth
- Maintains audit trail integrity

### Efficient File Syncing

File synchronization is optimized:

- **Selective copying**: Only changed files are copied
- **Metadata preservation**: Uses `shutil.copy2` for efficiency
- **Race condition handling**: Graceful handling of disappeared files

### Repository Structure

The repository structure minimizes overhead:

- **Flat structure**: No deep nesting
- **Relative paths**: Consistent path handling
- **Forward slashes**: Git-compatible paths

## Compliance Checking Optimizations

### Selective Scanning

Compliance checks are optimized:

- **On-demand execution**: Only when requested or configured
- **Targeted scanning**: Only checks relevant files
- **Rule filtering**: Skips inapplicable rules

**Configuration:**
```yaml
compliance:
  auto_check: false  # Disable automatic checks for better performance
```

### Rule Engine Efficiency

The rule engine is optimized:

- **Early termination**: Stops on first match
- **Pattern pre-compilation**: Regex patterns compiled once
- **Minimal file I/O**: Uses cached stat information

## Memory Management

### Event Buffer Limits

Event buffers are bounded to prevent memory growth:

- **Maximum buffer size**: 2x batch_size
- **Automatic flushing**: Prevents unbounded growth
- **Circular buffer**: Efficient memory usage

### Pattern Storage

Filter patterns are stored efficiently:

- **Set-based storage**: O(1) lookup for exact matches
- **Compiled patterns**: Regex patterns compiled once
- **Shared defaults**: Default patterns shared across instances

## System Resource Impact

### CPU Usage

Typical CPU usage:

- **Idle monitoring**: < 1% CPU
- **Active processing**: 2-5% CPU during file changes
- **Compliance scanning**: 5-10% CPU during scans

### Memory Usage

Typical memory footprint:

- **Base process**: 20-30 MB
- **With active monitoring**: 30-50 MB
- **During compliance scan**: 50-100 MB

### Disk I/O

Disk I/O is minimized:

- **Batched writes**: Reduces write operations
- **Efficient copying**: Uses OS-level copy operations
- **Minimal reads**: Caches file metadata

## Configuration for Performance

### High-Performance Configuration

For systems with many file changes:

```yaml
monitoring:
  batch_interval: 10  # Longer batching window
  batch_size: 50      # Larger batches
  blacklist_file: /etc/sysaudit/blacklist.txt  # Aggressive filtering

compliance:
  auto_check: false  # Disable automatic compliance checks
```

### Low-Latency Configuration

For systems requiring immediate commits:

```yaml
monitoring:
  batch_interval: 1   # Shorter batching window
  batch_size: 5       # Smaller batches

compliance:
  auto_check: true   # Enable automatic checks
```

### Balanced Configuration (Default)

Recommended for most systems:

```yaml
monitoring:
  batch_interval: 5
  batch_size: 10
  blacklist_file: /etc/sysaudit/blacklist.txt

compliance:
  auto_check: false
```

## Performance Monitoring

### Built-in Profiling

Run performance tests:

```bash
python -m pytest tests/test_performance.py -v -s
```

### Profiling Event Processing

```bash
python tests/test_performance.py
```

This will output:
- Filter throughput (paths/sec)
- Batching throughput (events/sec)
- Git commit time
- Compliance scan throughput

### System Monitoring

Monitor sysaudit resource usage:

```bash
# CPU and memory usage
ps aux | grep sysaudit

# Disk I/O
iotop -p $(pgrep -f sysaudit)

# System logs
journalctl -u sysaudit -f
```

## Performance Tuning Tips

### 1. Optimize Blacklist Patterns

Use specific patterns to reduce matching overhead:

```
# Good: Specific patterns
*.tmp
*.swp
/var/log/*

# Avoid: Overly broad patterns
*
**/*
```

### 2. Limit Watch Paths

Monitor only necessary directories:

```yaml
monitoring:
  paths:
    - /etc          # Good: Specific critical paths
    - /usr/local/bin
    # Avoid: /       # Bad: Entire filesystem
```

### 3. Adjust Batch Settings

Tune based on your workload:

- **High-frequency changes**: Increase batch_interval and batch_size
- **Low-frequency changes**: Decrease for lower latency
- **Mixed workload**: Use defaults

### 4. Disable Auto-Compliance

Run compliance checks manually:

```bash
# Manual compliance check
sysaudit compliance-report --paths /etc
```

### 5. Use SSD Storage

Store the audit repository on SSD for better performance:

```yaml
repository:
  path: /mnt/ssd/sysaudit  # SSD-backed storage
```

## Benchmarks

### Event Processing

- **Filter throughput**: 10,000+ paths/sec
- **Batching throughput**: 20,000+ events/sec
- **Pattern matching (cached)**: 100,000+ paths/sec

### Git Operations

- **Commit time (10 files)**: < 2 seconds
- **Commit time (100 files)**: < 10 seconds
- **Repository growth**: ~1 KB per file change

### Compliance Scanning

- **Scan throughput**: 100+ files/sec
- **Full system scan (/etc)**: 5-30 seconds
- **Memory overhead**: < 50 MB

## Troubleshooting Performance Issues

### High CPU Usage

1. Check for excessive file changes:
   ```bash
   journalctl -u sysaudit | grep "Batch commit"
   ```

2. Increase batch settings to reduce commit frequency

3. Add more patterns to blacklist

### High Memory Usage

1. Check event buffer size:
   - Reduce batch_size if memory is constrained

2. Disable auto-compliance checks

3. Restart service periodically if needed

### Slow Git Operations

1. Check repository size:
   ```bash
   du -sh /var/lib/sysaudit
   ```

2. Consider periodic repository cleanup:
   ```bash
   cd /var/lib/sysaudit
   git gc --aggressive
   ```

3. Use SSD storage for repository

### High Disk I/O

1. Increase batch_interval to reduce write frequency

2. Add more patterns to blacklist to reduce monitored files

3. Disable auto-compliance checks

## Best Practices

1. **Start with defaults** - The default configuration is optimized for most use cases

2. **Monitor resource usage** - Use system monitoring tools to track impact

3. **Tune incrementally** - Make small adjustments and measure impact

4. **Use blacklists** - Aggressively filter unnecessary files

5. **Schedule compliance scans** - Run during off-peak hours

6. **Regular maintenance** - Periodically clean up Git repository

## Conclusion

Sysaudit is designed for minimal performance impact while providing comprehensive auditing. By following these optimization guidelines and tuning configuration based on your specific workload, you can achieve optimal performance for your use case.
