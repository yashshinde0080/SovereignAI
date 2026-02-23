// src/engines/layerstream/eviction.rs
use crate::core::memory_tracker::{MemoryCategory, MemoryTracker};
use std::sync::Arc;
use tracing::info;

pub struct EvictionPolicy {
    memory_tracker: Arc<MemoryTracker>,
    max_layers_in_memory: usize,
}

impl EvictionPolicy {
    pub fn new(
        memory_tracker: Arc<MemoryTracker>,
        max_layers_in_memory: usize,
    ) -> Self {
        Self {
            memory_tracker,
            max_layers_in_memory,
        }
    }

    /// Determine if eviction is needed before loading new layer
    pub fn should_evict(&self, current_cached: usize) -> bool {
        current_cached >= self.max_layers_in_memory
            || self.memory_tracker.usage_percent() > 85.0
    }

    /// Select which layer to evict (LRU strategy)
    pub fn select_victim(
        &self,
        cached_layers: &[usize],
        current_layer: usize,
    ) -> Option<usize> {
        // Never evict current or next layer
        cached_layers.iter()
            .filter(|&&id| id != current_layer && id != current_layer + 1)
            .min() // Evict oldest (lowest layer ID)
            .copied()
    }

    /// Force evict layer weights from memory tracker
    pub fn execute_eviction(&self, layer_id: usize) -> bool {
        let alloc_id = format!("layer_{}", layer_id);
        if self.memory_tracker.release(&alloc_id).is_some() {
            info!("Evicted layer {} from memory tracker", layer_id);
            true
        } else {
            false
        }
    }
}