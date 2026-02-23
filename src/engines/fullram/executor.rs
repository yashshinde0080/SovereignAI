// src/engines/fullram/executor.rs
use crate::core::config::InferenceConfig;
use crate::core::memory_tracker::{MemoryCategory, MemoryTracker};
use crate::engines::fullram::loader::FullModelLoader;
use crate::engines::shared::tensor::Tensor;
use crate::engines::shared::tokenizer::Tokenizer;
use crate::engines::shared::transformer::*;
use crate::engines::traits::*;
use crate::model_manager::model_metadata::ModelMetadata;
use anyhow::Result;
use parking_lot::Mutex;
use std::sync::Arc;
use std::time::Instant;

pub struct FullRamEngine {
    model_meta: ModelMetadata,
    config: ModelConfig,
    inference_config: InferenceConfig,
    layers: Vec<TransformerLayerWeights>,
    embedding: Tensor,
    output_proj: Tensor,
    tokenizer: Tokenizer,
    kv_cache: Mutex<KvCache>,
    memory_tracker: Arc<MemoryTracker>,
    loaded: bool,
}

impl FullRamEngine {
    pub fn new(
        model_meta: ModelMetadata,
        memory_tracker: Arc<MemoryTracker>,
        inference_config: InferenceConfig,
    ) -> Result<Self> {
        let model_path = &model_meta.file_path;

        // Load entire model into RAM
        let (config, layers, embedding, output_proj) =
            FullModelLoader::load(model_path)?;

        // Track memory
        let total_size = layers.iter()
            .map(|l| l.size_bytes())
            .sum::<u64>()
            + embedding.size_bytes() as u64
            + output_proj.size_bytes() as u64;

        memory_tracker.try_allocate(
            "fullram_model",
            MemoryCategory::LayerWeights,
            total_size,
        )?;

        let tokenizer = Tokenizer::from_model_path(model_path)?;

        let kv_cache = KvCache::new(
            config.num_layers,
            config.max_seq_len,
            config.num_kv_heads,
            config.head_dim,
        );

        memory_tracker.try_allocate(
            "fullram_kv_cache",
            MemoryCategory::KvCache,
            kv_cache.size_bytes(),
        )?;

        Ok(Self {
            model_meta,
            config,
            inference_config,
            layers,
            embedding,
            output_proj,
            tokenizer,
            kv_cache: Mutex::new(kv_cache),
            memory_tracker,
            loaded: true,
        })
    }

    fn generate_tokens(
        &self,
        input_tokens: &[u32],
        max_tokens: usize,
        temperature: f32,
    ) -> Result<(Vec<u32>, u128)> {
        let mut kv = self.kv_cache.lock();
        kv.reset();

        let mut all_tokens = input_tokens.to_vec();
        let mut generated = Vec::new();
        let mut time_to_first = 0u128;
        let start = Instant::now();

        for step in 0..max_tokens {
            let current_token = *all_tokens.last().unwrap();

            // Embed current token
            let hidden = self.embed_token(current_token);

            // Forward through all layers
            let mut x = hidden;
            for layer in &self.layers {
                x = forward_layer(
                    &x,
                    layer,
                    &mut kv,
                    &self.config,
                    all_tokens.len() - 1,
                );
            }

            // Project to vocabulary
            let logits = x.matmul(&self.output_proj);

            // Sample next token
            let next_token = logits.sample(temperature);

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

        Ok((generated, time_to_first))
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

impl InferenceEngine for FullRamEngine {
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

            let (generated_tokens, ttft) = self.generate_tokens(
                &input_tokens,
                request.max_tokens,
                request.temperature,
            )?;

            let text = self.tokenizer.decode(&generated_tokens);
            let total_time = start.elapsed();

            Ok(InferenceResponse {
                text,
                tokens_generated: generated_tokens.len(),
                prompt_tokens,
                time_to_first_token_ms: ttft,
                total_time_ms: total_time.as_millis(),
                peak_memory_bytes: self.memory_tracker.current_usage(),
                mode: "fullram".to_string(),
            })
        })
    }

    fn model_name(&self) -> &str {
        &self.model_meta.name
    }

    fn mode(&self) -> &str {
        "fullram"
    }

    fn is_loaded(&self) -> bool {
        self.loaded
    }

    fn unload(&self) -> Result<()> {
        self.memory_tracker.release("fullram_model");
        self.memory_tracker.release("fullram_kv_cache");
        Ok(())
    }

    fn memory_usage(&self) -> u64 {
        self.memory_tracker.current_usage()
    }
}