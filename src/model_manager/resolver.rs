// src/model_manager/resolver.rs
use crate::model_manager::model_metadata::{ModelMetadata, ModelSource};
use crate::model_manager::registry::ModelRegistry;
use crate::core::hardware_detector::HardwareProfile;
use anyhow::Result;
use std::sync::Arc;

pub struct ModelResolver {
    registry: Arc<ModelRegistry>,
}

impl ModelResolver {
    pub fn new(registry: Arc<ModelRegistry>) -> Self {
        Self { registry }
    }

    /// Resolve model spec to concrete metadata
    pub async fn resolve(
        &self,
        spec: &str,
        hardware: &HardwareProfile,
    ) -> Result<ModelMetadata> {
        let (family, size, version) =
            ModelMetadata::parse_model_spec(spec);

        tracing::info!(
            "Resolving model: family={}, size={}, version={:?}",
            family, size, version
        );

        // Step 1: Check local registry
        if let Some(model) = self.registry
            .find_model(&family, &size, version.as_deref())
            .await?
        {
            tracing::info!("Model found locally: {}", model.name);
            return Ok(model);
        }

        // Step 2: Model not found locally
        tracing::info!(
            "Model not found locally. \
            Use 'sovereign pull {}' to download.",
            spec
        );

        Err(anyhow::anyhow!(
            "Model '{}' not found. Available models: {:?}",
            spec,
            self.registry.list_models().await?
                .iter()
                .map(|m| &m.name)
                .collect::<Vec<_>>()
        ))
    }

    /// Select best quantization for hardware
    pub fn select_quant(
        &self,
        available_quants: &[String],
        hardware: &HardwareProfile,
    ) -> String {
        let ram_gb = hardware.available_ram_bytes as f64
            / (1024.0 * 1024.0 * 1024.0);

        let preferred = if ram_gb >= 32.0 {
            vec!["Q8_0", "Q6_K", "Q5_K_M"]
        } else if ram_gb >= 16.0 {
            vec!["Q5_K_M", "Q4_K_M", "Q4_K_S"]
        } else {
            vec!["Q4_K_M", "Q4_K_S", "Q3_K_S"]
        };

        for pref in preferred {
            if available_quants.iter()
                .any(|q| q.contains(pref))
            {
                return pref.to_string();
            }
        }

        available_quants.first()
            .cloned()
            .unwrap_or_else(|| "Q4_K_M".to_string())
    }
}