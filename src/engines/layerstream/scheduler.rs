// src/engines/layerstream/scheduler.rs
use crate::core::memory_tracker::{MemoryCategory, MemoryTracker};
use crate::engines::layerstream::eviction::EvictionPolicy;
use crate::engines::layerstream::mmap_loader::MmapModelFile;
use crate::engines::layerstream::prefetch::PrefetchManager;
use crate::engines::shared::transformer::*;
use anyhow::Result;
use std::sync::Arc;
use std::time::Instant;

/// Core LayerStream scheduler
/// Orchestrates layer loading, computation, prefetching, and eviction
pub struct LayerStreamScheduler {
    prefetch_manager: PrefetchManager,
    eviction_policy: EvictionPolicy,
    memory_tracker: Arc<MemoryTracker>,
    config: ModelConfig,
    layer_size_bytes: u64,
}

#[derive(Debug)]
pub struct SchedulerStats {
    pub layers_processed: usize,
    pub prefetch_hits: usize,
    pub prefetch_misses: usize,
    pub evictions: usize,
    pub total_io_time_ms: u128,
}

impl LayerStreamScheduler {
    pub fn new(
        mmap_file: Arc<MmapModelFile>,
        memory_tracker: Arc<MemoryTracker>,
        config: ModelConfig,
        max_layers_in_memory: usize,
    ) -> Self {
        let layer_size = mmap_file.layer_size_bytes();

        let prefetch_manager = PrefetchManager::new(
            mmap_file.clone(),
            max_layers_in_memory,
        );

        let eviction_policy = EvictionPolicy::new(
            memory_tracker.clone(),
            max_layers_in_memory,
        );

        Self {
            prefetch_manager,
            eviction_policy,
            memory_tracker,
            config,
            layer_size_bytes: layer_size,
        }
    }

    /// Execute full forward pass through all layers
    pub fn forward_pass(
        &self,
        input: &crate::engines::shared::tensor::Tensor,
        kv_cache: &mut KvCache,
        position: usize,
    ) -> Result<(crate::engines::shared::tensor::Tensor, SchedulerStats)> {
        let mut stats = SchedulerStats {
            layers_processed: 0,
            prefetch_hits: 0,
            prefetch_misses: 0,
            evictions: 0,
            total_io_time_ms: 0,
        };

        let mut hidden = input.clone();

        for layer_id in 0..self.config.num_layers {
            // Step 1: Prefetch next layer
            if layer_id + 1 < self.config.num_layers {
                self.prefetch_manager.request_prefetch(layer_id + 1);
            }

            // Step 2: Ensure current layer is loaded
            let io_start = Instant::now();
            let layer_weights = self.prefetch_manager
                .get_layer(layer_id)?;
            let io_time = io_start.elapsed();
            stats.total_io_time_ms += io_time.as_millis();

            if io_time.as_millis() < 5 {
                stats.prefetch_hits += 1;
            } else {
                stats.prefetch_misses += 1;
            }

            // Step 3: Track memory
            let alloc_id = format!("layer_{}", layer_id);
            let _ = self.memory_tracker.try_allocate(
                &alloc_id,
                MemoryCategory::LayerWeights,
                self.layer_size_bytes,
            );

            // Step 4: Compute forward pass for this layer
            hidden = forward_layer(
                &hidden,
                &layer_weights,
                kv_cache,
                &self.config,
                position,
            );

            stats.layers_processed += 1;

            // Step 5: Evict previous layer
            if layer_id > 0 {
                let prev_alloc = format!("layer_{}", layer_id - 1);
                self.memory_tracker.release(&prev_alloc);
                self.prefetch_manager.evict(layer_id - 1);
                stats.evictions += 1;
            }

            // Step 6: Enforce memory ceiling
            if self.eviction_policy.should_evict(
                self.prefetch_manager.cached_count()
            ) {
                self.prefetch_manager.cleanup_except(layer_id);
            }
        }

        // Evict last layer
        let last_alloc = format!(
            "layer_{}",
            self.config.num_layers - 1
        );
        self.memory_tracker.release(&last_alloc);
        self.prefetch_manager.evict(self.config.num_layers - 1);

        Ok((hidden, stats))
    }

    pub fn shutdown(&self) {
        self.prefetch_manager.shutdown();
    }
}