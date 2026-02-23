// src/providers/provider_trait.rs
use crate::model_manager::model_metadata::ModelMetadata;
use anyhow::Result;
use async_trait::async_trait;

#[async_trait]
pub trait ModelProvider: Send + Sync {
    fn name(&self) -> &str;

    async fn search(
        &self,
        query: &str,
    ) -> Result<Vec<ModelSearchResult>>;

    async fn get_metadata(
        &self,
        model_id: &str,
    ) -> Result<ModelMetadata>;

    async fn download(
        &self,
        model_id: &str,
        dest_dir: &str,
    ) -> Result<String>;

    fn supports_resume(&self) -> bool;
}

#[derive(Debug, Clone, serde::Serialize)]
pub struct ModelSearchResult {
    pub id: String,
    pub name: String,
    pub size_bytes: u64,
    pub quantizations: Vec<String>,
    pub source: String,
}