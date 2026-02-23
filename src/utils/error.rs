// src/utils/error.rs
use thiserror::Error;

#[derive(Debug, Error)]
pub enum SovereignError {
    #[error("Model not found: {0}")]
    ModelNotFound(String),

    #[error("Insufficient memory: need {needed} bytes, have {available}")]
    InsufficientMemory { needed: u64, available: u64 },

    #[error("Inference error: {0}")]
    InferenceError(String),

    #[error("Storage error: {0}")]
    StorageError(String),

    #[error("Security error: {0}")]
    SecurityError(String),

    #[error("Configuration error: {0}")]
    ConfigError(String),

    #[error("Plugin error: {0}")]
    PluginError(String),
}