// src/vectorstore/embedding.rs
use anyhow::Result;

/// Embedding model interface
pub struct EmbeddingPipeline {
    dimension: usize,
}

impl EmbeddingPipeline {
    pub fn new(model_name: &str) -> Result<Self> {
        let dimension = match model_name {
            "all-MiniLM-L6-v2" => 384,
            "all-mpnet-base-v2" => 768,
            _ => 384,
        };

        tracing::info!(
            "Embedding pipeline: {} (dim={})",
            model_name, dimension
        );

        Ok(Self { dimension })
    }

    pub fn embed(&self, text: &str) -> Vec<f32> {
        // Placeholder: in production use ONNX or GGUF embedding model
        let mut embedding = vec![0.0f32; self.dimension];
        for (i, byte) in text.bytes().enumerate() {
            embedding[i % self.dimension] += byte as f32 / 255.0;
        }

        let norm: f32 = embedding.iter()
            .map(|x| x * x)
            .sum::<f32>()
            .sqrt();

        if norm > 0.0 {
            for x in &mut embedding {
                *x /= norm;
            }
        }

        embedding
    }

    pub fn dimension(&self) -> usize {
        self.dimension
    }
}