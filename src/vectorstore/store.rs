// src/vectorstore/store.rs
use crate::core::config::VectorStoreConfig;
use crate::vectorstore::hnsw::HnswIndex;
use anyhow::Result;
use serde::{Deserialize, Serialize};
use std::path::PathBuf;

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Document {
    pub id: String,
    pub content: String,
    pub metadata: std::collections::HashMap<String, String>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct Chunk {
    pub id: String,
    pub document_id: String,
    pub content: String,
    pub embedding: Vec<f32>,
    pub start_idx: usize,
    pub end_idx: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SearchResult {
    pub chunk: Chunk,
    pub score: f32,
}

pub struct VectorStore {
    index: HnswIndex,
    chunks: parking_lot::RwLock<Vec<Chunk>>,
    config: VectorStoreConfig,
    index_path: PathBuf,
}

impl VectorStore {
    pub fn new(config: &VectorStoreConfig) -> Result<Self> {
        let index_path = PathBuf::from(&config.index_path);
        std::fs::create_dir_all(&index_path)?;

        let index = HnswIndex::new(384, 16, 200); // dim, M, ef

        Ok(Self {
            index,
            chunks: parking_lot::RwLock::new(Vec::new()),
            config: config.clone(),
            index_path,
        })
    }

    /// Ingest a document: chunk, embed, index
    pub fn ingest(&self, document: &Document) -> Result<usize> {
        let text_chunks = self.chunk_text(
            &document.content,
            self.config.chunk_size,
            self.config.chunk_overlap,
        );

        let mut stored_count = 0;

        for (i, text) in text_chunks.iter().enumerate() {
            // Generate embedding
            let embedding = self.embed_text(text);

            let chunk = Chunk {
                id: format!("{}_{}", document.id, i),
                document_id: document.id.clone(),
                content: text.clone(),
                embedding: embedding.clone(),
                start_idx: i * self.config.chunk_size,
                end_idx: (i + 1) * self.config.chunk_size,
            };

            self.index.insert(&embedding, self.chunks.read().len());
            self.chunks.write().push(chunk);
            stored_count += 1;
        }

        tracing::info!(
            "Ingested document '{}': {} chunks",
            document.id, stored_count
        );

        Ok(stored_count)
    }

    /// Search for relevant chunks
    pub fn search(
        &self,
        query: &str,
        top_k: usize,
    ) -> Vec<SearchResult> {
        let query_embedding = self.embed_text(query);
        let neighbors = self.index.search(&query_embedding, top_k);

        let chunks = self.chunks.read();

        neighbors.into_iter()
            .filter_map(|(idx, score)| {
                chunks.get(idx).map(|chunk| SearchResult {
                    chunk: chunk.clone(),
                    score,
                })
            })
            .collect()
    }

    /// Build RAG context from search results
    pub fn build_context(
        &self,
        query: &str,
        max_tokens: usize,
        top_k: usize,
    ) -> String {
        let results = self.search(query, top_k);

        let mut context = String::new();
        let mut token_count = 0;

        for result in results {
            let chunk_tokens = result.chunk.content
                .split_whitespace().count();
            if token_count + chunk_tokens > max_tokens {
                break;
            }
            context.push_str(&result.chunk.content);
            context.push_str("\n\n");
            token_count += chunk_tokens;
        }

        context
    }

    fn chunk_text(
        &self,
        text: &str,
        chunk_size: usize,
        overlap: usize,
    ) -> Vec<String> {
        let words: Vec<&str> = text.split_whitespace().collect();
        let mut chunks = Vec::new();
        let mut start = 0;

        while start < words.len() {
            let end = (start + chunk_size).min(words.len());
            let chunk = words[start..end].join(" ");
            chunks.push(chunk);

            if end >= words.len() {
                break;
            }

            start += chunk_size - overlap;
        }

        chunks
    }

    fn embed_text(&self, text: &str) -> Vec<f32> {
        // Placeholder embedding
        // In production: use actual embedding model
        let mut embedding = vec![0.0f32; 384];
        for (i, byte) in text.bytes().enumerate() {
            embedding[i % 384] += byte as f32 / 255.0;
        }

        // Normalize
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

    pub fn save(&self) -> Result<()> {
        let chunks = self.chunks.read();
        let json = serde_json::to_string(&*chunks)?;
        let path = self.index_path.join("chunks.json");
        std::fs::write(path, json)?;
        tracing::info!("Vector store saved");
        Ok(())
    }

    pub fn load(&self) -> Result<()> {
        let path = self.index_path.join("chunks.json");
        if path.exists() {
            let json = std::fs::read_to_string(path)?;
            let loaded: Vec<Chunk> = serde_json::from_str(&json)?;
            let mut chunks = self.chunks.write();
            *chunks = loaded;
            tracing::info!(
                "Loaded {} chunks from disk",
                chunks.len()
            );
        }
        Ok(())
    }

    pub fn chunk_count(&self) -> usize {
        self.chunks.read().len()
    }
}