// src/cli/run.rs
use crate::cli::display;
use crate::core::hardware_detector::ExecutionMode;
use crate::core::runtime::Runtime;
use crate::engines::traits::InferenceRequest;
use crate::model_manager::resolver::ModelResolver;
use anyhow::Result;
use std::sync::Arc;

pub async fn execute_single(
    runtime: Arc<Runtime>,
    model_spec: &str,
    mode_str: &str,
    prompt: &str,
) -> Result<()> {
    display::print_banner();

    let resolver = ModelResolver::new(runtime.registry.clone());

    display::print_info(&format!(
        "Resolving model: {}", model_spec
    ));

    let model = resolver
        .resolve(model_spec, &runtime.hardware)
        .await?;

    let mode: ExecutionMode = mode_str.parse()?;

    let resolved_mode = match &mode {
        ExecutionMode::Auto => runtime.hardware.recommend_mode(
            model.file_size_bytes,
            runtime.config.runtime.max_ram_usage_percent,
        ),
        other => other.clone(),
    };

    display::print_header("Loading Model");
    display::print_key_value("Model:", &model.name);
    display::print_key_value("Quantization:", &model.quantization);
    display::print_key_value(
        "Size:",
        &display::human_readable_size(model.file_size_bytes),
    );
    display::print_key_value("Mode:", &resolved_mode.to_string());

    runtime.load_model(model.clone(), mode)?;

    display::print_success("Model loaded");
    println!();

    display::print_status_bar(
        &model.name,
        &resolved_mode.to_string(),
        runtime.memory_tracker.current_usage() / (1024 * 1024),
        None,
    );

    let request = InferenceRequest {
        prompt: prompt.to_string(),
        max_tokens: 256,
        temperature: 0.7,
        top_p: 0.9,
        stop_sequences: vec![],
        stream: false,
    };

    display::print_info("Generating response...");
    println!();

    let response = runtime.inference(request).await?;

    let tps = if response.total_time_ms > 0 {
        response.tokens_generated as f64
            / (response.total_time_ms as f64 / 1000.0)
    } else {
        0.0
    };

    // Show response
    println!(
        "{}{}Assistant:{} {}",
        display::BOLD,
        display::GREEN,
        display::RESET,
        response.text
    );
    println!();

    // Show metrics
    display::print_header("Performance");
    display::print_metric(
        "Tokens generated:",
        &response.tokens_generated.to_string(),
        "tokens",
    );
    display::print_metric(
        "Total time:",
        &response.total_time_ms.to_string(),
        "ms",
    );
    display::print_metric(
        "First token:",
        &response.time_to_first_token_ms.to_string(),
        "ms",
    );
    display::print_metric(
        "Speed:",
        &format!("{:.1}", tps),
        "tokens/sec",
    );
    display::print_metric(
        "Peak RAM:",
        &display::human_readable_size(response.peak_memory_bytes),
        "",
    );
    display::print_metric("Mode:", &response.mode, "");

    Ok(())
}