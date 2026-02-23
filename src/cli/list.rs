// src/cli/list.rs
use crate::cli::display;
use crate::core::runtime::Runtime;
use anyhow::Result;
use std::sync::Arc;

pub async fn execute(
    runtime: Arc<Runtime>,
    verbose: bool,
) -> Result<()> {
    let models = runtime.registry.list_models().await?;

    if models.is_empty() {
        display::print_header("Installed Models");
        println!();
        display::print_info("No models installed.");
        println!();
        println!(
            "  Use: {}sovereign pull /path/to/model.gguf \
            --source local{}",
            display::CYAN, display::RESET,
        );
        return Ok(());
    }

    display::print_header(&format!(
        "Installed Models ({})",
        models.len()
    ));

    if verbose {
        for model in &models {
            println!();
            display::print_key_value("ID:", &model.id);
            display::print_key_value("Name:", &model.name);
            display::print_key_value("Family:", &model.family);
            display::print_key_value(
                "Size:",
                &model.size_label,
            );
            display::print_key_value(
                "Quant:",
                &model.quantization,
            );
            display::print_key_value(
                "File:",
                &display::human_readable_size(
                    model.file_size_bytes
                ),
            );
            display::print_key_value("Path:", &model.file_path);
            display::print_key_value(
                "Version:",
                &model.version,
            );
            display::print_key_value(
                "Engines:",
                &model.engines_supported.join(", "),
            );
            println!(
                "  {}{}{}",
                display::DIM,
                "─".repeat(40),
                display::RESET,
            );
        }
    } else {
        let rows: Vec<Vec<String>> = models
            .iter()
            .map(|m| {
                vec![
                    m.name.clone(),
                    display::human_readable_size(
                        m.file_size_bytes
                    ),
                    m.quantization.clone(),
                    m.version.clone(),
                    m.id[..8.min(m.id.len())].to_string(),
                ]
            })
            .collect();

        display::print_table(
            &["Name", "Size", "Quant", "Version", "ID"],
            &rows,
            &[25, 10, 10, 10, 10],
        );
    }

    Ok(())
}