// src/core/engine_factory.rs
use crate::core::config::AppConfig;
use crate::core::hardware_detector::{ExecutionMode, HardwareProfile};
use crate::core::memory_tracker::MemoryTracker;
use crate::engines::fullram::FullRamEngine;
use crate::engines::layerstream::LayerStreamEngine;
use crate::engines::traits::{InferenceEngine, InferenceRequest, InferenceResponse};
use crate::model_manager::model_metadata::ModelMetadata;
use anyhow::Result;
use std::sync::Arc;

pub struct EngineFactory;

impl EngineFactory {
    pub fn create(
        mode: ExecutionMode,
        model: &ModelMetadata,
        hardware: &HardwareProfile,
        memory_tracker: Arc<MemoryTracker>,
        config: &AppConfig,
    ) -> Result<Box<dyn InferenceEngine>> {
        let resolved_mode = match mode {
            ExecutionMode::Auto => {
                hardware.recommend_mode(
                    model.file_size_bytes,
                    config.runtime.max_ram_usage_percent
                )
            }
            other => other,
        };

        match resolved_mode {
            ExecutionMode::FullRam => {
                tracing::info!("Creating FullRAM engine for {}", model.name);
                let engine = FullRamEngine::new(
                    model.clone(),
                    memory_tracker,
                    config.inference.clone(),
                )?;
                Ok(Box::new(engine))
            }
            ExecutionMode::LayerStream => {
                tracing::info!(
                    "Creating LayerStream engine for {}", model.name
                );
                let engine = LayerStreamEngine::new(
                    model.clone(),
                    memory_tracker,
                    config.inference.clone(),
                    hardware.disk_read_speed_mbps,
                )?;
                Ok(Box::new(engine))
            }
            ExecutionMode::Insufficient => {
                Err(anyhow::anyhow!(
                    "Insufficient system resources for model '{}'. \
                    Required: {} bytes, Available RAM: {} bytes, \
                    Disk speed: {:.1} MB/s",
                    model.name,
                    model.file_size_bytes,
                    hardware.available_ram_bytes,
                    hardware.disk_read_speed_mbps
                ))
            }
            _ => Err(anyhow::anyhow!("Invalid engine mode")),
        }
    }
}