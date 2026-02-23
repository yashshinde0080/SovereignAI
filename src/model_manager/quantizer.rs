// src/model_manager/quantizer.rs
use anyhow::Result;
use std::path::{Path, PathBuf};

/// Handles model format conversion and quantization
pub struct Quantizer;

impl Quantizer {
    /// Check if model is already in GGUF format
    pub fn is_gguf<P: AsRef<Path>>(path: P) -> bool {
        path.as_ref()
            .extension()
            .map(|e| e == "gguf")
            .unwrap_or(false)
    }

    /// Convert and quantize model to GGUF format
    /// In production: call llama.cpp convert tools
    pub fn quantize<P: AsRef<Path>>(
        input: P,
        output_dir: &str,
        quant_type: &str,
    ) -> Result<PathBuf> {
        let input_path = input.as_ref();

        if Self::is_gguf(input_path) {
            tracing::info!("Model already in GGUF format");
            return Ok(input_path.to_path_buf());
        }

        let stem = input_path.file_stem()
            .unwrap_or_default()
            .to_string_lossy();

        let output_path = PathBuf::from(output_dir)
            .join(format!("{}-{}.gguf", stem, quant_type));

        // In production: invoke llama.cpp quantize binary
        // or use ggml library directly
        tracing::info!(
            "Quantizing {} to {} ({})",
            input_path.display(),
            output_path.display(),
            quant_type
        );

        // Placeholder: copy file
        std::fs::copy(input_path, &output_path)?;

        Ok(output_path)
    }

    /// Get recommended quantization based on available RAM
    pub fn recommend_quant(available_ram_gb: f64) -> &'static str {
        if available_ram_gb >= 32.0 {
            "Q8_0"
        } else if available_ram_gb >= 16.0 {
            "Q5_K_M"
        } else if available_ram_gb >= 8.0 {
            "Q4_K_M"
        } else {
            "Q3_K_S"
        }
    }
}