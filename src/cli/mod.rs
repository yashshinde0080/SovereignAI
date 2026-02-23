// src/cli/mod.rs
pub mod run;
pub mod pull;
pub mod list;
pub mod remove;
pub mod benchmark;
pub mod system_info;
pub mod logs;
pub mod interactive;
pub mod display;

use crate::core::runtime::Runtime;
use anyhow::Result;
use clap::Subcommand;
use std::sync::Arc;

#[derive(Subcommand)]
pub enum Commands {
    /// Run a model with single prompt
    Run {
        /// Model spec (e.g., "llama3:8b")
        model: String,
        /// Execution mode: fullram, layerstream, auto
        #[arg(long, default_value = "auto")]
        mode: String,
        /// Enable interactive chat mode
        #[arg(long)]
        interactive: bool,
        /// Single prompt (non-interactive)
        #[arg(long)]
        prompt: Option<String>,
    },

    /// Start API + Web UI server
    Serve {
        #[arg(long, default_value = "3030")]
        port: u16,
        /// Open browser automatically
        #[arg(long)]
        open: bool,
    },

    /// Pull/download a model
    Pull {
        model: String,
        #[arg(long, default_value = "local")]
        source: String,
        /// Force re-download
        #[arg(long)]
        force: bool,
    },

    /// List installed models
    List {
        /// Show detailed info
        #[arg(long)]
        verbose: bool,
    },

    /// Remove a model
    Remove {
        model_id: String,
        /// Skip confirmation
        #[arg(long)]
        force: bool,
    },

    /// Run performance benchmark
    Benchmark {
        model: String,
        #[arg(long, default_value = "auto")]
        mode: String,
        /// Compare all modes
        #[arg(long)]
        compare: bool,
    },

    /// Show system information
    System {
        /// Run disk speed test
        #[arg(long)]
        benchmark_disk: bool,
    },

    /// View runtime logs
    Logs {
        /// Number of lines
        #[arg(long, default_value = "50")]
        lines: usize,
        /// Follow mode
        #[arg(long)]
        follow: bool,
        /// Filter by category
        #[arg(long)]
        filter: Option<String>,
    },

    /// Import model bundle from USB/disk
    Import { path: String },

    /// Export model as portable bundle
    Export {
        model_id: String,
        #[arg(long, default_value = "./export")]
        output: String,
    },

    /// Interactive chat session
    Chat {
        model: String,
        #[arg(long, default_value = "auto")]
        mode: String,
    },
}

pub async fn execute(
    command: Commands,
    runtime: Arc<Runtime>,
) -> Result<()> {
    match command {
        Commands::Run {
            model,
            mode,
            interactive,
            prompt,
        } => {
            if interactive {
                interactive::start_session(
                    runtime, &model, &mode,
                ).await
            } else if let Some(p) = prompt {
                run::execute_single(
                    runtime, &model, &mode, &p,
                ).await
            } else {
                run::execute_single(
                    runtime,
                    &model,
                    &mode,
                    "Hello! How are you?",
                ).await
            }
        }
        Commands::Serve { port, open } => {
            crate::api::server::start_server(runtime, port, open)
                .await
        }
        Commands::Pull {
            model,
            source,
            force,
        } => pull::execute(runtime, &model, &source, force).await,
        Commands::List { verbose } => {
            list::execute(runtime, verbose).await
        }
        Commands::Remove { model_id, force } => {
            remove::execute(runtime, &model_id, force).await
        }
        Commands::Benchmark {
            model,
            mode,
            compare,
        } => {
            benchmark::execute(
                runtime, &model, &mode, compare,
            ).await
        }
        Commands::System { benchmark_disk } => {
            system_info::execute(runtime, benchmark_disk).await
        }
        Commands::Logs {
            lines,
            follow,
            filter,
        } => {
            logs::execute(lines, follow, filter.as_deref()).await
        }
        Commands::Import { path } => {
            let meta = crate::providers::usb_bundle
                ::UsbBundleProvider::import_bundle(
                    &path,
                    &runtime.config.models.base_path,
                )?;
            runtime.registry.register_model(&meta).await?;
            display::print_success(&format!(
                "Model imported: {}", meta.name
            ));
            Ok(())
        }
        Commands::Export { model_id, output } => {
            let models = runtime.registry.list_models().await?;
            let model = models
                .iter()
                .find(|m| m.id == model_id || m.name == model_id)
                .ok_or_else(|| {
                    anyhow::anyhow!(
                        "Model not found: {}", model_id
                    )
                })?;

            crate::providers::usb_bundle
                ::UsbBundleProvider::export_bundle(
                    model, &output,
                )?;
            display::print_success(&format!(
                "Bundle exported to: {}", output
            ));
            Ok(())
        }
        Commands::Chat { model, mode } => {
            interactive::start_session(
                runtime, &model, &mode,
            ).await
        }
    }
}