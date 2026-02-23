// src/core/memory_tracker.rs
use parking_lot::RwLock;
use std::collections::HashMap;
use std::sync::Arc;
use tracing::{info, warn};

#[derive(Debug, Clone)]
pub struct MemoryAllocation {
    pub id: String,
    pub category: MemoryCategory,
    pub size_bytes: u64,
    pub timestamp: std::time::Instant,
}

#[derive(Debug, Clone, PartialEq, Eq, Hash)]
pub enum MemoryCategory {
    LayerWeights,
    PrefetchBuffer,
    ActivationBuffer,
    KvCache,
    EmbeddingIndex,
    SystemOverhead,
}

pub struct MemoryTracker {
    max_bytes: u64,
    allocations: RwLock<HashMap<String, MemoryAllocation>>,
    current_usage: RwLock<u64>,
}

impl MemoryTracker {
    pub fn new(max_bytes: u64) -> Arc<Self> {
        Arc::new(Self {
            max_bytes,
            allocations: RwLock::new(HashMap::new()),
            current_usage: RwLock::new(0),
        })
    }

    pub fn try_allocate(
        &self,
        id: &str,
        category: MemoryCategory,
        size_bytes: u64,
    ) -> Result<(), MemoryError> {
        let mut current = self.current_usage.write();
        let mut allocs = self.allocations.write();

        if *current + size_bytes > self.max_bytes {
            return Err(MemoryError::CeilingExceeded {
                requested: size_bytes,
                available: self.max_bytes - *current,
                max: self.max_bytes,
            });
        }

        let allocation = MemoryAllocation {
            id: id.to_string(),
            category,
            size_bytes,
            timestamp: std::time::Instant::now(),
        };

        *current += size_bytes;
        allocs.insert(id.to_string(), allocation);

        info!(
            "Memory allocated: {} ({} bytes). Total: {}/{}",
            id, size_bytes, *current, self.max_bytes
        );

        Ok(())
    }

    pub fn release(&self, id: &str) -> Option<u64> {
        let mut current = self.current_usage.write();
        let mut allocs = self.allocations.write();

        if let Some(allocation) = allocs.remove(id) {
            *current -= allocation.size_bytes;
            info!(
                "Memory released: {} ({} bytes). Total: {}/{}",
                id, allocation.size_bytes, *current, self.max_bytes
            );
            Some(allocation.size_bytes)
        } else {
            None
        }
    }

    pub fn current_usage(&self) -> u64 {
        *self.current_usage.read()
    }

    pub fn available(&self) -> u64 {
        self.max_bytes - *self.current_usage.read()
    }

    pub fn usage_percent(&self) -> f64 {
        let current = *self.current_usage.read();
        (current as f64 / self.max_bytes as f64) * 100.0
    }

    pub fn get_eviction_candidates(
        &self,
        category: MemoryCategory,
    ) -> Vec<MemoryAllocation> {
        let allocs = self.allocations.read();
        let mut candidates: Vec<MemoryAllocation> = allocs
            .values()
            .filter(|a| a.category == category)
            .cloned()
            .collect();

        // Sort by oldest first (LRU)
        candidates.sort_by(|a, b| a.timestamp.cmp(&b.timestamp));
        candidates
    }

    pub fn force_evict_category(
        &self,
        category: MemoryCategory,
        needed_bytes: u64
    ) -> Vec<String> {
        let candidates = self.get_eviction_candidates(category);
        let mut freed = 0u64;
        let mut evicted_ids = Vec::new();

        for candidate in candidates {
            if freed >= needed_bytes {
                break;
            }
            if let Some(size) = self.release(&candidate.id) {
                freed += size;
                evicted_ids.push(candidate.id);
            }
        }

        if freed < needed_bytes {
            warn!(
                "Could only free {} of {} requested bytes",
                freed, needed_bytes
            );
        }

        evicted_ids
    }

    pub fn snapshot(&self) -> MemorySnapshot {
        let allocs = self.allocations.read();
        let mut by_category: HashMap<MemoryCategory, u64> = HashMap::new();

        for alloc in allocs.values() {
            *by_category.entry(alloc.category.clone()).or_insert(0)
                += alloc.size_bytes;
        }

        MemorySnapshot {
            total_max: self.max_bytes,
            total_used: *self.current_usage.read(),
            by_category,
            allocation_count: allocs.len(),
        }
    }
}

#[derive(Debug)]
pub struct MemorySnapshot {
    pub total_max: u64,
    pub total_used: u64,
    pub by_category: HashMap<MemoryCategory, u64>,
    pub allocation_count: usize,
}

#[derive(Debug, thiserror::Error)]
pub enum MemoryError {
    #[error(
        "Memory ceiling exceeded: requested {requested} bytes, \
        available {available} of {max} max"
    )]
    CeilingExceeded {
        requested: u64,
        available: u64,
        max: u64,
    },
}