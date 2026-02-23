// src/core/scheduler.rs
use crate::core::memory_tracker::{MemoryCategory, MemoryTracker};
use anyhow::Result;
use std::sync::Arc;
use tracing::{info, warn};

/// Global task scheduler for managing inference,
/// prefetch, and eviction priorities
pub struct TaskScheduler {
    memory_tracker: Arc<MemoryTracker>,
    max_concurrent_prefetch: usize,
    active_prefetch_count: parking_lot::Mutex<usize>,
}

impl TaskScheduler {
    pub fn new(
        memory_tracker: Arc<MemoryTracker>,
        max_concurrent_prefetch: usize,
    ) -> Self {
        Self {
            memory_tracker,
            max_concurrent_prefetch,
            active_prefetch_count: parking_lot::Mutex::new(0),
        }
    }

    pub fn can_prefetch(&self) -> bool {
        let count = self.active_prefetch_count.lock();
        *count < self.max_concurrent_prefetch
    }

    pub fn begin_prefetch(&self) -> bool {
        let mut count = self.active_prefetch_count.lock();
        if *count < self.max_concurrent_prefetch {
            *count += 1;
            true
        } else {
            false
        }
    }

    pub fn end_prefetch(&self) {
        let mut count = self.active_prefetch_count.lock();
        if *count > 0 {
            *count -= 1;
        }
    }

    pub fn ensure_memory_available(
        &self,
        needed: u64
    ) -> Result<()> {
        if self.memory_tracker.available() >= needed {
            return Ok(());
        }

        info!(
            "Need {} bytes, attempting eviction",
            needed
        );

        // Try evicting prefetch buffers first
        self.memory_tracker.force_evict_category(
            MemoryCategory::PrefetchBuffer,
            needed
        );

        if self.memory_tracker.available() >= needed {
            return Ok(());
        }

        // Try evicting old layer weights
        self.memory_tracker.force_evict_category(
            MemoryCategory::LayerWeights,
            needed
        );

        if self.memory_tracker.available() >= needed {
            Ok(())
        } else {
            Err(anyhow::anyhow!(
                "Cannot free enough memory. Need {} bytes, \
                only {} available",
                needed,
                self.memory_tracker.available()
            ))
        }
    }
}