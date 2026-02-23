// src/model_manager/model_metadata.rs
use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ModelMetadata {
    pub id: String,
    pub name: String,
    pub family: String,
    pub size_label: String,
    pub quantization: String,
    pub file_path: String,
    pub file_size_bytes: u64,
    pub checksum_sha256: String,
    pub source: ModelSource,
    pub engines_supported: Vec<String>,
    pub downloaded: bool,
    pub version: String,
    pub created_at: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub enum ModelSource {
    HuggingFace { repo: String },
    Local,
    Bundle,
    Enterprise { endpoint: String },
}

impl ModelMetadata {
    pub fn parse_model_spec(spec: &str) -> (String, String, Option<String>) {
        // Parse "llama3:8b@v0.2" format
        let parts: Vec<&str> = spec.split('@').collect();
        let version = parts.get(1).map(|s| s.to_string());

        let name_parts: Vec<&str> = parts[0].split(':').collect();
        let family = name_parts[0].to_string();
        let size = name_parts.get(1)
            .unwrap_or(&"default")
            .to_string();

        (family, size, version)
    }
}