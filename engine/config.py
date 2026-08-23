"""Model configuration.

Loads transformer architecture parameters from config.json or GGUF
metadata. All fields have sensible defaults for common models.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# ── Common config field mappings ─────────────────────────────────────
# Maps HuggingFace config.json keys → our field names
_HF_KEY_MAP = {
    "hidden_size": "dim",
    "num_hidden_layers": "n_layers",
    "num_attention_heads": "n_heads",
    "num_key_value_heads": "n_kv_heads",
    "intermediate_size": "hidden_dim",
    "rms_norm_eps": "norm_eps",
    "rope_theta": "rope_theta",
    "max_position_embeddings": "max_position_embeddings",
    "vocab_size": "vocab_size",
    "rope_scaling": "rope_scaling",
}

# Maps GGUF metadata keys → our field names
_GGUF_KEY_MAP = {
    "llama.embedding_length": "dim",
    "llama.block_count": "n_layers",
    "llama.attention.head_count": "n_heads",
    "llama.attention.head_count_kv": "n_kv_heads",
    "llama.feed_forward_length": "hidden_dim",
    "llama.attention.layer_norm_rms_epsilon": "norm_eps",
    "llama.rope.freq_base": "rope_theta",
    "llama.context_length": "max_position_embeddings",
}


@dataclass
class ModelConfig:
    """Transformer model configuration with sane defaults."""

    vocab_size: int = 32000
    n_layers: int = 22
    n_heads: int = 32
    n_kv_heads: int = 32
    dim: int = 2048
    hidden_dim: int = 5632
    norm_eps: float = 1e-5
    rope_theta: float = 10000.0
    max_position_embeddings: int = 2048
    rope_scaling: dict[str, Any] | None = None

    @property
    def head_dim(self) -> int:
        return self.dim // self.n_heads

    @property
    def kv_dim(self) -> int:
        return self.dim // self.n_heads * self.n_kv_heads

    def __str__(self) -> str:
        return (
            f"ModelConfig(vocab={self.vocab_size}, layers={self.n_layers}, "
            f"heads={self.n_heads}/{self.n_kv_heads}kv, dim={self.dim}, "
            f"hidden={self.hidden_dim}, ctx={self.max_position_embeddings})"
        )

    @classmethod
    def from_json(cls, path: str | Path) -> ModelConfig:
        """Load from HuggingFace config.json."""
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)
        return cls._from_dict(raw, _HF_KEY_MAP)

    @classmethod
    def from_gguf_metadata(cls, metadata: dict[str, Any]) -> ModelConfig:
        """Load from GGUF header metadata KV pairs."""
        return cls._from_dict(metadata, _GGUF_KEY_MAP)

    @classmethod
    def load(cls, model_dir: str | Path, gguf_metadata: dict[str, Any] | None = None) -> ModelConfig:
        """Smart loader: tries config.json, falls back to GGUF metadata, then defaults."""
        model_dir = Path(model_dir)

        # If model_dir is a file (GGUF), look in parent directory
        if model_dir.is_file():
            model_dir = model_dir.parent

        config_path = model_dir / "config.json"
        if config_path.exists():
            cfg = cls.from_json(config_path)
            # GGUF metadata overrides where available
            if gguf_metadata:
                for gguf_key, field_name in _GGUF_KEY_MAP.items():
                    if gguf_key in gguf_metadata:
                        val = gguf_metadata[gguf_key]
                        if hasattr(cfg, field_name):
                            current = getattr(cfg, field_name)
                            # Only override if types match or are compatible
                            if type(val) is type(current) or (
                                isinstance(val, (int, float)) and isinstance(current, (int, float))
                            ):
                                setattr(cfg, field_name, val)
            return cfg

        if gguf_metadata:
            return cls.from_gguf_metadata(gguf_metadata)

        return cls()  # all defaults

    @classmethod
    def _from_dict(cls, data: dict[str, Any], key_map: dict[str, str]) -> ModelConfig:
        """Build config from a dict using a key mapping."""
        kwargs: dict[str, Any] = {}
        for src_key, field_name in key_map.items():
            if src_key in data:
                val = data[src_key]
                # Type coercion for common mismatches
                field_type = type(getattr(cls, field_name, None))
                if field_type is int and isinstance(val, (int, float)):
                    kwargs[field_name] = int(val)
                elif field_type is float and isinstance(val, (int, float)):
                    kwargs[field_name] = float(val)
                else:
                    kwargs[field_name] = val
        return cls(**kwargs)


def demo():
    """Print config from a model directory."""
    import sys
    if len(sys.argv) < 2:
        print("usage: python -m engine.config <model_dir>")
        print("config: module loads OK")
        return
    cfg = ModelConfig.load(sys.argv[1])
    print(cfg)


if __name__ == "__main__":
    demo()
