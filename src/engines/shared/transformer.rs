// src/engines/shared/transformer.rs
use super::tensor::Tensor;

/// Weights for a single transformer layer
#[derive(Clone)]
pub struct TransformerLayerWeights {
    pub layer_id: usize,
    pub attention_norm: Tensor,
    pub wq: Tensor,
    pub wk: Tensor,
    pub wv: Tensor,
    pub wo: Tensor,
    pub ffn_norm: Tensor,
    pub w1: Tensor,  // gate
    pub w2: Tensor,  // down
    pub w3: Tensor,  // up
}

impl TransformerLayerWeights {
    pub fn size_bytes(&self) -> u64 {
        (self.attention_norm.size_bytes()
            + self.wq.size_bytes()
            + self.wk.size_bytes()
            + self.wv.size_bytes()
            + self.wo.size_bytes()
            + self.ffn_norm.size_bytes()
            + self.w1.size_bytes()
            + self.w2.size_bytes()
            + self.w3.size_bytes()) as u64
    }
}

/// Model configuration parsed from GGUF
#[derive(Debug, Clone)]
pub struct ModelConfig {
    pub vocab_size: usize,
    pub hidden_dim: usize,
    pub intermediate_dim: usize,
    pub num_layers: usize,
    pub num_heads: usize,
    pub num_kv_heads: usize,
    pub head_dim: usize,
    pub max_seq_len: usize,
    pub rms_norm_eps: f32,
    pub rope_theta: f32,
}

impl ModelConfig {
    pub fn llama3_8b() -> Self {
        Self {
            vocab_size: 128256,
            hidden_dim: 4096,
            intermediate_dim: 14336,
            num_layers: 32,
            num_heads: 32,
            num_kv_heads: 8,
            head_dim: 128,
            max_seq_len: 8192,
            rms_norm_eps: 1e-5,
            rope_theta: 500000.0,
        }
    }
}

/// KV Cache for attention
pub struct KvCache {
    pub k: Vec<Tensor>,  // per layer
    pub v: Vec<Tensor>,  // per layer
    pub seq_len: usize,
    pub max_seq_len: usize,
}

impl KvCache {
    pub fn new(
        num_layers: usize,
        max_seq_len: usize,
        num_kv_heads: usize,
        head_dim: usize,
    ) -> Self {
        let k: Vec<Tensor> = (0..num_layers)
            .map(|_| Tensor::zeros(
                &[max_seq_len, num_kv_heads * head_dim]
            ))
            .collect();

        let v: Vec<Tensor> = (0..num_layers)
            .map(|_| Tensor::zeros(
                &[max_seq_len, num_kv_heads * head_dim]
            ))
            .collect();

        Self {
            k,
            v,
            seq_len: 0,
            max_seq_len,
        }
    }

    pub fn size_bytes(&self) -> u64 {
        let k_size: usize = self.k.iter()
            .map(|t| t.size_bytes())
            .sum();
        let v_size: usize = self.v.iter()
            .map(|t| t.size_bytes())
            .sum();
        (k_size + v_size) as u64
    }

    pub fn advance(&mut self) {
        self.seq_len += 1;
    }

    pub fn reset(&mut self) {
        self.seq_len = 0;
    }

    pub fn is_full(&self) -> bool {
        self.seq_len >= self.max_seq_len
    }

    /// Sliding window: drop oldest half of cache
    pub fn slide_window(&mut self) {
        let keep_from = self.seq_len / 2;
        // In production: actually shift data in tensors
        self.seq_len -= keep_from;
        tracing::info!(
            "KV cache sliding window applied, \
            new seq_len={}",
            self.seq_len
        );
    }
}

/// Execute a single transformer layer
pub fn forward_layer(
    input: &Tensor,
    weights: &TransformerLayerWeights,
    kv_cache: &mut KvCache,
    config: &ModelConfig,
    position: usize,
) -> Tensor {
    // 1. Attention norm
    let normed = input.rms_norm(
        &weights.attention_norm,
        config.rms_norm_eps
    );

    // 2. QKV projections
    let q = normed.matmul(&weights.wq);
    let k = normed.matmul(&weights.wk);
    let v = normed.matmul(&weights.wv);

    // 3. RoPE (simplified — production needs proper impl)
    // Skipped for brevity — apply rotary embeddings to q, k

    // 4. Attention computation (simplified single-head)
    let scale = 1.0 / (config.head_dim as f32).sqrt();
    let scores = q.matmul(&k); // Simplified
    let scaled_scores = Tensor::from_vec(
        scores.data.iter().map(|x| x * scale).collect(),
        scores.shape.clone(),
    );
    let attn_weights = scaled_scores.softmax();
    let attn_output = attn_weights.matmul(&v);

    // 5. Output projection
    let attn_projected = attn_output.matmul(&weights.wo);

    // 6. Residual connection
    let after_attn = input.add(&attn_projected);

    // 7. FFN norm
    let ffn_normed = after_attn.rms_norm(
        &weights.ffn_norm,
        config.rms_norm_eps
    );

    // 8. FFN: SwiGLU
    let gate = ffn_normed.matmul(&weights.w1).silu();
    let up = ffn_normed.matmul(&weights.w3);
    let ffn_out = gate.element_multiply(&up);
    let ffn_projected = ffn_out.matmul(&weights.w2);

    // 9. Residual connection
    after_attn.add(&ffn_projected)
}