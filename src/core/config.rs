// src/core/config.rs
use serde::Deserialize;
use std::path::Path;
use anyhow::Result;

#[derive(Debug, Clone, Deserialize)]
pub struct AppConfig {
    pub runtime: RuntimeConfig,
    pub models: ModelsConfig,
    pub inference: InferenceConfig,
    pub security: SecurityConfig,
    pub vectorstore: VectorStoreConfig,
    pub plugins: PluginsConfig,
}

#[derive(Debug, Clone, Deserialize)]
pub struct RuntimeConfig {
    pub name: String,
    pub version: String,
    pub bind_address: String,
    pub port: u16,
    pub max_ram_usage_percent: u8,
    pub log_level: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct ModelsConfig {
    pub base_path: String,
    pub cache_path: String,
    pub registry_db: String,
    pub max_storage_gb: u64,
    pub auto_cleanup: bool,
}

#[derive(Debug, Clone, Deserialize)]
pub struct InferenceConfig {
    pub default_mode: String,
    pub max_context_length: usize,
    pub default_temperature: f32,
    pub default_top_p: f32,
}

#[derive(Debug, Clone, Deserialize)]
pub struct SecurityConfig {
    pub encrypt_models: bool,
    pub encryption_algorithm: String,
    pub audit_logging: bool,
    pub allow_remote_access: bool,
}

#[derive(Debug, Clone, Deserialize)]
pub struct VectorStoreConfig {
    pub engine: String,
    pub index_path: String,
    pub embedding_model: String,
    pub chunk_size: usize,
    pub chunk_overlap: usize,
}

#[derive(Debug, Clone, Deserialize)]
pub struct PluginsConfig {
    pub enabled: bool,
    pub plugin_dir: String,
    pub sandbox: bool,
    pub max_memory_mb: u64,
}

pub fn load_config<P: AsRef<Path>>(path: P) -> Result<AppConfig> {
    let content = std::fs::read_to_string(path.as_ref())?;
    let config: AppConfig = toml::from_str(&content)?;
    Ok(config)
}

impl Default for AppConfig {
    fn default() -> Self {
        Self {
            runtime: RuntimeConfig {
                name: "SovereignAI Edge".into(),
                version: "0.1.0".into(),
                bind_address: "127.0.0.1".into(),
                port: 8080,
                max_ram_usage_percent: 75,
                log_level: "info".into(),
            },
            models: ModelsConfig {
                base_path: "./models/installed".into(),
                cache_path: "./models/.cache".into(),
                registry_db: "./models/registry.db".into(),
                max_storage_gb: 50,
                auto_cleanup: true,
            },
            inference: InferenceConfig {
                default_mode: "auto".into(),
                max_context_length: 4096,
                default_temperature: 0.7,
                default_top_p: 0.9,
            },
            security: SecurityConfig {
                encrypt_models: false,
                encryption_algorithm: "AES-256-GCM".into(),
                audit_logging: true,
                allow_remote_access: false,
            },
            vectorstore: VectorStoreConfig {
                engine: "hnsw".into(),
                index_path: "./vector_store".into(),
                embedding_model: "all-MiniLM-L6-v2".into(),
                chunk_size: 512,
                chunk_overlap: 50,
            },
            plugins: PluginsConfig {
                enabled: true,
                plugin_dir: "./plugins".into(),
                sandbox: true,
                max_memory_mb: 512,
            },
        }
    }
}