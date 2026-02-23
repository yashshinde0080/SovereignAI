// src/engines/layerstream/executor.rs
use crate::core::config::InferenceConfig;
use crate::core::memory_tracker::{MemoryCategory, MemoryTracker};
use crate::engines::layerstream::mmap_loader::MmapModelFile;
use crate::engines::layerstream::scheduler::LayerStreamScheduler;
use crate::engines::shared::tensor::Tensor;
use crate::engines::shared::tokenizer::Tokenizer;
use crate::engines::shared::transformer::*;
use crate::engines::traits::*;
use crate::model_manager::model_metadata::ModelMetadata;
use anyhow::Result;
use parking_lot::Mutex;
use std::sync::Arc;
use std::time::Instant;

pub struct LayerStreamEngine {
    model_meta: ModelMetadata,
    config: ModelConfig,
    inference_config: InferenceConfig,
    scheduler: LayerStreamScheduler,
    tokenizer: Tokenizer,
    embedding: Tensor,
    output_proj: Tensor,
    kv_cache: Mutex<KvCache>,
    memory_tracker: Arc<MemoryTracker>,
    disk_speed_mbps: f64,
}

impl LayerStreamEngine {
    pub fn new(
        model_meta: ModelMetadata,
        memory_tracker: Arc<MemoryTracker>,
        inference_config: InferenceConfig,
        disk_speed_mbps: f64,
    ) -> Result<Self> {
        let config = ModelConfig::llama3_8b();

        // Open memory-mapped model file
        let mmap_file = MmapModelFile::open(
            &model_meta.file_path,
            config.num_layers,
            config.hidden_dim,
        )?;
        let mmap_file = Arc::new(mmap_file);

        // Determine max layers in memory based on available RAM
        let layer_size = mmap_file.layer_size_bytes();
        let available = memory_tracker.available();
        let max_layers = (available / layer_size)
            .min(3) // Never more than 3 layers
            .max(2) as usize; // At least 2 for double buffering

        tracing::info!(
            "LayerStream: max {} layers in memory \
            ({} bytes/layer, {} bytes available)",
            max_layers, layer_size, available
        );

        if disk_speed_mbps < 100.0 {
            tracing::warn!(
                "Disk speed {:.1} MB/s is below recommended 100 MB/s. \
                LayerStream performance may degrade.",
                disk_speed_mbps
            );
        }

        let scheduler = LayerStreamScheduler::new(
            mmap_file,
            memory_tracker.clone(),
            config.clone(),
            max_layers,
        );

        let tokenizer = Tokenizer::from_model_path(
            &model_meta.file_path
        )?;

        // Load embedding and output projection
        // These stay resident in memory
        let embedding = Tensor::zeros(
            &[config.vocab_size, config.hidden_dim]
        );
        let output_proj = Tensor::zeros(
            &[config.hidden_dim, config.vocab_size]
        );

        memory_tracker.try_allocate(
            "embedding",
            MemoryCategory::LayerWeights,
            embedding.size_bytes() as u64,
        )?;

        memory_tracker.try_allocate(
            "output_proj",
            MemoryCategory::LayerWeights,
            output_proj.size_bytes() as u64,
        )?;

        let kv_cache = KvCache::new(
            config.num_layers,
            config.max_seq_len.min(inference_config.max_context_length),
            config.num_kv_heads,
            config.head_dim,
        );

        memory_tracker.try_allocate(
            "layerstream_kv_cache",
            MemoryCategory::KvCache,
            kv_cache.size_bytes(),
        )?;

        Ok(Self {
            model_meta,
            config,
            inference_config,
            scheduler,
            tokenizer,
            embedding,
            output_proj,
            kv_cache: Mutex::new(kv_cache),
            memory_tracker,
            disk_speed_mbps,
        })
    }

    fn embed_token(&self, token_id: u32) -> Tensor {
        let h = self.config.hidden_dim;
        let start = (token_id as usize) * h;
        let end = start + h;

        if end <= self.embedding.data.len() {
            Tensor::from_vec(
                self.embedding.data[start..end].to_vec(),
                vec![1, h],
            )
        } else {
            Tensor::zeros(&[1, h])
        }
    }
}

impl InferenceEngine for LayerStreamEngine {
    fn generate(
        &self,
        request: &InferenceRequest,
    ) -> std::pin::Pin<Box<dyn std::future::Future<
        Output = Result<InferenceResponse>
    > + Send + '_>> {
        Box::pin(async move {
            let start = Instant::now();

            let input_tokens = self.tokenizer.encode(&request.prompt);
            let prompt_tokens = input_tokens.len();

            let mut all_tokens = input_tokens.clone();
            let mut generated = Vec::new();
            let mut time_to_first = 0u128;

            let mut kv = self.kv_cache.lock();
            kv.reset();

            let mut total_io_ms = 0u128;

            for step in 0..request.max_tokens {
                let current_token = *all_tokens.last().unwrap();
                let hidden = self.embed_token(current_token);

                // Forward through all layers via scheduler
                let (output, stats) = self.scheduler.forward_pass(
                    &hidden,
                    &mut kv,
                    all_tokens.len() - 1,
                )?;

                total_io_ms += stats.total_io_time_ms;

                // Project to vocab
                let logits = output.matmul(&self.output_proj);
                let next_token = logits.sample(request.temperature);

                if step == 0 {
                    time_to_first = start.elapsed().as_millis();
                }

                if next_token as u32 == self.tokenizer.eos_token() {
                    break;
                }

                generated.push(next_token as u32);
                all_tokens.push(next_token as u32);
                kv.advance();

                if kv.is_full() {
                    kv.slide_window();
                }
            }

            let text = self.tokenizer.decode(&generated);
            let total_time = start.elapsed();

            tracing::info!(
                "LayerStream: {} tokens, {:.1}ms total, \
                {:.1}ms I/O ({:.1}%)",
                generated.len(),
                total_time.as_millis(),
                total_io_ms,
                (total_io_ms as f64
                    / total_time.as_millis() as f64) * 100.0
            );

            Ok(InferenceResponse {
                text,
                tokens_generated: generated.len(),
                prompt_tokens,
                time_to_first_token_ms: time_to_first,
                total_time_ms: total_time.as_millis(),
                peak_memory_bytes: self.memory_tracker.current_usage(),
                mode: "layerstream".to_string(),
            })
        })
    }

    fn model_name(&self) -> &str {
        &self.model_meta.name
    }

    fn mode(&self) -> &str {
        "layerstream"
    }

    fn is_loaded(&self) -> bool {
        true
    }

    fn unload(&self) -> Result<()> {
        self.scheduler.shutdown();
        self.memory_tracker.release("embedding");
        self.memory_tracker.release("output_proj");
        self.memory_tracker.release("layerstream_kv_cache");
        Ok(())
    }

    fn memory_usage(&self) -> u64 {
        self.memory_tracker.current_usage()
    }
}