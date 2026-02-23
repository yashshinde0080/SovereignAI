// src/cli/pull.rs
use crate::cli::display;
use crate::core::runtime::Runtime;
use crate::model_manager::checksum;
use crate::model_manager::model_metadata::{
    ModelMetadata, ModelSource,
};
use crate::providers::local::LocalProvider;
use crate::providers::provider_trait::ModelProvider;
use anyhow::Result;
use std::sync::Arc;

pub async fn execute(
    runtime: Arc<Runtime>,
    model_spec: &str,
    source: &str,
    force: bool,
) -> Result<()> {
    display::print_banner();
    display::print_header("Pull Model");

    match source {
        "local" => pull_local(runtime, model_spec, force).await,
        "huggingface" | "hf" => {
            pull_hf(runtime, model_spec).await
        }
        _ => {
            display::print_error(&format!(
                "Unknown source: {}", source
            ));
            Err(anyhow::anyhow!("Unknown source"))
        }
    }
}

async fn pull_local(
    runtime: Arc<Runtime>,
    path: &str,
    force: bool,
) -> Result<()> {
    // Stage 1: Verify file exists
    display::print_progress_stage(
        "Verifying file...",
        display::ProgressStatus::Active,
    );

    if !std::path::Path::new(path).exists() {
        display::print_progress_stage(
            "File not found",
            display::ProgressStatus::Failed,
        );
        return Err(anyhow::anyhow!(
            "File not found: {}", path
        ));
    }

    display::print_progress_stage(
        "File verified",
        display::ProgressStatus::Complete,
    );

    // Stage 2: Check if already registered
    if !force {
        let existing = runtime.registry.list_models().await?;
        for m in &existing {
            if m.file_path == path {
                display::print_warning(
                    "Model already registered. \
                    Use --force to re-register.",
                );
                return Ok(());
            }
        }
    }

    // Stage 3: Compute checksum
    display::print_progress_stage(
        "Computing checksum...",
        display::ProgressStatus::Active,
    );

    let hash = checksum::compute_sha256(path)?;

    display::print_progress_stage(
        &format!("Checksum: {}...{}", &hash[..8], &hash[56..]),
        display::ProgressStatus::Complete,
    );

    // Stage 4: Get metadata
    display::print_progress_stage(
        "Reading metadata...",
        display::ProgressStatus::Active,
    );

    let provider = LocalProvider::new(vec![".".to_string()]);
    let metadata = provider.get_metadata(path).await?;

    display::print_progress_stage(
        "Metadata read",
        display::ProgressStatus::Complete,
    );

    // Stage 5: Register
    display::print_progress_stage(
        "Registering model...",
        display::ProgressStatus::Active,
    );

    runtime.registry.register_model(&metadata).await?;

    display::print_progress_stage(
        "Registration complete",
        display::ProgressStatus::Complete,
    );

    println!();
    display::print_success(&format!(
        "Model registered: {}", metadata.name
    ));

    display::print_header("Model Details");
    display::print_key_value("Name:", &metadata.name);
    display::print_key_value("Path:", &metadata.file_path);
    display::print_key_value(
        "Size:",
        &display::human_readable_size(metadata.file_size_bytes),
    );
    display::print_key_value(
        "Checksum:",
        &metadata.checksum_sha256,
    );

    Ok(())
}

async fn pull_hf(
    runtime: Arc<Runtime>,
    model_spec: &str,
) -> Result<()> {
    #[cfg(feature = "online")]
    {
        display::print_info(&format!(
            "Searching HuggingFace: {}", model_spec
        ));

        let provider =
            crate::providers::huggingface::HuggingFaceProvider::new();
        let results = provider.search(model_spec).await?;

        if results.is_empty() {
            display::print_warning("No models found.");
            return Ok(());
        }

        display::print_header("Search Results");

        let rows: Vec<Vec<String>> = results
            .iter()
            .enumerate()
            .map(|(i, r)| {
                vec![
                    format!("[{}]", i),
                    r.name.clone(),
                    display::human_readable_size(r.size_bytes),
                ]
            })
            .collect();

        display::print_table(
            &["#", "Name", "Size"],
            &rows,
            &[5, 50, 10],
        );

        println!();
        display::print_info(
            "Download GGUF manually, then use: \
            sovereign pull <path> --source local",
        );

        Ok(())
    }

    #[cfg(not(feature = "online"))]
    {
        display::print_error(
            "Online features disabled. \
            Build with --features online",
        );
        Err(anyhow::anyhow!("Online features disabled"))
    }
}