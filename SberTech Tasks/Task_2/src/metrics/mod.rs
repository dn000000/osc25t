use hdrhistogram::Histogram;
use std::collections::HashMap;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::Mutex;
use std::time::Duration;

/// Metrics collector for performance tracking
pub struct Metrics {
    operation_latencies: Mutex<HashMap<String, Histogram<u64>>>,
    throughput: AtomicU64,
    allocations: AtomicU64,
    fsync_count: AtomicU64,
    fdatasync_count: AtomicU64,
}

impl Metrics {
    pub fn new() -> Self {
        Self {
            operation_latencies: Mutex::new(HashMap::new()),
            throughput: AtomicU64::new(0),
            allocations: AtomicU64::new(0),
            fsync_count: AtomicU64::new(0),
            fdatasync_count: AtomicU64::new(0),
        }
    }

    pub fn record_latency(&self, operation: &str, duration: Duration) {
        let mut latencies = self.operation_latencies.lock().unwrap();
        let histogram = latencies
            .entry(operation.to_string())
            .or_insert_with(|| Histogram::<u64>::new(3).unwrap());
        
        let micros = duration.as_micros() as u64;
        let _ = histogram.record(micros);
    }

    pub fn increment_throughput(&self) {
        self.throughput.fetch_add(1, Ordering::Relaxed);
    }

    pub fn increment_allocations(&self) {
        self.allocations.fetch_add(1, Ordering::Relaxed);
    }

    pub fn increment_fsync(&self) {
        self.fsync_count.fetch_add(1, Ordering::Relaxed);
    }

    pub fn increment_fdatasync(&self) {
        self.fdatasync_count.fetch_add(1, Ordering::Relaxed);
    }

    pub fn get_percentiles(&self, operation: &str) -> (f64, f64, f64) {
        let latencies = self.operation_latencies.lock().unwrap();
        if let Some(histogram) = latencies.get(operation) {
            let p50 = histogram.value_at_quantile(0.50) as f64;
            let p95 = histogram.value_at_quantile(0.95) as f64;
            let p99 = histogram.value_at_quantile(0.99) as f64;
            (p50, p95, p99)
        } else {
            (0.0, 0.0, 0.0)
        }
    }

    pub fn get_throughput(&self) -> u64 {
        self.throughput.load(Ordering::Relaxed)
    }

    pub fn report(&self) -> MetricsReport {
        let mut operation_latencies = HashMap::new();
        let latencies = self.operation_latencies.lock().unwrap();
        
        for (op, histogram) in latencies.iter() {
            let p50 = histogram.value_at_quantile(0.50) as f64;
            let p95 = histogram.value_at_quantile(0.95) as f64;
            let p99 = histogram.value_at_quantile(0.99) as f64;
            operation_latencies.insert(op.clone(), (p50, p95, p99));
        }
        
        MetricsReport {
            throughput: self.throughput.load(Ordering::Relaxed),
            allocations: self.allocations.load(Ordering::Relaxed),
            fsync_count: self.fsync_count.load(Ordering::Relaxed),
            fdatasync_count: self.fdatasync_count.load(Ordering::Relaxed),
            operation_latencies,
        }
    }
}

#[derive(Debug)]
pub struct MetricsReport {
    pub throughput: u64,
    pub allocations: u64,
    pub fsync_count: u64,
    pub fdatasync_count: u64,
    pub operation_latencies: HashMap<String, (f64, f64, f64)>, // (p50, p95, p99)
}

#[cfg(test)]
mod tests {
    use super::*;
    use std::time::Duration;

    #[test]
    fn test_metrics_creation() {
        let metrics = Metrics::new();
        assert_eq!(metrics.get_throughput(), 0);
    }

    #[test]
    fn test_latency_recording() {
        let metrics = Metrics::new();
        
        // Record some latencies for PUT operation
        metrics.record_latency("put", Duration::from_micros(100));
        metrics.record_latency("put", Duration::from_micros(200));
        metrics.record_latency("put", Duration::from_micros(150));
        
        // Get percentiles
        let (p50, p95, p99) = metrics.get_percentiles("put");
        
        // Verify percentiles are in reasonable range
        assert!(p50 > 0.0);
        assert!(p95 > 0.0);
        assert!(p99 > 0.0);
        assert!(p50 <= p95);
        assert!(p95 <= p99);
    }

    #[test]
    fn test_throughput_counter() {
        let metrics = Metrics::new();
        
        assert_eq!(metrics.get_throughput(), 0);
        
        metrics.increment_throughput();
        assert_eq!(metrics.get_throughput(), 1);
        
        metrics.increment_throughput();
        metrics.increment_throughput();
        assert_eq!(metrics.get_throughput(), 3);
    }

    #[test]
    fn test_allocation_counter() {
        let metrics = Metrics::new();
        
        metrics.increment_allocations();
        metrics.increment_allocations();
        metrics.increment_allocations();
        
        let report = metrics.report();
        assert_eq!(report.allocations, 3);
    }

    #[test]
    fn test_fsync_counter() {
        let metrics = Metrics::new();
        
        metrics.increment_fsync();
        metrics.increment_fsync();
        
        let report = metrics.report();
        assert_eq!(report.fsync_count, 2);
    }

    #[test]
    fn test_fdatasync_counter() {
        let metrics = Metrics::new();
        
        metrics.increment_fdatasync();
        metrics.increment_fdatasync();
        metrics.increment_fdatasync();
        
        let report = metrics.report();
        assert_eq!(report.fdatasync_count, 3);
    }

    #[test]
    fn test_metrics_report() {
        let metrics = Metrics::new();
        
        // Record various metrics
        metrics.record_latency("put", Duration::from_micros(100));
        metrics.record_latency("get", Duration::from_micros(50));
        metrics.increment_throughput();
        metrics.increment_throughput();
        metrics.increment_allocations();
        metrics.increment_fsync();
        metrics.increment_fdatasync();
        
        // Get report
        let report = metrics.report();
        
        // Verify report contents
        assert_eq!(report.throughput, 2);
        assert_eq!(report.allocations, 1);
        assert_eq!(report.fsync_count, 1);
        assert_eq!(report.fdatasync_count, 1);
        assert!(report.operation_latencies.contains_key("put"));
        assert!(report.operation_latencies.contains_key("get"));
    }

    #[test]
    fn test_multiple_operations_latency() {
        let metrics = Metrics::new();
        
        // Record latencies for different operations
        metrics.record_latency("put", Duration::from_micros(100));
        metrics.record_latency("put", Duration::from_micros(200));
        metrics.record_latency("get", Duration::from_micros(50));
        metrics.record_latency("get", Duration::from_micros(75));
        metrics.record_latency("delete", Duration::from_micros(150));
        metrics.record_latency("scan", Duration::from_micros(500));
        
        // Verify all operations are tracked
        let report = metrics.report();
        assert_eq!(report.operation_latencies.len(), 4);
        assert!(report.operation_latencies.contains_key("put"));
        assert!(report.operation_latencies.contains_key("get"));
        assert!(report.operation_latencies.contains_key("delete"));
        assert!(report.operation_latencies.contains_key("scan"));
    }

    #[test]
    fn test_percentile_calculation() {
        let metrics = Metrics::new();
        
        // Record a series of latencies with known distribution
        for i in 1..=100 {
            metrics.record_latency("test", Duration::from_micros(i * 10));
        }
        
        let (p50, p95, p99) = metrics.get_percentiles("test");
        
        // p50 should be around 500 microseconds (50th value * 10)
        // p95 should be around 950 microseconds (95th value * 10)
        // p99 should be around 990 microseconds (99th value * 10)
        assert!(p50 >= 400.0 && p50 <= 600.0, "p50 = {}", p50);
        assert!(p95 >= 900.0 && p95 <= 1000.0, "p95 = {}", p95);
        assert!(p99 >= 980.0 && p99 <= 1010.0, "p99 = {}", p99);
    }

    #[test]
    fn test_get_percentiles_nonexistent_operation() {
        let metrics = Metrics::new();
        
        // Get percentiles for an operation that hasn't been recorded
        let (p50, p95, p99) = metrics.get_percentiles("nonexistent");
        
        // Should return zeros
        assert_eq!(p50, 0.0);
        assert_eq!(p95, 0.0);
        assert_eq!(p99, 0.0);
    }
}
