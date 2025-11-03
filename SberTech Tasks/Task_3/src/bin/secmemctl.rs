use std::io::{Read, Write};
use std::os::fd::{AsRawFd, RawFd};
use std::os::unix::net::UnixStream;
use std::path::PathBuf;
use std::time::Duration;

use anyhow::{anyhow, Result};
use clap::{Parser, Subcommand};
use memfd::Memfd;
use tracing::{info, warn};
use tracing_subscriber::EnvFilter;
use zeroize::Zeroize;

use secmem::common::*;

#[derive(Parser, Debug)]
#[command(name = "secmemctl", about = "CLI для secmem-agent: put/get секретов через memfd + SCM_RIGHTS")]
struct Args {
    #[arg(long, default_value = "/run/secmem.sock")]
    socket: String,

    #[command(subcommand)]
    cmd: Cmd,
}

#[derive(Subcommand, Debug)]
enum Cmd {
    /// Сохранить секрет: формат name=value, TTL в формате 10s/10m/1h
    Put { item: String, #[arg(long)] ttl: String },
    /// Получить секрет по имени, печать в stdout
    Get { name: String },
}

fn main() -> Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(EnvFilter::from_default_env())
        .with_target(false)
        .init();

    let args = Args::parse();
    match args.cmd {
        Cmd::Put { item, ttl } => put_cmd(&args.socket, &item, &ttl),
        Cmd::Get { name } => get_cmd(&args.socket, &name),
    }
}

fn put_cmd(socket: &str, item: &str, ttl: &str) -> Result<()> {
    let (name, value) = parse_item(item)?;
    let ttl_dur = parse_ttl(ttl)?;
    let ttl_ms = ttl_dur.as_millis() as u64;

    // Create memfd with plaintext sealed
    let plaintext = value.into_bytes();
    let memfd = create_sealed_memfd(&format!("put:{}", name), &plaintext)?;

    // Connect
    let stream = UnixStream::connect(socket)?;
    let fd = stream.as_raw_fd();

    // Send command line and memfd via SCM_RIGHTS
    let line = format!("PUT {} {}\n", name, ttl_ms);
    send_fd_with_payload(fd, Some(memfd.as_file().as_raw_fd()), line.as_bytes())?;

    // Read ACK
    let (payload, _) = recv_fd_with_payload(fd, 128)?;
    let s = String::from_utf8_lossy(&payload);
    if !s.starts_with("OK") { return Err(anyhow!("agent error: {}", s.trim())); }
    info!("PUT ok: {}", name);
    Ok(())
}

fn get_cmd(socket: &str, name: &str) -> Result<()> {
    let stream = UnixStream::connect(socket)?;
    let fd = stream.as_raw_fd();
    let line = format!("GET {}\n", name);
    send_fd_with_payload(fd, None, line.as_bytes())?;

    // Receive memfd
    let (payload, maybe_fd) = recv_fd_with_payload(fd, 128)?;
    let s = String::from_utf8_lossy(&payload);
    if !s.starts_with("OK") {
        println!("{}", s.trim());
        return Ok(());
    }
    let out_fd = maybe_fd.ok_or_else(|| anyhow!("agent did not send memfd"))?;

    // Read plaintext from memfd and print to stdout
    let buf = read_all_from_fd(out_fd)?;
    // Attempt mlock
    let mut buf_clone = buf.clone();
    mlock_buffer(&mut buf_clone).ok();
    let out = String::from_utf8(buf).unwrap_or_else(|_| "<binary>".to_string());
    println!("{}", out);
    // Zeroize clone
    zeroize_and_munlock(&mut buf_clone);
    Ok(())
}

fn parse_item(item: &str) -> Result<(String, String)> {
    let parts: Vec<&str> = item.splitn(2, '=').collect();
    if parts.len() != 2 { return Err(anyhow!("item must be name=value")); }
    Ok((parts[0].to_string(), parts[1].to_string()))
}