// src/cli/remove.rs
use crate::cli::display;
use crate::core::runtime::Runtime;
use anyhow::Result;
use std::sync::Arc;

pub async fn execute(
    runtime: Arc<Runtime>,
    model_id: &str,
    force: bool,
) -> Result<()> {
    // Find model
    let models = runtime.registry.list_models().await?;
    let model = models
        .iter()
        .find(|m| m.id == model_id || m.name == model_id)
        .ok_or_else(|| {
            anyhow::anyhow!("Model not found: {}", model_id)
        })?;

    display::print_header("Remove Model");
    display::print_key_value("Name:", &model.name);
    display::print_key_value(
        "Size:",
        &display::human_readable_size(model.file_size_bytes),
    );
    display::print_key_value("Path:", &model.file_path);

    if !force {
        if !display::prompt_confirm(
            "Are you sure you want to remove this model?",
        ) {
            display::print_info("Cancelled.");
            return Ok(());
        }
    }

    runtime.registry.remove_model(&model.id).await?;
    display::print_success(&format!(
        "Model removed: {}", model.name
    ));

    Ok(())
}