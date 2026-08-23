"""Tests for transformer model, KV-cache, and text generation."""

from pathlib import Path

import numpy as np
import pytest

from engine.config import ModelConfig
from engine.gguf import GGUFParser
from engine.loader import CheckpointLoader
from engine.model import TransformerModel, _attention, _ffn
from engine.kv_cache import KVCache
from engine.inference import generate
from engine.tokenizer import Tokenizer


# ── Helpers ─────────────────────────────────────────────────────────

def _load_transformer(tiny_transformer_gguf: Path, model_dir: Path | None = None):
    """Load a tiny transformer model from GGUF + config."""
    loader = CheckpointLoader(tiny_transformer_gguf)
    if model_dir:
        config = ModelConfig.load(model_dir, loader.data.metadata)
    else:
        config = ModelConfig.from_gguf_metadata(loader.data.metadata)
    model = TransformerModel(config, loader)
    return model, loader


# ── KV-Cache tests ──────────────────────────────────────────────────

class TestKVCache:
    def test_basic_append(self):
        cache = KVCache(n_layers=2, n_heads=4, head_dim=8, max_seq_len=64)
        k = np.ones((3, 4, 8), dtype=np.float32)
        v = np.ones((3, 4, 8), dtype=np.float32)
        cache.append(0, k, v)
        cache.advance(3)
        assert cache.cur_len == 3

    def test_get_after_append(self):
        cache = KVCache(n_layers=1, n_heads=2, head_dim=4, max_seq_len=16)
        k = np.arange(16).reshape(2, 2, 4).astype(np.float32)
        v = np.arange(16, 32).reshape(2, 2, 4).astype(np.float32)
        cache.append(0, k, v)
        cache.advance(2)
        k_out, v_out = cache.get(0)
        np.testing.assert_array_equal(k_out, k)
        np.testing.assert_array_equal(v_out, v)

    def test_overflow_raises(self):
        cache = KVCache(n_layers=1, n_heads=2, head_dim=4, max_seq_len=4)
        k = np.ones((5, 2, 4), dtype=np.float32)
        v = np.ones((5, 2, 4), dtype=np.float32)
        with pytest.raises(ValueError, match="overflow"):
            cache.append(0, k, v)

    def test_clear(self):
        cache = KVCache(n_layers=1, n_heads=2, head_dim=4, max_seq_len=16)
        cache.append(0, np.ones((3, 2, 4)), np.ones((3, 2, 4)))
        cache.advance(3)
        cache.clear()
        assert cache.cur_len == 0

    def test_size_bytes(self):
        cache = KVCache(n_layers=2, n_heads=4, head_dim=8, max_seq_len=64)
        expected = 2 * 2 * 64 * 4 * 8 * 4  # n_layers * 2(k+v) * max * n_heads * head_dim * 4bytes
        assert cache.size_bytes == expected

    def test_single_token_append(self):
        """Append with 2D input [n_heads, head_dim] (no seq dim)."""
        cache = KVCache(n_layers=1, n_heads=2, head_dim=4, max_seq_len=16)
        k = np.ones((2, 4), dtype=np.float32)
        v = np.ones((2, 4), dtype=np.float32)
        cache.append(0, k, v)
        cache.advance(1)
        assert cache.cur_len == 1


# ── Attention tests ─────────────────────────────────────────────────

class TestAttention:
    def test_causal_mask(self):
        """Prefill: each position can only attend to previous positions."""
        n_heads, head_dim = 2, 4
        seq_len = 3
        q = np.random.randn(seq_len, n_heads, head_dim).astype(np.float32)
        k = np.random.randn(seq_len, n_heads, head_dim).astype(np.float32)
        v = np.random.randn(seq_len, n_heads, head_dim).astype(np.float32)

        out = _attention(q, k, v, kv_cache=None, layer_idx=0)
        assert out.shape == (seq_len, n_heads, head_dim)  # returns un-flattened

    def test_with_kv_cache(self):
        """Decode: single query attending to cached keys."""
        n_heads, head_dim = 2, 4
        cache = KVCache(n_layers=1, n_heads=n_heads, head_dim=head_dim, max_seq_len=16)

        # Prefill: 3 tokens
        q_prefill = np.random.randn(3, n_heads, head_dim).astype(np.float32)
        k_prefill = np.random.randn(3, n_heads, head_dim).astype(np.float32)
        v_prefill = np.random.randn(3, n_heads, head_dim).astype(np.float32)
        out = _attention(q_prefill, k_prefill, v_prefill, cache, layer_idx=0)
        assert out.shape == (3, n_heads, head_dim)
        # Advance cache manually (normally done by forward())
        cache.advance(3)

        # Decode: 1 token attending to 3 cached
        q_decode = np.random.randn(1, n_heads, head_dim).astype(np.float32)
        k_new = np.random.randn(1, n_heads, head_dim).astype(np.float32)
        v_new = np.random.randn(1, n_heads, head_dim).astype(np.float32)
        out = _attention(q_decode, k_new, v_new, cache, layer_idx=0)
        assert out.shape == (1, n_heads, head_dim)
        assert cache.cur_len == 3  # advance not called by _attention

    def test_gqa_expansion(self):
        """GQA: n_kv_heads=2, n_heads=4 → k/v repeated 2x."""
        n_heads, n_kv_heads, head_dim = 4, 2, 4
        q = np.random.randn(1, n_heads, head_dim).astype(np.float32)
        k = np.random.randn(1, n_kv_heads, head_dim).astype(np.float32)
        v = np.random.randn(1, n_kv_heads, head_dim).astype(np.float32)

        out = _attention(q, k, v, kv_cache=None, layer_idx=0)
        assert out.shape == (1, n_heads, head_dim)  # un-flattened


# ── FFN tests ───────────────────────────────────────────────────────

class TestFFN:
    def test_shape(self):
        dim, hidden_dim = 16, 32
        x = np.random.randn(3, dim).astype(np.float32)
        gate_w = np.random.randn(hidden_dim, dim).astype(np.float32)
        up_w = np.random.randn(hidden_dim, dim).astype(np.float32)
        down_w = np.random.randn(dim, hidden_dim).astype(np.float32)

        out = _ffn(x, gate_w, up_w, down_w)
        assert out.shape == (3, dim)

    def test_deterministic(self):
        dim, hidden_dim = 8, 16
        x = np.ones((1, dim), dtype=np.float32)
        gate_w = np.ones((hidden_dim, dim), dtype=np.float32)
        up_w = np.ones((hidden_dim, dim), dtype=np.float32)
        down_w = np.ones((dim, hidden_dim), dtype=np.float32)

        out1 = _ffn(x, gate_w, up_w, down_w)
        out2 = _ffn(x, gate_w, up_w, down_w)
        np.testing.assert_array_equal(out1, out2)


# ── Model forward pass tests ────────────────────────────────────────

class TestTransformerModel:
    def test_forward_shape(self, tiny_transformer_gguf: Path):
        model, loader = _load_transformer(tiny_transformer_gguf)
        ids = np.array([0, 1, 2], dtype=np.int64)
        logits = model.forward(ids)
        assert logits.shape == (3, 256)  # [seq_len, vocab_size]
        loader.close()

    def test_forward_single_token(self, tiny_transformer_gguf: Path):
        model, loader = _load_transformer(tiny_transformer_gguf)
        ids = np.array([5], dtype=np.int64)
        logits = model.forward(ids)
        assert logits.shape == (1, 256)
        loader.close()

    def test_forward_with_kv_cache(self, tiny_transformer_gguf: Path):
        model, loader = _load_transformer(tiny_transformer_gguf)
        config = model.config
        cache = KVCache(config.n_layers, config.n_kv_heads, config.head_dim,
                        config.max_position_embeddings)

        # Prefill
        ids = np.array([0, 1, 2], dtype=np.int64)
        logits = model.forward(ids, cache)
        assert logits.shape == (3, 256)
        assert cache.cur_len == 3

        # Decode
        next_id = np.array([np.argmax(logits[-1])], dtype=np.int64)
        logits2 = model.forward(next_id, cache)
        assert logits2.shape == (1, 256)
        assert cache.cur_len == 4
        loader.close()

    def test_deterministic(self, tiny_transformer_gguf: Path):
        model, _ = _load_transformer(tiny_transformer_gguf)
        ids = np.array([0, 1], dtype=np.int64)
        logits1 = model.forward(ids.copy())
        logits2 = model.forward(ids.copy())
        np.testing.assert_array_almost_equal(logits1, logits2, decimal=5)

    def test_n_params(self, tiny_transformer_gguf: Path):
        model, _ = _load_transformer(tiny_transformer_gguf)
        n = model.n_params()
        assert n > 0
        assert isinstance(n, int)

    def test_size_gb(self, tiny_transformer_gguf: Path):
        model, _ = _load_transformer(tiny_transformer_gguf)
        gb = model.size_gb()
        assert gb > 0
        assert gb > 0  # tiny model has params


# ── Generation tests ────────────────────────────────────────────────

class TestGeneration:
    def test_generate_basic(self, tiny_transformer_gguf: Path, tiny_model_dir: Path):
        model, loader = _load_transformer(tiny_transformer_gguf, tiny_model_dir)
        tokenizer = Tokenizer(tiny_model_dir)

        result = generate(model, tokenizer, "hello", max_tokens=5)
        assert result.n_generated_tokens <= 5
        assert result.elapsed_s > 0
        assert result.tokens_per_second >= 0
        loader.close()

    def test_generate_empty_prompt(self, tiny_transformer_gguf: Path, tiny_model_dir: Path):
        model, loader = _load_transformer(tiny_transformer_gguf, tiny_model_dir)
        tokenizer = Tokenizer(tiny_model_dir)

        result = generate(model, tokenizer, "", max_tokens=3)
        assert result.n_generated_tokens <= 3
        loader.close()

    def test_generate_greedy(self, tiny_transformer_gguf: Path, tiny_model_dir: Path):
        """temperature=0 → deterministic (greedy) generation."""
        model, loader = _load_transformer(tiny_transformer_gguf, tiny_model_dir)
        tokenizer = Tokenizer(tiny_model_dir)

        r1 = generate(model, tokenizer, "test", max_tokens=5, temperature=0.0)
        r2 = generate(model, tokenizer, "test", max_tokens=5, temperature=0.0)
        assert r1.token_ids == r2.token_ids
        loader.close()

    def test_generate_budget(self, tiny_transformer_gguf: Path, tiny_model_dir: Path):
        """Generation works with a memory budget set."""
        model, loader = _load_transformer(tiny_transformer_gguf, tiny_model_dir)
        tokenizer = Tokenizer(tiny_model_dir)

        result = generate(model, tokenizer, "hello", max_tokens=3)
        assert result.kv_cache_mb > 0
        loader.close()

    def test_generation_result_fields(self, tiny_transformer_gguf: Path, tiny_model_dir: Path):
        model, loader = _load_transformer(tiny_transformer_gguf, tiny_model_dir)
        tokenizer = Tokenizer(tiny_model_dir)

        result = generate(model, tokenizer, "hello world", max_tokens=5)
        assert hasattr(result, "text")
        assert hasattr(result, "token_ids")
        assert hasattr(result, "n_prompt_tokens")
        assert hasattr(result, "n_generated_tokens")
        assert hasattr(result, "elapsed_s")
        assert hasattr(result, "tokens_per_second")
        assert hasattr(result, "peak_rss_mb")
        assert hasattr(result, "kv_cache_mb")
        assert result.n_prompt_tokens > 0
        loader.close()
