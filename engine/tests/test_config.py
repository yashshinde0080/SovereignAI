"""Tests for model configuration."""

import json
from pathlib import Path

import pytest

from engine.config import ModelConfig


class TestModelConfig:
    def test_defaults(self):
        cfg = ModelConfig()
        assert cfg.vocab_size == 32000
        assert cfg.n_layers == 22
        assert cfg.n_heads == 32
        assert cfg.dim == 2048
        assert cfg.norm_eps == 1e-5

    def test_head_dim(self):
        cfg = ModelConfig(dim=4096, n_heads=32)
        assert cfg.head_dim == 128

    def test_kv_dim_gqa(self):
        cfg = ModelConfig(dim=4096, n_heads=32, n_kv_heads=8)
        assert cfg.kv_dim == 1024

    def test_from_json(self, tiny_model_dir: Path):
        cfg = ModelConfig.from_json(tiny_model_dir / "config.json")
        assert cfg.vocab_size == 256
        assert cfg.n_layers == 2
        assert cfg.dim == 16
        assert cfg.n_heads == 4

    def test_from_gguf_metadata(self):
        meta = {
            "llama.embedding_length": 4096,
            "llama.block_count": 32,
            "llama.attention.head_count": 32,
            "llama.attention.head_count_kv": 8,
            "llama.feed_forward_length": 11008,
            "llama.attention.layer_norm_rms_epsilon": 1e-5,
            "llama.rope.freq_base": 10000.0,
            "llama.context_length": 4096,
        }
        cfg = ModelConfig.from_gguf_metadata(meta)
        assert cfg.dim == 4096
        assert cfg.n_layers == 32
        assert cfg.n_kv_heads == 8
        assert cfg.hidden_dim == 11008

    def test_smart_loader_prefers_json(self, tiny_model_dir: Path):
        cfg = ModelConfig.load(tiny_model_dir)
        # Should use config.json values
        assert cfg.vocab_size == 256
        assert cfg.n_layers == 2

    def test_smart_loader_fallback_to_gguf(self, tmp_path: Path):
        meta = {"llama.embedding_length": 64, "llama.block_count": 4}
        cfg = ModelConfig.load(tmp_path, gguf_metadata=meta)
        assert cfg.dim == 64
        assert cfg.n_layers == 4

    def test_smart_loader_defaults(self, tmp_path: Path):
        cfg = ModelConfig.load(tmp_path)
        # No config.json, no GGUF metadata → all defaults
        assert cfg.vocab_size == 32000

    def test_str(self):
        cfg = ModelConfig()
        s = str(cfg)
        assert "vocab=32000" in s
        assert "layers=22" in s

    def test_type_coercion(self, tmp_path: Path):
        """Config fields accept int for float fields and vice versa."""
        d = tmp_path / "coerce"
        d.mkdir()
        cfg_data = {
            "hidden_size": 1024.0,  # float where int expected
            "rms_norm_eps": 1,  # int where float expected
        }
        (d / "config.json").write_text(json.dumps(cfg_data))
        cfg = ModelConfig.from_json(d / "config.json")
        assert cfg.dim == 1024
        assert cfg.norm_eps == 1.0

    def test_partial_config(self, tmp_path: Path):
        """Config with only some fields set."""
        d = tmp_path / "partial"
        d.mkdir()
        (d / "config.json").write_text(json.dumps({"vocab_size": 50000}))
        cfg = ModelConfig.from_json(d / "config.json")
        assert cfg.vocab_size == 50000
        assert cfg.n_layers == 22  # default
