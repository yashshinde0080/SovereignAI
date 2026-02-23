// src/providers/huggingface.rs
use crate::providers::provider_trait::*;
use crate::model_manager::model_metadata::{ModelMetadata, ModelSource};
use anyhow::Result;
use async_trait::async_trait;

pub struct HuggingFaceProvider {
    #[cfg(feature = "online")]
    client: reqwest::Client,
}

impl HuggingFaceProvider {
    pub fn new() -> Self {
        Self {
            #[cfg(feature = "online")]
            client: reqwest::Client::new(),
        }
    }
}

#[async_trait]
impl ModelProvider for HuggingFaceProvider {
    fn name(&self) -> &str {
        "huggingface"
    }

    async fn search(
        &self,
        query: &str,
    ) -> Result<Vec<ModelSearchResult>> {
        #[cfg(feature = "online")]
        {
            let url = format!(
                "https://huggingface.co/api/models\
                ?search={}&filter=gguf",
                query
            );
            let response: Vec<serde_json::Value> =
                self.client.get(&url)
                    .send()
                    .await?
                    .json()
                    .await?;

            let results: Vec<ModelSearchResult> = response.iter()
                .take(10)
                .map(|m| ModelSearchResult {
                    id: m["id"].as_str()
                        .unwrap_or("").to_string(),
                    name: m["modelId"].as_str()
                        .unwrap_or("").to_string(),
                    size_bytes: 0,
                    quantizations: vec![],
                    source: "huggingface".to_string(),
                })
                .collect();

            Ok(results)
        }

        #[cfg(not(feature = "online"))]
        {
            Err(anyhow::anyhow!(
                "Online features disabled. \
                Build with --features online"
            ))
        }
    }

    async fn get_metadata(
        &self,
        model_id: &str,
    ) -> Result<ModelMetadata> {
        Ok(ModelMetadata {
            id: uuid::Uuid::new_v4().to_string(),
            name: model_id.to_string(),
            family: model_id.split('/').last()
                .unwrap_or(model_id).to_string(),
            size_label: "unknown".to_string(),
            quantization: "unknown".to_string(),
            file_path: String::new(),
            file_size_bytes: 0,
            checksum_sha256: String::new(),
            source: ModelSource::HuggingFace {
                repo: model_id.to_string()
            },
            engines_supported: vec![
                "fullram".to_string(),
                "layerstream".to_string()
            ],
            downloaded: false,
            version: "latest".to_string(),
            created_at: chrono::Utc::now().to_rfc3339(),
        })
    }

    async fn download(
        &self,
        _model_id: &str,
        _dest_dir: &str,
    ) -> Result<String> {
        #[cfg(feature = "online")]
        {
            // In production: download from HF hub
            tracing::info!(
                "Downloading from HuggingFace: {}", _model_id
            );
            Err(anyhow::anyhow!(
                "Full HF download not yet implemented"
            ))
        }

        #[cfg(not(feature = "online"))]
        {
            Err(anyhow::anyhow!("Online features disabled"))
        }
    }

    fn supports_resume(&self) -> bool {
        true
    }
}