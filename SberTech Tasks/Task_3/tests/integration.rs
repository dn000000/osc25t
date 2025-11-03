use assert_cmd::prelude::*;
use predicates::str::contains;
use std::process::{Command, Stdio};
use std::thread;
use std::time::Duration;

#[test]
fn put_get_roundtrip() {
    let socket = "/dev/shm/secmem_test.sock";
    // Start agent
    let uid = nix::unistd::Uid::current().as_raw();
    let mut agent = Command::cargo_bin("secmem-agent").unwrap()
        .arg("--socket").arg(socket)
        .arg("--allow-uid").arg(uid.to_string())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .spawn()
        .expect("spawn agent");

    // Give it some time
    thread::sleep(Duration::from_millis(200));

    // Put
    Command::cargo_bin("secmemctl").unwrap()
        .arg("--socket").arg(socket)
        .arg("put").arg("db_password=supersecret")
        .arg("--ttl").arg("2s")
        .assert()
        .success();

    // Get
    Command::cargo_bin("secmemctl").unwrap()
        .arg("--socket").arg(socket)
        .arg("get").arg("db_password")
        .assert()
        .success()
        .stdout(contains("supersecret"));

    let _ = agent.kill();
}

#[test]
fn ttl_expiration_prevents_get() {
    let socket = "/dev/shm/secmem_test2.sock";
    let uid = nix::unistd::Uid::current().as_raw();
    let mut agent = Command::cargo_bin("secmem-agent").unwrap()
        .arg("--socket").arg(socket)
        .arg("--allow-uid").arg(uid.to_string())
        .stdout(Stdio::inherit())
        .stderr(Stdio::inherit())
        .spawn()
        .expect("spawn agent");

    thread::sleep(Duration::from_millis(200));

    // Put with short TTL
    Command::cargo_bin("secmemctl").unwrap()
        .arg("--socket").arg(socket)
        .arg("put").arg("short=one")
        .arg("--ttl").arg("1s")
        .assert()
        .success();

    thread::sleep(Duration::from_millis(1500));

    // Get should error
    Command::cargo_bin("secmemctl").unwrap()
        .arg("--socket").arg(socket)
        .arg("get").arg("short")
        .assert()
        .success()
        .stdout(contains("ERR no such key"));

    let _ = agent.kill();
}