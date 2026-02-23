// src/providers/usb_bundle.rs
use crate::providers::provider_trait::*;
use crate::model_manager::model_metadata::{ModelMetadata, ModelSource};
use crate::model_manager::checksum;
use anyhow::Result;
use async_trait::async_trait;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, Serialize, Deserialize)]
pub struct ModelBundle {
    pub metadata: ModelMetadata,
    pub checksum: String,
    pub signature: Option<String>,
}

pub struct UsbBundleProvider;

impl UsbBundleProvider {
    pub fn new() -> Self {
        Self
    }

    /// Export model as portable bundle
    pub fn export_bundle(
        model: &ModelMetadata,
        output_path: &str,
    ) -> Result<PathBuf> {
        let bundle = ModelBundle {
            metadata: model.clone(),
            checksum: model.checksum_sha256.clone(),
            signature: None,
        };

        let bundle_dir = PathBuf::from(output_path);
        std::fs::create_dir_all(&bundle_dir)?;

        // Write metadata
        let meta_path = bundle_dir.join("manifest.json");
        let json = serde_json::to_string_pretty(&bundle)?;
        std::fs::write(&meta_path, json)?;

        // Copy model file
        let model_filename = PathBuf::from(&model.file_path)
            .file_name()
            .unwrap_or_default()
            .to_string_lossy()
            .to_string();
        let dest_model = bundle_dir.join(&model_filename);
        std::fs::copy(&model.file_path, &dest_model)?;

        tracing::info!(
            "Bundle exported to: {}",
            bundle_dir.display()
        );

        Ok(bundle_dir)
    }

    /// Import model from bundle
    pub fn import_bundle(
        bundle_path: &str,
        models_dir: &str,
    ) -> Result<ModelMetadata> {
        let bundle_dir = PathBuf::from(bundle_path);

        // Read manifest
        let manifest_path = bundle_dir.join("manifest.json");
        let manifest_json = std::fs::read_to_string(&manifest_path)?;
        let bundle: ModelBundle =
            serde_json::from_str(&manifest_json)?;

        // Find model file
        let model_files: Vec<PathBuf> = std::fs::read_dir(&bundle_dir)?
            .filter_map(|e| e.ok())
            .filter(|e| {
                e.path().extension()
                    .map(|ext| ext == "gguf")
                    .unwrap_or(false)
            })
            .map(|e| e.path())
            .collect();

        let model_file = model_files.first()
            .ok_or_else(|| anyhow::anyhow!(
                "No .gguf file found in bundle"
            ))?;

        // Verify checksum
        let actual_checksum = checksum::compute_sha256(model_file)?;
        if actual_checksum != bundle.checksum {
            return Err(anyhow::anyhow!(
                "Bundle checksum mismatch! \
                Expected: {}, Got: {}",
                bundle.checksum,
                actual_checksum
            ));
        }

        // Copy to models directory
        let dest_dir = PathBuf::from(models_dir)
            .join(&bundle.metadata.family);
        std::fs::create_dir_all(&dest_dir)?;

        let dest = dest_dir.join(
            model_file.file_name().unwrap()
        );
        std::fs::copy(model_file, &dest)?;

        let mut metadata = bundle.metadata;
        metadata.file_path = dest.to_string_lossy().to_string();
        metadata.downloaded = true;

        tracing::info!(
            "Bundle imported: {}", metadata.name
        );

        Ok(metadata)
    }
}

#[async_trait]
impl ModelProvider for UsbBundleProvider {
    fn name(&self) -> &str {
        "usb_bundle"
    }

    async fn search(
        &self,
        _query: &str,
    ) -> Result<Vec<ModelSearchResult>> {
        Ok(vec![])
    }

    async fn get_metadata(
        &self,
        bundle_path: &str,
    ) -> Result<ModelMetadata> {
        let manifest = PathBuf::from(bundle_path)
            .join("manifest.json");
        let json = std::fs::read_to_string(manifest)?;
        let bundle: ModelBundle = serde_json::from_str(&json)?;
        Ok(bundle.metadata)
    }

    async fn download(
        &self,
        _model_id: &str,
        _dest_dir: &str,
    ) -> Result<String> {
        Err(anyhow::anyhow!(
            "Use import_bundle() for USB bundles"
        ))
    }

    fn supports_resume(&self) -> bool {
        false
    }
}