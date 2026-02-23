// src/core/benchmark.rs
use crate::engines::traits::{InferenceEngine, InferenceRequest};
use anyhow::Result;
use serde::Serialize;
use std::time::Instant;

#[derive(Debug, Serialize)]
pub struct BenchmarkResult {
    pub model_name: String,
    pub mode: String,
    pub prompt_tokens: usize,
    pub generated_tokens: usize,
    pub total_time_ms: u128,
    pub tokens_per_second: f64,
    pub time_to_first_token_ms: u128,
    pub peak_memory_bytes: u64,
}

pub async fn run_benchmark(
    engine: &dyn InferenceEngine,
    model_name: &str,
    mode: &str,
) -> Result<BenchmarkResult> {
    let test_prompt = "Explain the concept of quantum entanglement \
        in simple terms.";

    let request = InferenceRequest {
        prompt: test_prompt.to_string(),
        max_tokens: 128,
        temperature: 0.7,
        top_p: 0.9,
        stop_sequences: vec![],
        stream: false,
    };

    let start = Instant::now();
    let response = engine.generate(&request).await?;
    let total_time = start.elapsed();

    let tps = if total_time.as_secs_f64() > 0.0 {
        response.tokens_generated as f64 / total_time.as_secs_f64()
    } else {
        0.0
    };

    Ok(BenchmarkResult {
        model_name: model_name.to_string(),
        mode: mode.to_string(),
        prompt_tokens: response.prompt_tokens,
        generated_tokens: response.tokens_generated,
        total_time_ms: total_time.as_millis(),
        tokens_per_second: tps,
        time_to_first_token_ms: response.time_to_first_token_ms,
        peak_memory_bytes: response.peak_memory_bytes,
    })
}