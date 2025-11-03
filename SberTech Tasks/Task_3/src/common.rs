use anyhow::{anyhow, Result};
use std::io::{IoSlice, IoSliceMut, Read, Write};
use std::os::fd::{AsRawFd, BorrowedFd, FromRawFd, IntoRawFd, RawFd};
use std::time::Duration;

use memfd::{Memfd, MemfdOptions, FileSeal};
use nix::fcntl::{fcntl, FcntlArg, FdFlag};
use nix::sys::socket::{recvmsg, sendmsg, ControlMessage, ControlMessageOwned, MsgFlags};
use nix::sys::socket::{sockopt, getsockopt};
use zeroize::Zeroize;

pub fn parse_ttl(s: &str) -> Result<Duration> {
    // Supports formats like: 10s, 10m, 1h
    let s = s.trim();
    if s.is_empty() { return Err(anyhow!("empty TTL")); }
    let (num, unit) = s.split_at(s.len() - 1);
    let n: u64 = num.parse()?;
    match unit {
        "s" => Ok(Duration::from_secs(n)),
        "m" => Ok(Duration::from_secs(n * 60)),
        "h" => Ok(Duration::from_secs(n * 3600)),
        _ => Err(anyhow!("unsupported TTL unit: {}", unit)),
    }
}

pub fn mlockall_current_future() -> Result<()> {
    let res = unsafe { libc::mlockall(libc::MCL_CURRENT | libc::MCL_FUTURE) };
    if res != 0 {
        let err = std::io::Error::last_os_error();
        Err(anyhow!("mlockall failed: {}", err))
    } else {
        Ok(())
    }
}

pub fn protect_process() -> Result<()> {
    // Disable core dumps/ptrace for non-root
    unsafe {
        // PR_SET_DUMPABLE = 4
        if libc::prctl(libc::PR_SET_DUMPABLE, 0, 0, 0, 0) != 0 {
            let err = std::io::Error::last_os_error();
            eprintln!("warn: prctl(PR_SET_DUMPABLE,0) failed: {}", err);
        }
        // PR_SET_NO_NEW_PRIVS = 38
        if libc::prctl(libc::PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0 {
            let err = std::io::Error::last_os_error();
            eprintln!("warn: prctl(PR_SET_NO_NEW_PRIVS,1) failed: {}", err);
        }
    }
    Ok(())
}

pub fn ensure_cloexec(fd: RawFd) -> Result<()> {
    let flags = FdFlag::FD_CLOEXEC;
    fcntl(fd, FcntlArg::F_SETFD(flags)).map_err(|e| anyhow!("F_SETFD(FD_CLOEXEC) failed: {}", e))?;
    Ok(())
}

pub fn create_sealed_memfd(name: &str, data: &[u8]) -> Result<Memfd> {
    let memfd = MemfdOptions::default()
        .allow_sealing(true)
        .close_on_exec(true)
        .create(name)?;
    let mut file = memfd.as_file();
    file.set_len(data.len() as u64)?;
    file.write_all(data)?;
    file.flush()?;
    // Apply seals: WRITE/SHRINK/GROW then SEAL
    memfd.add_seals(&[FileSeal::SealShrink, FileSeal::SealGrow, FileSeal::SealWrite])?;
    memfd.add_seal(FileSeal::SealSeal)?;
    ensure_cloexec(file.as_raw_fd())?;
    Ok(memfd)
}

pub fn read_all_from_fd(fd: RawFd) -> Result<Vec<u8>> {
    use std::io::Seek;
    let mut file = unsafe { std::fs::File::from_raw_fd(fd) };
    let mut buf = Vec::new();
    // Reset file position to beginning
    file.seek(std::io::SeekFrom::Start(0))?;
    file.read_to_end(&mut buf)?;
    // Avoid closing fd when file goes out of scope – we used from_raw_fd
    let _ = file.into_raw_fd();
    Ok(buf)
}

pub fn send_fd_with_payload(sock_fd: RawFd, fd_to_send: Option<RawFd>, payload: &[u8]) -> Result<()> {
    let iov = [IoSlice::new(payload)];
    let fds;
    let cmsg = match fd_to_send {
        Some(fd) => {
            fds = [fd];
            vec![ControlMessage::ScmRights(&fds)]
        },
        None => vec![],
    };
    sendmsg::<()>(sock_fd, &iov, &cmsg, MsgFlags::empty(), None)
        .map_err(|e| anyhow!("sendmsg failed: {}", e))?;
    Ok(())
}

pub fn recv_fd_with_payload(sock_fd: RawFd, bufsize: usize) -> Result<(Vec<u8>, Option<RawFd>)> {
    let mut buf = vec![0u8; bufsize];
    let mut iov = [IoSliceMut::new(&mut buf)];
    let mut cmsgspace = nix::cmsg_space!([RawFd; 1]);
    let msg = recvmsg::<()>(sock_fd, &mut iov, Some(&mut cmsgspace), MsgFlags::empty())
        .map_err(|e| anyhow!("recvmsg failed: {}", e))?;
    let mut fd_recv: Option<RawFd> = None;
    for cmsg in msg.cmsgs() {
        if let ControlMessageOwned::ScmRights(fds) = cmsg {
            if let Some(&fd) = fds.first() { fd_recv = Some(fd); }
        }
    }
    let bytes_read = msg.bytes;
    drop(iov);
    let payload = buf[..bytes_read].to_vec();
    Ok((payload, fd_recv))
}

pub struct PeerCred {
    pub pid: libc::pid_t,
    pub uid: libc::uid_t,
    pub gid: libc::gid_t,
}

pub fn get_peercred(fd: RawFd) -> Result<PeerCred> {
    let borrowed_fd = unsafe { BorrowedFd::borrow_raw(fd) };
    let ucred = getsockopt(&borrowed_fd, sockopt::PeerCredentials)
        .map_err(|e| anyhow!("getsockopt(SO_PEERCRED) failed: {}", e))?;
    Ok(PeerCred { pid: ucred.pid(), uid: ucred.uid(), gid: ucred.gid() })
}

pub fn mlock_buffer(buf: &mut [u8]) -> Result<()> {
    let res = unsafe { libc::mlock(buf.as_ptr() as *const libc::c_void, buf.len()) };
    if res != 0 {
        let err = std::io::Error::last_os_error();
        Err(anyhow!("mlock failed: {}", err))
    } else { Ok(()) }
}

pub fn zeroize_and_munlock(buf: &mut [u8]) {
    buf.zeroize();
    unsafe { let _ = libc::munlock(buf.as_ptr() as *const libc::c_void, buf.len()); }
}