// src/main.rs
mod core;
mod engines;
mod model_manager;
mod providers;
mod database;
mod vectorstore;
mod security;
mod api;
mod cli;
mod plugins;
mod utils;

use clap::Parser;
use tracing_subscriber;

#[derive(Parser)]
#[command(name = "sovereign")]
#[command(about = "SovereignAI Edge - Portable Offline LLM Runtime")]
struct SovereignCli {
    #[command(subcommand)]
    command: cli::Commands,
}

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    tracing_subscriber::fmt()
        .with_env_filter(
            tracing_subscriber::EnvFilter::from_default_env()
                .add_directive("sovereign_ai=info".parse()?)
        )
        .init();

    let cli_args = SovereignCli::parse();

    let config = core::config::load_config("configs/default.toml")?;

    let runtime = core::runtime::Runtime::initialize(config).await?;

    cli::execute(cli_args.command, runtime).await?;

    Ok(())
}