// src/api/routes.rs
use crate::api::{chat, embeddings, rag, system, websocket};
use crate::core::runtime::Runtime;
use axum::{
    routing::{get, post},
    Router,
};
use std::sync::Arc;

pub fn create_routes() -> Router<Arc<Runtime>> {
    Router::new()
        // Chat
        .route("/v1/chat", post(chat::chat_completion))
        // Embeddings
        .route(
            "/v1/embeddings",
            post(embeddings::create_embedding),
        )
        // RAG
        .route("/v1/rag/ingest", post(rag::ingest_document))
        .route("/v1/rag/query", post(rag::query_rag))
        .route("/v1/rag/stats", get(rag::rag_stats))
        // Models
        .route("/v1/models", get(system::list_models))
        .route(
            "/v1/models/active",
            get(system::active_model),
        )
        .route("/v1/models/load", post(system::load_model))
        .route(
            "/v1/models/unload",
            post(system::unload_model),
        )
        // System
        .route("/v1/system/status", get(system::system_status))
        .route(
            "/v1/system/hardware",
            get(system::hardware_info),
        )
        .route(
            "/v1/system/memory",
            get(system::memory_status),
        )
        .route(
            "/v1/system/benchmark",
            post(system::run_benchmark),
        )
        // WebSocket for streaming
        .route("/v1/ws", get(websocket::ws_handler))
}