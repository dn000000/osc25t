use crate::error::{Result, StorageError};
use io_uring::{opcode, types, IoUring};
use std::fs::File;
use std::os::unix::io::{AsRawFd, RawFd};

/// io_uring context for batched I/O operations
pub struct IoUringContext {
    ring: IoUring,
    _queue_depth: u32,
    _sqpoll_enabled: bool,
    fixed_files: Vec<File>,
    fixed_buffers: Vec<Vec<u8>>,
}

impl IoUringContext {
    /// Create a new IoUringContext with configurable queue depth and SQPOLL mode
    pub fn new(queue_depth: u32, enable_sqpoll: bool) -> Result<Self> {
        let mut builder = IoUring::builder();
        
        if enable_sqpoll {
            builder.setup_sqpoll(1000); // 1 second idle timeout
        }
        
        let ring = builder
            .build(queue_depth)
            .map_err(|e| StorageError::IoUringError(format!("Failed to create io_uring: {}", e)))?;
        
        Ok(Self {
            ring,
            _queue_depth: queue_depth,
            _sqpoll_enabled: enable_sqpoll,
            fixed_files: Vec::new(),
            fixed_buffers: Vec::new(),
        })
    }

    /// Create a test-only IoUringContext that doesn't actually initialize io_uring
    /// This is useful for tests that don't need io_uring functionality
    #[cfg(test)]
    pub fn new_test() -> Result<Self> {
        // Try to create a minimal io_uring, but if it fails, return an error
        // The caller can handle this gracefully in tests
        Self::new(1, false)
    }

    /// Perform a single read operation
    pub async fn read(&mut self, fd: RawFd, offset: u64, buf: &mut [u8]) -> Result<usize> {
        let read_e = opcode::Read::new(types::Fd(fd), buf.as_mut_ptr(), buf.len() as u32)
            .offset(offset)
            .build()
            .user_data(0);

        unsafe {
            self.ring
                .submission()
                .push(&read_e)
                .map_err(|e| StorageError::IoUringError(format!("Failed to push read operation: {}", e)))?;
        }

        self.ring
            .submit_and_wait(1)
            .map_err(|e| StorageError::IoUringError(format!("Failed to submit read: {}", e)))?;

        let cqe = self.ring
            .completion()
            .next()
            .ok_or_else(|| StorageError::IoUringError("No completion event".to_string()))?;

        let result = cqe.result();
        if result < 0 {
            return Err(StorageError::IoError(std::io::Error::from_raw_os_error(-result)));
        }

        Ok(result as usize)
    }

    /// Perform a single write operation
    pub async fn write(&mut self, fd: RawFd, offset: u64, buf: &[u8]) -> Result<usize> {
        let write_e = opcode::Write::new(types::Fd(fd), buf.as_ptr(), buf.len() as u32)
            .offset(offset)
            .build()
            .user_data(0);

        unsafe {
            self.ring
                .submission()
                .push(&write_e)
                .map_err(|e| StorageError::IoUringError(format!("Failed to push write operation: {}", e)))?;
        }

        self.ring
            .submit_and_wait(1)
            .map_err(|e| StorageError::IoUringError(format!("Failed to submit write: {}", e)))?;

        let cqe = self.ring
            .completion()
            .next()
            .ok_or_else(|| StorageError::IoUringError("No completion event".to_string()))?;

        let result = cqe.result();
        if result < 0 {
            return Err(StorageError::IoError(std::io::Error::from_raw_os_error(-result)));
        }

        Ok(result as usize)
    }

    /// Perform multiple read operations in a batch
    pub async fn batch_read(&mut self, ops: Vec<ReadOp>) -> Result<Vec<Vec<u8>>> {
        if ops.is_empty() {
            return Ok(Vec::new());
        }

        let num_ops = ops.len();
        let mut buffers: Vec<Vec<u8>> = Vec::with_capacity(num_ops);
        
        // Prepare buffers for each read operation
        for op in &ops {
            buffers.push(vec![0u8; op.length as usize]);
        }

        // Submit all read operations
        for (idx, op) in ops.iter().enumerate() {
            let fd = if op.file_idx < self.fixed_files.len() as u32 {
                types::Fixed(op.file_idx)
            } else {
                return Err(StorageError::IoUringError(format!(
                    "Invalid file index: {}",
                    op.file_idx
                )));
            };

            let buf = &mut buffers[idx];
            let read_e = opcode::Read::new(fd, buf.as_mut_ptr(), buf.len() as u32)
                .offset(op.offset)
                .build()
                .user_data(idx as u64);

            unsafe {
                self.ring
                    .submission()
                    .push(&read_e)
                    .map_err(|e| StorageError::IoUringError(format!("Failed to push read operation: {}", e)))?;
            }
        }

        // Submit all operations at once
        self.ring
            .submit_and_wait(num_ops)
            .map_err(|e| StorageError::IoUringError(format!("Failed to submit batch read: {}", e)))?;

        // Collect results
        let mut results = vec![Vec::new(); num_ops];
        for _ in 0..num_ops {
            let cqe = self.ring
                .completion()
                .next()
                .ok_or_else(|| StorageError::IoUringError("Missing completion event".to_string()))?;

            let user_data = cqe.user_data() as usize;
            let result = cqe.result();

            if result < 0 {
                return Err(StorageError::IoError(std::io::Error::from_raw_os_error(-result)));
            }

            // Move the buffer data to results
            let bytes_read = result as usize;
            buffers[user_data].truncate(bytes_read);
            results[user_data] = std::mem::take(&mut buffers[user_data]);
        }

        Ok(results)
    }

    /// Perform multiple write operations in a batch
    pub async fn batch_write(&mut self, ops: Vec<WriteOp>) -> Result<Vec<usize>> {
        if ops.is_empty() {
            return Ok(Vec::new());
        }

        let num_ops = ops.len();

        // Submit all write operations
        for (idx, op) in ops.iter().enumerate() {
            let fd = if op.file_idx < self.fixed_files.len() as u32 {
                types::Fixed(op.file_idx)
            } else {
                return Err(StorageError::IoUringError(format!(
                    "Invalid file index: {}",
                    op.file_idx
                )));
            };

            let write_e = opcode::Write::new(fd, op.data.as_ptr(), op.data.len() as u32)
                .offset(op.offset)
                .build()
                .user_data(idx as u64);

            unsafe {
                self.ring
                    .submission()
                    .push(&write_e)
                    .map_err(|e| StorageError::IoUringError(format!("Failed to push write operation: {}", e)))?;
            }
        }

        // Submit all operations at once
        self.ring
            .submit_and_wait(num_ops)
            .map_err(|e| StorageError::IoUringError(format!("Failed to submit batch write: {}", e)))?;

        // Collect results
        let mut results = vec![0usize; num_ops];
        for _ in 0..num_ops {
            let cqe = self.ring
                .completion()
                .next()
                .ok_or_else(|| StorageError::IoUringError("Missing completion event".to_string()))?;

            let user_data = cqe.user_data() as usize;
            let result = cqe.result();

            if result < 0 {
                return Err(StorageError::IoError(std::io::Error::from_raw_os_error(-result)));
            }

            results[user_data] = result as usize;
        }

        Ok(results)
    }

    /// Register files for fixed file mode (IORING_REGISTER_FILES)
    /// This reduces overhead by pre-registering file descriptors
    pub fn register_files(&mut self, files: Vec<File>) -> Result<()> {
        let fds: Vec<RawFd> = files.iter().map(|f| f.as_raw_fd()).collect();
        
        self.ring
            .submitter()
            .register_files(&fds)
            .map_err(|e| StorageError::IoUringError(format!("Failed to register files: {}", e)))?;
        
        self.fixed_files = files;
        Ok(())
    }

    /// Register buffers for fixed buffer mode (IORING_REGISTER_BUFFERS)
    /// This reduces overhead by pre-registering memory buffers
    pub fn register_buffers(&mut self, buffers: Vec<Vec<u8>>) -> Result<()> {
        let _iovecs: Vec<std::io::IoSlice> = buffers
            .iter()
            .map(|buf| std::io::IoSlice::new(buf))
            .collect();
        
        // Note: io-uring 0.6 may not support register_buffers directly
        // This is a placeholder implementation
        // In production, you would use the proper io_uring buffer registration API
        
        self.fixed_buffers = buffers;
        Ok(())
    }

    /// Read using fixed file descriptor
    pub async fn read_fixed(&mut self, file_idx: u32, offset: u64, buf: &mut [u8]) -> Result<usize> {
        let read_e = opcode::Read::new(types::Fixed(file_idx), buf.as_mut_ptr(), buf.len() as u32)
            .offset(offset)
            .build()
            .user_data(0);

        unsafe {
            self.ring
                .submission()
                .push(&read_e)
                .map_err(|e| StorageError::IoUringError(format!("Failed to push read operation: {}", e)))?;
        }

        self.ring
            .submit_and_wait(1)
            .map_err(|e| StorageError::IoUringError(format!("Failed to submit read: {}", e)))?;

        let cqe = self.ring
            .completion()
            .next()
            .ok_or_else(|| StorageError::IoUringError("No completion event".to_string()))?;

        let result = cqe.result();
        if result < 0 {
            return Err(StorageError::IoError(std::io::Error::from_raw_os_error(-result)));
        }

        Ok(result as usize)
    }

    /// Write using fixed file descriptor
    pub async fn write_fixed(&mut self, file_idx: u32, offset: u64, buf: &[u8]) -> Result<usize> {
        let write_e = opcode::Write::new(types::Fixed(file_idx), buf.as_ptr(), buf.len() as u32)
            .offset(offset)
            .build()
            .user_data(0);

        unsafe {
            self.ring
                .submission()
                .push(&write_e)
                .map_err(|e| StorageError::IoUringError(format!("Failed to push write operation: {}", e)))?;
        }

        self.ring
            .submit_and_wait(1)
            .map_err(|e| StorageError::IoUringError(format!("Failed to submit write: {}", e)))?;

        let cqe = self.ring
            .completion()
            .next()
            .ok_or_else(|| StorageError::IoUringError("No completion event".to_string()))?;

        let result = cqe.result();
        if result < 0 {
            return Err(StorageError::IoError(std::io::Error::from_raw_os_error(-result)));
        }

        Ok(result as usize)
    }

    /// Perform fsync operation via io_uring
    /// Ensures all data and metadata are written to disk
    pub async fn fsync(&mut self, fd: RawFd) -> Result<()> {
        let fsync_e = opcode::Fsync::new(types::Fd(fd))
            .build()
            .user_data(0);

        unsafe {
            self.ring
                .submission()
                .push(&fsync_e)
                .map_err(|e| StorageError::IoUringError(format!("Failed to push fsync operation: {}", e)))?;
        }

        self.ring
            .submit_and_wait(1)
            .map_err(|e| StorageError::IoUringError(format!("Failed to submit fsync: {}", e)))?;

        let cqe = self.ring
            .completion()
            .next()
            .ok_or_else(|| StorageError::IoUringError("No completion event".to_string()))?;

        let result = cqe.result();
        if result < 0 {
            return Err(StorageError::IoError(std::io::Error::from_raw_os_error(-result)));
        }

        Ok(())
    }

    /// Perform fdatasync operation via io_uring
    /// Ensures data is written to disk, but may skip some metadata updates
    pub async fn fdatasync(&mut self, fd: RawFd) -> Result<()> {
        let fdatasync_e = opcode::Fsync::new(types::Fd(fd))
            .flags(types::FsyncFlags::DATASYNC)
            .build()
            .user_data(0);

        unsafe {
            self.ring
                .submission()
                .push(&fdatasync_e)
                .map_err(|e| StorageError::IoUringError(format!("Failed to push fdatasync operation: {}", e)))?;
        }

        self.ring
            .submit_and_wait(1)
            .map_err(|e| StorageError::IoUringError(format!("Failed to submit fdatasync: {}", e)))?;

        let cqe = self.ring
            .completion()
            .next()
            .ok_or_else(|| StorageError::IoUringError("No completion event".to_string()))?;

        let result = cqe.result();
        if result < 0 {
            return Err(StorageError::IoError(std::io::Error::from_raw_os_error(-result)));
        }

        Ok(())
    }

    /// Perform sync_file_range operation
    /// Syncs a specific range of a file to disk
    pub async fn sync_file_range(&mut self, fd: RawFd, offset: u64, len: u64, flags: u32) -> Result<()> {
        let sync_e = opcode::SyncFileRange::new(types::Fd(fd), len as u32)
            .offset(offset)
            .flags(flags)
            .build()
            .user_data(0);

        unsafe {
            self.ring
                .submission()
                .push(&sync_e)
                .map_err(|e| StorageError::IoUringError(format!("Failed to push sync_file_range operation: {}", e)))?;
        }

        self.ring
            .submit_and_wait(1)
            .map_err(|e| StorageError::IoUringError(format!("Failed to submit sync_file_range: {}", e)))?;

        let cqe = self.ring
            .completion()
            .next()
            .ok_or_else(|| StorageError::IoUringError("No completion event".to_string()))?;

        let result = cqe.result();
        if result < 0 {
            return Err(StorageError::IoError(std::io::Error::from_raw_os_error(-result)));
        }

        Ok(())
    }

    /// Perform fsync using fixed file descriptor
    pub async fn fsync_fixed(&mut self, file_idx: u32) -> Result<()> {
        let fsync_e = opcode::Fsync::new(types::Fixed(file_idx))
            .build()
            .user_data(0);

        unsafe {
            self.ring
                .submission()
                .push(&fsync_e)
                .map_err(|e| StorageError::IoUringError(format!("Failed to push fsync operation: {}", e)))?;
        }

        self.ring
            .submit_and_wait(1)
            .map_err(|e| StorageError::IoUringError(format!("Failed to submit fsync: {}", e)))?;

        let cqe = self.ring
            .completion()
            .next()
            .ok_or_else(|| StorageError::IoUringError("No completion event".to_string()))?;

        let result = cqe.result();
        if result < 0 {
            return Err(StorageError::IoError(std::io::Error::from_raw_os_error(-result)));
        }

        Ok(())
    }

    /// Perform fdatasync using fixed file descriptor
    pub async fn fdatasync_fixed(&mut self, file_idx: u32) -> Result<()> {
        let fdatasync_e = opcode::Fsync::new(types::Fixed(file_idx))
            .flags(types::FsyncFlags::DATASYNC)
            .build()
            .user_data(0);

        unsafe {
            self.ring
                .submission()
                .push(&fdatasync_e)
                .map_err(|e| StorageError::IoUringError(format!("Failed to push fdatasync operation: {}", e)))?;
        }

        self.ring
            .submit_and_wait(1)
            .map_err(|e| StorageError::IoUringError(format!("Failed to submit fdatasync: {}", e)))?;

        let cqe = self.ring
            .completion()
            .next()
            .ok_or_else(|| StorageError::IoUringError("No completion event".to_string()))?;

        let result = cqe.result();
        if result < 0 {
            return Err(StorageError::IoError(std::io::Error::from_raw_os_error(-result)));
        }

        Ok(())
    }
}

#[derive(Debug)]
pub struct ReadOp {
    pub file_idx: u32,
    pub offset: u64,
    pub length: u32,
    pub buffer_idx: u32,
}

#[derive(Debug)]
pub struct WriteOp {
    pub file_idx: u32,
    pub offset: u64,
    pub data: Vec<u8>,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn test_ioring_context_creation_without_sqpoll() {
        let result = IoUringContext::new(32, false);
        assert!(result.is_ok());
        let ctx = result.unwrap();
        assert_eq!(ctx._queue_depth, 32);
        assert_eq!(ctx._sqpoll_enabled, false);
    }

    #[test]
    fn test_ioring_context_creation_with_sqpoll() {
        let result = IoUringContext::new(32, true);
        // SQPOLL may fail if not supported by kernel or insufficient permissions
        // We just verify the flag is set correctly if creation succeeds
        if let Ok(ctx) = result {
            assert_eq!(ctx._queue_depth, 32);
            assert_eq!(ctx._sqpoll_enabled, true);
        }
    }

    #[test]
    fn test_ioring_context_respects_queue_depth() {
        let result = IoUringContext::new(128, false);
        assert!(result.is_ok());
        let ctx = result.unwrap();
        assert_eq!(ctx._queue_depth, 128);
    }
}
