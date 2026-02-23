// src/engines/shared/tokenizer.rs
use anyhow::Result;
use std::collections::HashMap;
use std::path::Path;

/// Simple BPE tokenizer implementation
/// In production, use tiktoken-rs or sentencepiece bindings
pub struct Tokenizer {
    vocab: HashMap<String, u32>,
    reverse_vocab: HashMap<u32, String>,
    bos_token: u32,
    eos_token: u32,
}

impl Tokenizer {
    pub fn from_model_path<P: AsRef<Path>>(path: P) -> Result<Self> {
        // In production: load tokenizer from GGUF metadata
        // or from separate tokenizer.json
        let mut vocab = HashMap::new();
        let mut reverse_vocab = HashMap::new();

        // Placeholder vocabulary
        for i in 0..32000u32 {
            let token = format!("token_{}", i);
            vocab.insert(token.clone(), i);
            reverse_vocab.insert(i, token);
        }

        Ok(Self {
            vocab,
            reverse_vocab,
            bos_token: 1,
            eos_token: 2,
        })
    }

    pub fn encode(&self, text: &str) -> Vec<u32> {
        // Simplified tokenization
        // In production: proper BPE encoding
        let mut tokens = vec![self.bos_token];
        for word in text.split_whitespace() {
            if let Some(&id) = self.vocab.get(word) {
                tokens.push(id);
            } else {
                // Character-level fallback
                for ch in word.chars() {
                    let key = ch.to_string();
                    if let Some(&id) = self.vocab.get(&key) {
                        tokens.push(id);
                    }
                }
            }
        }
        tokens
    }

    pub fn decode(&self, tokens: &[u32]) -> String {
        tokens.iter()
            .filter(|&&t| t != self.bos_token && t != self.eos_token)
            .filter_map(|t| self.reverse_vocab.get(t))
            .cloned()
            .collect::<Vec<_>>()
            .join(" ")
    }

    pub fn vocab_size(&self) -> usize {
        self.vocab.len()
    }

    pub fn eos_token(&self) -> u32 {
        self.eos_token
    }
}