// src/engines/fullram/loader.rs
use crate::engines::shared::tensor::Tensor;
use crate::engines::shared::transformer::{
    ModelConfig, TransformerLayerWeights
};
use anyhow::Result;
use std::path::Path;

/// Loads entire model into RAM
pub struct FullModelLoader;

impl FullModelLoader {
    /// Load GGUF model file into memory
    /// Returns all layer weights and model config
    pub fn load<P: AsRef<Path>>(
        path: P,
    ) -> Result<(ModelConfig, Vec<TransformerLayerWeights>, Tensor, Tensor)> {
        let path = path.as_ref();
        tracing::info!("Loading model from: {}", path.display());

        let file_size = std::fs::metadata(path)?.len();
        tracing::info!(
            "Model file size: {} MB",
            file_size / (1024 * 1024)
        );

        // In production: parse GGUF header, extract tensors
        // For now: create placeholder config
        let config = ModelConfig::llama3_8b();

        let mut layers = Vec::new();
        for i in 0..config.num_layers {
            let layer = Self::create_placeholder_layer(i, &config);
            layers.push(layer);
        }

        // Embedding and output projection
        let embedding = Tensor::zeros(
            &[config.vocab_size, config.hidden_dim]
        );
        let output_proj = Tensor::zeros(
            &[config.hidden_dim, config.vocab_size]
        );

        tracing::info!(
            "Model loaded: {} layers, {} params (placeholder)",
            config.num_layers,
            config.vocab_size * config.hidden_dim
        );

        Ok((config, layers, embedding, output_proj))
    }

    fn create_placeholder_layer(
        layer_id: usize,
        config: &ModelConfig,
    ) -> TransformerLayerWeights {
        let h = config.hidden_dim;
        let inter = config.intermediate_dim;
        let kv_dim = config.num_kv_heads * config.head_dim;

        TransformerLayerWeights {
            layer_id,
            attention_norm: Tensor::zeros(&[h]),
            wq: Tensor::zeros(&[h, h]),
            wk: Tensor::zeros(&[h, kv_dim]),
            wv: Tensor::zeros(&[h, kv_dim]),
            wo: Tensor::zeros(&[h, h]),
            ffn_norm: Tensor::zeros(&[h]),
            w1: Tensor::zeros(&[h, inter]),
            w2: Tensor::zeros(&[inter, h]),
            w3: Tensor::zeros(&[h, inter]),
        }
    }
}