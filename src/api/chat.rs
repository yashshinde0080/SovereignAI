// src/api/chat.rs
use crate::core::runtime::Runtime;
use crate::engines::traits::InferenceRequest;
use axum::{
    extract::State,
    Json,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;

#[derive(Debug, Deserialize)]
pub struct ChatRequest {
    pub messages: Vec<ChatMessage>,
    #[serde(default = "default_max_tokens")]
    pub max_tokens: usize,
    #[serde(default = "default_temperature")]
    pub temperature: f32,
    #[serde(default = "default_top_p")]
    pub top_p: f32,
}

#[derive(Debug, Serialize, Deserialize)]
pub struct ChatMessage {
    pub role: String,
    pub content: String,
}

#[derive(Debug, Serialize)]
pub struct ChatResponse {
    pub id: String,
    pub choices: Vec<ChatChoice>,
    pub usage: UsageStats,
}

#[derive(Debug, Serialize)]
pub struct ChatChoice {
    pub index: usize,
    pub message: ChatMessage,
    pub finish_reason: String,
}

#[derive(Debug, Serialize)]
pub struct UsageStats {
    pub prompt_tokens: usize,
    pub completion_tokens: usize,
    pub total_tokens: usize,
}

fn default_max_tokens() -> usize { 256 }
fn default_temperature() -> f32 { 0.7 }
fn default_top_p() -> f32 { 0.9 }

pub async fn chat_completion(
    State(runtime): State<Arc<Runtime>>,
    Json(request): Json<ChatRequest>,
) -> Result<Json<ChatResponse>, axum::http::StatusCode> {
    // Build prompt from messages
    let prompt = request.messages.iter()
        .map(|m| format!("{}: {}", m.role, m.content))
        .collect::<Vec<_>>()
        .join("\n");

    let inference_req = InferenceRequest {
        prompt,
        max_tokens: request.max_tokens,
        temperature: request.temperature,
        top_p: request.top_p,
        stop_sequences: vec![],
        stream: false,
    };

    match runtime.inference(inference_req).await {
        Ok(response) => {
            Ok(Json(ChatResponse {
                id: uuid::Uuid::new_v4().to_string(),
                choices: vec![ChatChoice {
                    index: 0,
                    message: ChatMessage {
                        role: "assistant".to_string(),
                        content: response.text,
                    },
                    finish_reason: "stop".to_string(),
                }],
                usage: UsageStats {
                    prompt_tokens: response.prompt_tokens,
                    completion_tokens: response.tokens_generated,
                    total_tokens: response.prompt_tokens
                        + response.tokens_generated,
                },
            }))
        }
        Err(e) => {
            tracing::error!("Inference error: {}", e);
            Err(axum::http::StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}