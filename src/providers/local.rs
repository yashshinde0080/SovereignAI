// src/providers/local.rs
use crate::providers::provider_trait::*;
use crate::model_manager::model_metadata::{ModelMetadata, ModelSource};
use crate::model_manager::checksum;
use anyhow::Result;
use async_trait::async_trait;
use std::path::PathBuf;
use walkdir::WalkDir;

pub struct LocalProvider {
    scan_dirs: Vec<PathBuf>,
}

impl LocalProvider {
    pub fn new(dirs: Vec<String>) -> Self {
        Self {
            scan_dirs: dirs.into_iter()
                .map(PathBuf::from)
                .collect(),
        }
    }
}

#[async_trait]
impl ModelProvider for LocalProvider {
    fn name(&self) -> &str {
        "local"
    }

    async fn search(
        &self,
        query: &str,
    ) -> Result<Vec<ModelSearchResult>> {
        let mut results = Vec::new();

        for dir in &self.scan_dirs {
            for entry in WalkDir::new(dir)
                .into_iter()
                .filter_map(|e| e.ok())
            {
                let path = entry.path();
                let name = path.file_name()
                    .unwrap_or_default()
                    .to_string_lossy();

                if name.contains(query)
                    && name.ends_with(".gguf")
                {
                    let size = entry.metadata()
                        .map(|m| m.len())
                        .unwrap_or(0);

                    results.push(ModelSearchResult {
                        id: path.to_string_lossy().to_string(),
                        name: name.to_string(),
                        size_bytes: size,
                        quantizations: vec![],
                        source: "local".to_string(),
                    });
                }
            }
        }

        Ok(results)
    }

    async fn get_metadata(
        &self,
        model_path: &str,
    ) -> Result<ModelMetadata> {
        let path = PathBuf::from(model_path);
        let metadata = std::fs::metadata(&path)?;
        let name = path.file_stem()
            .unwrap_or_default()
            .to_string_lossy()
            .to_string();

        let hash = checksum::compute_sha256(&path)?;

        Ok(ModelMetadata {
            id: uuid::Uuid::new_v4().to_string(),
            name: name.clone(),
            family: name.clone(),
            size_label: "custom".to_string(),
            quantization: "unknown".to_string(),
            file_path: model_path.to_string(),
            file_size_bytes: metadata.len(),
            checksum_sha256: hash,
            source: ModelSource::Local,
            engines_supported: vec![
                "fullram".to_string(),
                "layerstream".to_string()
            ],
            downloaded: true,
            version: "local".to_string(),
            created_at: chrono::Utc::now().to_rfc3339(),
        })
    }

    async fn download(
        &self,
        _model_id: &str,
        _dest_dir: &str,
    ) -> Result<String> {
        Err(anyhow::anyhow!(
            "Local provider does not support download"
        ))
    }

    fn supports_resume(&self) -> bool {
        false
    }
}w