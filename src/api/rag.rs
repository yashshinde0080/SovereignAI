// src/api/rag.rs — Extended with stats endpoint
use crate::core::runtime::Runtime;
use crate::vectorstore::store::Document;
use axum::{
    extract::State,
    Json,
};
use serde::{Deserialize, Serialize};
use std::sync::Arc;

#[derive(Debug, Deserialize)]
pub struct IngestRequest {
    pub id: String,
    pub content: String,
    pub metadata: Option<
        std::collections::HashMap<String, String>
    >,
}

#[derive(Debug, Serialize)]
pub struct IngestResponse {
    pub document_id: String,
    pub chunks_created: usize,
}

#[derive(Debug, Deserialize)]
pub struct RagQueryRequest {
    pub query: String,
    #[serde(default = "default_top_k")]
    pub top_k: usize,
    #[serde(default = "default_max_context")]
    pub max_context_tokens: usize,
}

fn default_top_k() -> usize { 5 }
fn default_max_context() -> usize { 2048 }

#[derive(Debug, Serialize)]
pub struct RagQueryResponse {
    pub answer: String,
    pub sources: Vec<SourceInfo>,
    pub context_tokens: usize,
}

#[derive(Debug, Serialize)]
pub struct SourceInfo {
    pub document_id: String,
    pub content_preview: String,
    pub score: f32,
}

#[derive(Debug, Serialize)]
pub struct RagStatsResponse {
    pub total_chunks: usize,
    pub index_ready: bool,
}

pub async fn ingest_document(
    State(runtime): State<Arc<Runtime>>,
    Json(request): Json<IngestRequest>,
) -> Result<Json<IngestResponse>, axum::http::StatusCode> {
    let document = Document {
        id: request.id.clone(),
        content: request.content,
        metadata: request.metadata.unwrap_or_default(),
    };

    match runtime.vector_store.ingest(&document) {
        Ok(chunks) => Ok(Json(IngestResponse {
            document_id: request.id,
            chunks_created: chunks,
        })),
        Err(e) => {
            tracing::error!("Ingest error: {}", e);
            Err(axum::http::StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}

pub async fn query_rag(
    State(runtime): State<Arc<Runtime>>,
    Json(request): Json<RagQueryRequest>,
) -> Result<Json<RagQueryResponse>, axum::http::StatusCode> {
    let context = runtime.vector_store.build_context(
        &request.query,
        request.max_context_tokens,
        request.top_k,
    );

    let sources: Vec<SourceInfo> = runtime
        .vector_store
        .search(&request.query, request.top_k)
        .into_iter()
        .map(|r| SourceInfo {
            document_id: r.chunk.document_id,
            content_preview: r.chunk.content
                .chars()
                .take(200)
                .collect(),
            score: r.score,
        })
        .collect();

    let context_tokens =
        context.split_whitespace().count();

    let rag_prompt = format!(
        "Based on the following context, \
        answer the question.\n\n\
        Context:\n{}\n\n\
        Question: {}\n\nAnswer:",
        context, request.query
    );

    let req = crate::engines::traits::InferenceRequest {
        prompt: rag_prompt,
        max_tokens: 512,
        temperature: 0.3,
        top_p: 0.9,
        stop_sequences: vec![],
        stream: false,
    };

    match runtime.inference(req).await {
        Ok(response) => Ok(Json(RagQueryResponse {
            answer: response.text,
            sources,
            context_tokens,
        })),
        Err(e) => {
            tracing::error!("RAG query error: {}", e);
            Err(axum::http::StatusCode::INTERNAL_SERVER_ERROR)
        }
    }
}

pub async fn rag_stats(
    State(runtime): State<Arc<Runtime>>,
) -> Json<RagStatsResponse> {
    Json(RagStatsResponse {
        total_chunks: runtime.vector_store.chunk_count(),
        index_ready: runtime.vector_store.chunk_count() > 0,
    })
}