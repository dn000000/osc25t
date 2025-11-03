use std::collections::HashMap;
use std::fs;
use std::io::{Read, Write};
use std::os::fd::{AsRawFd, IntoRawFd, RawFd};
use std::os::unix::net::UnixListener;
use std::path::Path;
use std::os::unix::fs::PermissionsExt;
use std::sync::{Arc, Mutex};
use std::thread;
use std::time::{Duration, Instant};

use aes_gcm::aead::Aead;
use aes_gcm::{Aes256Gcm, Key, KeyInit, Nonce};
use anyhow::{anyhow, Result};
use clap::Parser;
use memfd::Memfd;
use nix::unistd::Uid;
use rand::rngs::OsRng;
use rand::RngCore;
use secrecy::{SecretVec, ExposeSecret};
use tracing::{error, info, warn};
use tracing_subscriber::EnvFilter;
use zeroize::Zeroize;

use secmem::common::*;

#[derive(Parser, Debug)]
#[command(name = "secmem-agent", about = "Secure in-RAM secret agent with AF_UNIX + SCM_RIGHTS")]
struct Args {
    #[arg(long, default_value = "/run/secmem.sock")]
    socket: String,

    #[arg(long, value_parser = clap::value_parser!(u32))]
    allow_uid: Vec<u32>,

    #[arg(long, value_parser = clap::value_parser!(u32))]
    allow_gid: Vec<u32>,
}

struct SecretRecord {
    name: String,
    storage: Memfd, // sealed memfd with ciphertext + tag + header
    expires_at: Instant,
}

struct AgentState {
    key: SecretVec<u8>, // AES-256 key
    cipher: Aes256Gcm,
    allowed_uids: Vec<u32>,
    allowed_gids: Vec<u32>,
    secrets: HashMap<String, SecretRecord>,
}

fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env())
        .with_target(false)
        .init();

    let args = Args::parse();

    // Process hardening + memory lock
    if let Err(e) = protect_process() { warn!("process hardening failed: {}", e); }
    if let Err(e) = mlockall_current_future() { warn!("mlockall failed: {}", e); }

    // Generate AES-256 key, lock and zeroize-on-drop
    let mut key_bytes_raw = vec![0u8; 32];
    mlock_buffer(&mut key_bytes_raw).ok();
    OsRng.fill_bytes(&mut key_bytes_raw);
    let key_bytes = SecretVec::<u8>::new(key_bytes_raw);
    let key = Key::<Aes256Gcm>::from_slice(key_bytes.expose_secret());
    let cipher = Aes256Gcm::new(key);

    let mut state = AgentState {
        key: key_bytes,
        cipher,
        allowed_uids: args.allow_uid.clone(),
        allowed_gids: args.allow_gid.clone(),
        secrets: HashMap::new(),
    };

    // Prepare socket
    let sock_path = Path::new(&args.socket);
    if sock_path.exists() {
        fs::remove_file(sock_path).ok();
    }
    // Only tmpfs paths recommended; rely on operator to place in /run or /dev/shm
    let listener = UnixListener::bind(sock_path)?;
    // set permissions: 0600
    let _ = fs::set_permissions(sock_path, fs::Permissions::from_mode(0o600));
    info!("secmem-agent listening on {}", args.socket);

    let shared = Arc::new(Mutex::new(state));
    let ttl_shared = Arc::clone(&shared);
    thread::spawn(move || ttl_worker(ttl_shared));

    for stream_res in listener.incoming() {
        match stream_res {
            Ok(stream) => {
                stream.set_nonblocking(false).ok();
                let fd = stream.as_raw_fd();
                let creds = match get_peercred(fd) {
                    Ok(c) => c,
                    Err(e) => { warn!("SO_PEERCRED failed: {}", e); continue; }
                };
                let uid = creds.uid as u32;
                let gid = creds.gid as u32;
                // access control
                {
                    let st = shared.lock().unwrap();
                    let allowed_uids = &st.allowed_uids;
                    let allowed_gids = &st.allowed_gids;
                    let mut permitted = true;
                    if !allowed_uids.is_empty() { permitted &= allowed_uids.contains(&uid); }
                    if !allowed_gids.is_empty() { permitted &= allowed_gids.contains(&gid); }
                    if !permitted {
                        warn!("deny client uid={} gid={} by policy", uid, gid);
                        continue;
                    }
                }

                // Transfer ownership of fd to the thread
                let fd = stream.into_raw_fd();
                let shared_cl = Arc::clone(&shared);
                thread::spawn(move || {
                    if let Err(e) = handle_client(shared_cl, fd, uid, gid) {
                        warn!("client error (uid={} gid={}): {}", uid, gid, e);
                    }
                    unsafe { libc::close(fd); }
                });
            }
            Err(e) => { error!("accept failed: {}", e); }
        }
    }

    Ok(())
}

fn ttl_worker(shared: Arc<Mutex<AgentState>>) {
    loop {
        thread::sleep(Duration::from_millis(500));
        let mut st = shared.lock().unwrap();
        let now = Instant::now();
        let mut expired: Vec<String> = Vec::new();
        for (k, v) in st.secrets.iter() {
            if v.expires_at <= now { expired.push(k.clone()); }
        }
        for k in expired {
            if let Some(mut rec) = st.secrets.remove(&k) {
                info!("TTL expired for key {}", k);
                // zeroize by truncating and closing memfd
                let fd = rec.storage.as_file().as_raw_fd();
                let _ = unsafe { libc::ftruncate(fd, 0) };
                drop(rec);
            }
        }
    }
}

fn handle_client(shared: Arc<Mutex<AgentState>>, fd: RawFd, uid: u32, gid: u32) -> Result<()> {
    // Expect a line payload like: "PUT name ttl_ms" or "GET name"
    let (payload, maybe_fd) = recv_fd_with_payload(fd, 4096)?;
    let line = String::from_utf8_lossy(&payload).trim().to_string();
    if line.is_empty() { return Err(anyhow!("empty request")); }
    let parts: Vec<&str> = line.split_whitespace().collect();
    match parts.as_slice() {
        ["PUT", name, ttl_ms] => {
            let ttl_ms: u64 = ttl_ms.parse()?;
            let put_fd = maybe_fd.ok_or_else(|| anyhow!("PUT requires memfd via SCM_RIGHTS"))?;
            handle_put(shared, fd, uid, gid, name, Duration::from_millis(ttl_ms), put_fd)
        }
        ["GET", name] => {
            handle_get(shared, fd, uid, gid, name)
        }
        _ => Err(anyhow!("unknown command: {}", line)),
    }
}

fn handle_put(shared: Arc<Mutex<AgentState>>, sock_fd: RawFd, uid: u32, gid: u32, name: &str, ttl: Duration, put_fd: RawFd) -> Result<()> {
    // Read plaintext from client's memfd securely
    let mut plaintext = read_all_from_fd(put_fd)?;
    mlock_buffer(&mut plaintext).ok();

    // Encrypt using AES-256-GCM with random nonce
    let mut nonce_bytes = [0u8; 12];
    OsRng.fill_bytes(&mut nonce_bytes);
    let nonce = Nonce::from_slice(&nonce_bytes);
    let cipher;
    {
        let st = shared.lock().unwrap();
        cipher = st.cipher.clone();
    }
    let ciphertext = cipher.encrypt(nonce, plaintext.as_ref()).map_err(|_| anyhow!("encryption failed"))?; // ciphertext || tag

    // Build header: magic(4) version(4) plain_len(8) nonce(12) cipher_len(8) [data]
    let mut blob = Vec::with_capacity(4 + 4 + 8 + 12 + 8 + ciphertext.len());
    blob.extend_from_slice(b"SMEM");
    blob.extend_from_slice(&1u32.to_be_bytes());
    blob.extend_from_slice(&(plaintext.len() as u64).to_be_bytes());
    blob.extend_from_slice(&nonce_bytes);
    blob.extend_from_slice(&(ciphertext.len() as u64).to_be_bytes());
    blob.extend_from_slice(&ciphertext);

    // Create sealed memfd and store
    let storage = create_sealed_memfd(&format!("secret:{}", name), &blob)?;
    // Zeroize plaintext ASAP
    zeroize_and_munlock(&mut plaintext);

    {
        let mut st = shared.lock().unwrap();
        let rec = SecretRecord { name: name.to_string(), storage, expires_at: Instant::now() + ttl };
        st.secrets.insert(name.to_string(), rec);
        info!("PUT by uid={} gid={} for key {} TTL {}ms", uid, gid, name, ttl.as_millis());
    }

    // Acknowledge
    send_fd_with_payload(sock_fd, None, b"OK\n")?;
    Ok(())
}

fn handle_get(shared: Arc<Mutex<AgentState>>, sock_fd: RawFd, uid: u32, gid: u32, name: &str) -> Result<()> {
    // Obtain fd without cloning Memfd
    let fd_opt = {
        let st = shared.lock().unwrap();
        st.secrets.get(name).map(|r| r.storage.as_file().as_raw_fd())
    };
    let fd = match fd_opt {
        Some(fd) => fd,
        None => { send_fd_with_payload(sock_fd, None, b"ERR no such key\n")?; return Ok(()); }
    };

    // Read blob from storage
    let blob = read_all_from_fd(fd)?;
    // Parse header
    if blob.len() < 4 + 4 + 8 + 12 + 8 { return Err(anyhow!("blob too small")); }
    if &blob[0..4] != b"SMEM" { return Err(anyhow!("bad magic")); }
    let plain_len = u64::from_be_bytes(blob[8..16].try_into().unwrap()) as usize;
    let nonce_bytes: [u8; 12] = blob[16..28].try_into().unwrap();
    let cipher_len = u64::from_be_bytes(blob[28..36].try_into().unwrap()) as usize;
    if 36 + cipher_len > blob.len() { return Err(anyhow!("bad lengths")); }
    let ciphertext = &blob[36..36+cipher_len];

    // Decrypt
    let nonce = Nonce::from_slice(&nonce_bytes);
    let cipher;
    {
        let st = shared.lock().unwrap();
        cipher = st.cipher.clone();
    }
    let mut plaintext = cipher.decrypt(nonce, ciphertext).map_err(|_| anyhow!("decryption failed"))?;
    if plaintext.len() != plain_len { return Err(anyhow!("length mismatch")); }
    mlock_buffer(&mut plaintext).ok();

    // Place into a new sealed memfd for client
    let out_memfd = create_sealed_memfd(&format!("secret_out:{}", name), &plaintext)?;
    // Zeroize plaintext
    zeroize_and_munlock(&mut plaintext);

    // Send memfd via SCM_RIGHTS
    let out_fd = out_memfd.as_file().as_raw_fd();
    send_fd_with_payload(sock_fd, Some(out_fd), b"OK\n")?;
    info!("GET by uid={} gid={} served key {}", uid, gid, name);
    Ok(())
}