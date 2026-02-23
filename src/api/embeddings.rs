// src/api/embeddings.rs
use crate::core::runtime::Runtime;
use axum::{
    extract::State,
    Json,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;

#[derive(Debug, Deserialize)]
pub struct EmbeddingRequest {
    pub input: String,
    pub model: Option<String>,
}

#[derive(Debug, Serialize)]
pub struct EmbeddingResponse {
    pub data: Vec<EmbeddingData>,
    pub model: String,
}

#[derive(Debug, Serialize)]
pub struct EmbeddingData {
    pub index: usize,
    pub embedding: Vec<f32>,
}

pub async fn create_embedding(
    State(runtime): State<Arc<Runtime>>,
    Json(request): Json<EmbeddingRequest>,
) -> Json<EmbeddingResponse> {
    // Use vector store's embedding function
    let results = runtime.vector_store.search(
        &request.input, 0
    );

    // Generate embedding for the input
    // In production: use dedicated embedding model
    let mut embedding = vec![0.0f32; 384];
    for (i, byte) in request.input.bytes().enumerate() {
        embedding[i % 384] += byte as f32 / 255.0;
    }

    let norm: f32 = embedding.iter()
        .map(|x| x * x)
        .sum::<f32>()
        .sqrt();

    if norm > 0.0 {
        for x in &mut embedding {
            *x /= norm;
        }
    }

    Json(EmbeddingResponse {
        data: vec![EmbeddingData {
            index: 0,
            embedding,
        }],
        model: request.model
            .unwrap_or_else(|| "default".to_string()),
    })
}