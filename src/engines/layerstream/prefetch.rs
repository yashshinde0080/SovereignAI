// src/engines/layerstream/prefetch.rs
use crate::engines::layerstream::mmap_loader::MmapModelFile;
use crate::engines::shared::transformer::TransformerLayerWeights;
use crossbeam::channel::{self, Receiver, Sender};
use parking_lot::Mutex;
use std::collections::HashMap;
use std::sync::Arc;
use std::thread;

pub struct PrefetchManager {
    mmap_file: Arc<MmapModelFile>,
    cache: Arc<Mutex<HashMap<usize, TransformerLayerWeights>>>,
    request_tx: Sender<PrefetchRequest>,
    max_cached_layers: usize,
}

enum PrefetchRequest {
    Load(usize),
    Evict(usize),
    Shutdown,
}

impl PrefetchManager {
    pub fn new(
        mmap_file: Arc<MmapModelFile>,
        max_cached_layers: usize,
    ) -> Self {
        let cache: Arc<Mutex<HashMap<usize, TransformerLayerWeights>>> =
            Arc::new(Mutex::new(HashMap::new()));

        let (tx, rx) = channel::unbounded();

        let cache_clone = cache.clone();
        let mmap_clone = mmap_file.clone();

        // Spawn prefetch worker thread
        thread::Builder::new()
            .name("prefetch-worker".into())
            .spawn(move || {
                Self::prefetch_worker(rx, cache_clone, mmap_clone);
            })
            .expect("Failed to spawn prefetch thread");

        Self {
            mmap_file,
            cache,
            request_tx: tx,
            max_cached_layers,
        }
    }

    fn prefetch_worker(
        rx: Receiver<PrefetchRequest>,
        cache: Arc<Mutex<HashMap<usize, TransformerLayerWeights>>>,
        mmap: Arc<MmapModelFile>,
    ) {
        loop {
            match rx.recv() {
                Ok(PrefetchRequest::Load(layer_id)) => {
                    let already_loaded = cache.lock().contains_key(&layer_id);
                    if already_loaded {
                        continue;
                    }

                    match mmap.load_layer(layer_id) {
                        Ok(weights) => {
                            cache.lock().insert(layer_id, weights);
                            tracing::debug!(
                                "Prefetched layer {}", layer_id
                            );
                        }
                        Err(e) => {
                            tracing::error!(
                                "Prefetch error layer {}: {}",
                                layer_id, e
                            );
                        }
                    }
                }
                Ok(PrefetchRequest::Evict(layer_id)) => {
                    cache.lock().remove(&layer_id);
                    tracing::debug!(
                        "Evicted layer {} from cache", layer_id
                    );
                }
                Ok(PrefetchRequest::Shutdown) | Err(_) => {
                    tracing::info!("Prefetch worker shutting down");
                    break;
                }
            }
        }
    }

    /// Request async prefetch of next layer
    pub fn request_prefetch(&self, layer_id: usize) {
        if layer_id < self.mmap_file.total_layers() {
            let _ = self.request_tx.send(PrefetchRequest::Load(layer_id));
        }
    }

    /// Get layer from cache or load synchronously
    pub fn get_layer(
        &self,
        layer_id: usize
    ) -> anyhow::Result<TransformerLayerWeights> {
        // Check cache first
        if let Some(weights) = self.cache.lock().get(&layer_id) {
            return Ok(weights.clone());
        }

        // Synchronous fallback
        let weights = self.mmap_file.load_layer(layer_id)?;
        self.cache.lock().insert(layer_id, weights.clone());
        Ok(weights)
    }

    /// Evict a layer from cache
    pub fn evict(&self, layer_id: usize) {
        let _ = self.request_tx.send(PrefetchRequest::Evict(layer_id));
    }

    /// Clean up old layers, keeping only nearby ones
    pub fn cleanup_except(&self, current_layer: usize) {
        let ids: Vec<usize> = self.cache.lock()
            .keys()
            .cloned()
            .collect();

        for id in ids {
            // Keep current and next layer
            if id != current_layer
                && id != current_layer + 1
                && id + 2 < current_layer
            {
                self.evict(id);
            }
        }
    }

    pub fn cached_count(&self) -> usize {
        self.cache.lock().len()
    }

    pub fn shutdown(&self) {
        let _ = self.request_tx.send(PrefetchRequest::Shutdown);
    }
}

impl Drop for PrefetchManager {
    fn drop(&mut self) {
        self.shutdown();
    }
}