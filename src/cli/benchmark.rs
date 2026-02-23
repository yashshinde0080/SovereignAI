// src/cli/benchmark.rs
use crate::cli::display;
use crate::core::hardware_detector::ExecutionMode;
use crate::core::runtime::Runtime;
use crate::engines::traits::InferenceRequest;
use crate::model_manager::resolver::ModelResolver;
use anyhow::Result;
use std::sync::Arc;
use std::time::Instant;

pub async fn execute(
    runtime: Arc<Runtime>,
    model_spec: &str,
    mode_str: &str,
    compare: bool,
) -> Result<()> {
    display::print_banner();

    let resolver = ModelResolver::new(runtime.registry.clone());
    let model = resolver
        .resolve(model_spec, &runtime.hardware)
        .await?;

    if compare {
        run_comparison(runtime, &model.name, model_spec).await
    } else {
        run_single(runtime, model_spec, mode_str).await
    }
}

async fn run_single(
    runtime: Arc<Runtime>,
    model_spec: &str,
    mode_str: &str,
) -> Result<()> {
    let resolver = ModelResolver::new(runtime.registry.clone());
    let model = resolver
        .resolve(model_spec, &runtime.hardware)
        .await?;

    let mode: ExecutionMode = mode_str.parse()?;

    display::print_header("Benchmark");
    display::print_key_value("Model:", &model.name);
    display::print_key_value("Mode:", &mode.to_string());
    display::print_info("Loading model...");

    runtime.load_model(model.clone(), mode)?;

    display::print_info("Running benchmark...");
    println!();

    let test_prompts = vec![
        "Explain quantum computing in simple terms.",
        "Write a function to sort a list in Python.",
        "What is the capital of France and why is it important?",
    ];

    let mut total_tokens = 0usize;
    let mut total_time_ms = 0u128;
    let mut total_ttft_ms = 0u128;
    let mut peak_memory = 0u64;

    for (i, prompt) in test_prompts.iter().enumerate() {
        let request = InferenceRequest {
            prompt: prompt.to_string(),
            max_tokens: 128,
            temperature: 0.0,
            top_p: 1.0,
            stop_sequences: vec![],
            stream: false,
        };

        let response = runtime.inference(request).await?;

        total_tokens += response.tokens_generated;
        total_time_ms += response.total_time_ms;
        total_ttft_ms += response.time_to_first_token_ms;
        peak_memory = peak_memory.max(response.peak_memory_bytes);

        println!(
            "  {}Test {}: {} tokens in {}ms{} ({:.1} tok/s)",
            display::DIM,
            i + 1,
            response.tokens_generated,
            response.total_time_ms,
            display::RESET,
            if response.total_time_ms > 0 {
                response.tokens_generated as f64
                    / (response.total_time_ms as f64 / 1000.0)
            } else {
                0.0
            },
        );
    }

    let avg_tps = if total_time_ms > 0 {
        total_tokens as f64
            / (total_time_ms as f64 / 1000.0)
    } else {
        0.0
    };
    let avg_ttft = total_ttft_ms / test_prompts.len() as u128;

    display::print_header("Results");
    display::print_metric(
        "Avg Tokens/sec:",
        &format!("{:.1}", avg_tps),
        "tok/s",
    );
    display::print_metric(
        "Avg TTFT:",
        &avg_ttft.to_string(),
        "ms",
    );
    display::print_metric(
        "Total tokens:",
        &total_tokens.to_string(),
        "tokens",
    );
    display::print_metric(
        "Total time:",
        &total_time_ms.to_string(),
        "ms",
    );
    display::print_metric(
        "Peak RAM:",
        &display::human_readable_size(peak_memory),
        "",
    );

    Ok(())
}

async fn run_comparison(
    runtime: Arc<Runtime>,
    model_name: &str,
    model_spec: &str,
) -> Result<()> {
    display::print_header("Mode Comparison Benchmark");
    display::print_key_value("Model:", model_name);
    println!();

    let modes = vec![
        ("fullram", ExecutionMode::FullRam),
        ("layerstream", ExecutionMode::LayerStream),
    ];

    let mut results: Vec<(String, f64, u128, u64)> = Vec::new();

    for (mode_name, mode) in &modes {
        display::print_info(&format!(
            "Testing {} mode...", mode_name
        ));

        let resolver = ModelResolver::new(
            runtime.registry.clone()
        );
        let model = resolver
            .resolve(model_spec, &runtime.hardware)
            .await?;

        match runtime.load_model(model, mode.clone()) {
            Ok(_) => {
                let request = InferenceRequest {
                    prompt: "Explain the theory of relativity."
                        .to_string(),
                    max_tokens: 128,
                    temperature: 0.0,
                    top_p: 1.0,
                    stop_sequences: vec![],
                    stream: false,
                };

                match runtime.inference(request).await {
                    Ok(response) => {
                        let tps = if response.total_time_ms > 0 {
                            response.tokens_generated as f64
                                / (response.total_time_ms as f64
                                    / 1000.0)
                        } else {
                            0.0
                        };

                        results.push((
                            mode_name.to_string(),
                            tps,
                            response.time_to_first_token_ms,
                            response.peak_memory_bytes,
                        ));
                    }
                    Err(e) => {
                        display::print_warning(&format!(
                            "{} failed: {}",
                            mode_name, e
                        ));
                    }
                }

                runtime.unload_model();
            }
            Err(e) => {
                display::print_warning(&format!(
                    "Cannot load in {} mode: {}",
                    mode_name, e
                ));
            }
        }
    }

    if results.len() >= 2 {
        let metrics: Vec<(String, String, String)> = vec![
            (
                "Tokens/sec".to_string(),
                format!("{:.1}", results[0].1),
                format!("{:.1}", results[1].1),
            ),
            (
                "First Token".to_string(),
                format!("{}ms", results[0].2),
                format!("{}ms", results[1].2),
            ),
            (
                "Peak RAM".to_string(),
                display::human_readable_size(results[0].3),
                display::human_readable_size(results[1].3),
            ),
        ];

        display::print_comparison_table(
            &results[0].0,
            &results[1].0,
            &metrics,
        );
    }

    Ok(())
}