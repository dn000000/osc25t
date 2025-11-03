use clap::Parser;
use tracing_subscriber;
use uringkv::cli::Command;

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    // Initialize logging
    tracing_subscriber::fmt()
        .with_target(false)
        .with_thread_ids(true)
        .with_level(true)
        .init();

    // Parse CLI arguments
    let cmd = Command::parse();
    
    // Execute command
    uringkv::cli::execute_command(cmd).await?;

    Ok(())
}
