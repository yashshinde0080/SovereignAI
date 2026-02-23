// src/engines/traits.rs
use anyhow::Result;
use async_trait::async_trait;
use serde::{Deserialize, Serialize};

// We need async_trait since trait methods are async
// Add `async-trait = "0.1"` to Cargo.toml

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InferenceRequest {
    pub prompt: String,
    pub max_tokens: usize,
    pub temperature: f32,
    pub top_p: f32,
    pub stop_sequences: Vec<String>,
    pub stream: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct InferenceResponse {
    pub text: String,
    pub tokens_generated: usize,
    pub prompt_tokens: usize,
    pub time_to_first_token_ms: u128,
    pub total_time_ms: u128,
    pub peak_memory_bytes: u64,
    pub mode: String,
}

pub trait InferenceEngine: Send + Sync {
    fn generate(
        &self,
        request: &InferenceRequest,
    ) -> std::pin::Pin<Box<dyn std::future::Future<
        Output = Result<InferenceResponse>
    > + Send + '_>>;

    fn model_name(&self) -> &str;
    fn mode(&self) -> &str;
    fn is_loaded(&self) -> bool;
    fn unload(&self) -> Result<()>;
    fn memory_usage(&self) -> u64;
}