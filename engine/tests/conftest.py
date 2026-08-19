"""Shared test fixtures.

Creates tiny synthetic model files for fast unit tests.
No real model download needed.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest
import numpy as np


# ── Synthetic GGUF builder ──────────────────────────────────────────

ALIGNMENT = 32
GGML_TYPE_F16 = 1


def _write_gguf_string(f, s: str) -> None:
    b = s.encode("utf-8")
    f.write(struct.pack("<Q", len(b)))
    f.write(b)


def _write_gguf_value(f, v) -> None:
    if isinstance(v, bool):
        f.write(struct.pack("<I", 7))
        f.write(struct.pack("<B", int(v)))
    elif isinstance(v, int):
        f.write(struct.pack("<I", 4))
        f.write(struct.pack("<I", v))
    elif isinstance(v, float):
        f.write(struct.pack("<I", 6))
        f.write(struct.pack("<f", v))
    elif isinstance(v, str):
        f.write(struct.pack("<I", 8))
        _write_gguf_string(f, v)
    else:
        raise ValueError(f"Unsupported type: {type(v)}")


def _align(pos: int) -> int:
    return ((pos + ALIGNMENT - 1) // ALIGNMENT) * ALIGNMENT


def _estimate_header_size(
    tensor_names: list[tuple[str, list[int]]],
    kv_pairs: list[tuple[str, Any]],
) -> int:
    """Estimate the header size for a GGUF file."""
    size = 24  # magic + version + n_tensors + n_kv

    for key, val in kv_pairs:
        key_b = key.encode()
        size += 8 + len(key_b)  # string key
        # Value type tag + value
        if isinstance(val, int):
            size += 4 + 4
        elif isinstance(val, float):
            size += 4 + 4
        elif isinstance(val, str):
            val_b = val.encode()
            size += 4 + 8 + len(val_b)

    for name, shape in tensor_names:
        name_b = name.encode()
        size += 8 + len(name_b)  # string
        size += 8                # ndims
        size += len(shape) * 8   # dims
        size += 4                # type
        size += 8                # offset

    return size


def build_tiny_gguf(
    path: Path,
    n_layers: int = 2,
    dim: int = 16,
    n_heads: int = 4,
    n_kv_heads: int = 4,
    hidden_dim: int = 32,
    vocab_size: int = 256,
) -> None:
    """Build a complete tiny transformer GGUF file with F16 tensors.

    Includes all weights needed for a full forward pass and
    architecture metadata so ModelConfig loads correctly.
    """
    # Build tensor list with shapes
    tensor_specs: list[tuple[str, list[int]]] = [
        ("token_embd.weight", [vocab_size, dim]),
        ("output_norm.weight", [dim]),
        ("output.weight", [vocab_size, dim]),
    ]

    head_dim = dim // n_heads
    kv_dim = n_kv_heads * head_dim

    for i in range(n_layers):
        tensor_specs.extend([
            (f"blk.{i}.attn_norm.weight", [dim]),
            (f"blk.{i}.attn_q.weight", [n_heads * head_dim, dim]),
            (f"blk.{i}.attn_k.weight", [kv_dim, dim]),
            (f"blk.{i}.attn_v.weight", [kv_dim, dim]),
            (f"blk.{i}.attn_output.weight", [dim, n_heads * head_dim]),
            (f"blk.{i}.ffn_norm.weight", [dim]),
            (f"blk.{i}.ffn_gate.weight", [hidden_dim, dim]),
            (f"blk.{i}.ffn_up.weight", [hidden_dim, dim]),
            (f"blk.{i}.ffn_down.weight", [dim, hidden_dim]),
        ])

    # Architecture metadata for ModelConfig
    kv_pairs = [
        ("general.alignment", 32),
        ("general.architecture", "llama"),
        ("llama.attention.head_count", n_heads),
        ("llama.attention.head_count_kv", n_kv_heads),
        ("llama.attention.layer_norm_rms_epsilon", 1e-5),
        ("llama.block_count", n_layers),
        ("llama.context_length", 128),
        ("llama.embedding_length", dim),
        ("llama.feed_forward_length", hidden_dim),
        ("llama.rope.freq_base", 10000.0),
    ]

    # Compute header size and data layout
    header_end = _estimate_header_size(tensor_specs, kv_pairs)
    data_start = _align(header_end)

    # Compute tensor data offsets
    tensor_info = []
    data_pos = data_start
    for name, shape in tensor_specs:
        nbytes = int(np.prod(shape)) * 2  # F16 = 2 bytes
        offset = _align(data_pos)
        tensor_info.append((name, shape, GGML_TYPE_F16, offset))
        data_pos = offset + nbytes

    # Write the file
    with open(path, "wb") as f:
        # Header
        f.write(struct.pack("<I", 0x46554747))  # magic
        f.write(struct.pack("<I", 3))            # version
        f.write(struct.pack("<Q", len(tensor_info)))  # n_tensors
        f.write(struct.pack("<Q", len(kv_pairs)))  # n_kv

        # KV pairs
        for key, val in kv_pairs:
            _write_gguf_string(f, key)
            _write_gguf_value(f, val)

        # Tensor info
        for name, shape, ggml_type, offset in tensor_info:
            _write_gguf_string(f, name)
            f.write(struct.pack("<Q", len(shape)))
            for d in shape:
                f.write(struct.pack("<Q", d))
            f.write(struct.pack("<I", ggml_type))
            f.write(struct.pack("<Q", offset))

        # Pad to data_start
        cur = f.tell()
        if cur < data_start:
            f.write(b"\x00" * (data_start - cur))

        # Tensor data (random F16 values for realistic weights)
        rng = np.random.RandomState(42)
        for name, shape, _, offset in tensor_info:
            cur = f.tell()
            if cur < offset:
                f.write(b"\x00" * (offset - cur))
            arr = rng.randn(*shape).astype(np.float16) * 0.02
            f.write(arr.tobytes())


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def tiny_gguf(tmp_path: Path) -> Path:
    """Create a tiny synthetic GGUF file."""
    path = tmp_path / "tiny.gguf"
    build_tiny_gguf(path)
    return path


@pytest.fixture
def tiny_transformer_gguf(tmp_path: Path) -> Path:
    """Create a complete tiny transformer GGUF with all layer weights."""
    path = tmp_path / "tiny_transformer.gguf"
    build_tiny_gguf(path, n_layers=2, dim=16, n_heads=4, n_kv_heads=4,
                    hidden_dim=32, vocab_size=256)
    return path


@pytest.fixture
def tiny_model_dir(tmp_path: Path) -> Path:
    """Create a directory with config.json + tokenizer files."""
    d = tmp_path / "tiny_model"
    d.mkdir()

    # config.json — must match the GGUF dimensions
    config = {
        "vocab_size": 256,
        "num_hidden_layers": 2,
        "num_attention_heads": 4,
        "num_key_value_heads": 4,
        "hidden_size": 16,
        "intermediate_size": 32,
        "rms_norm_eps": 1e-5,
        "rope_theta": 10000.0,
        "max_position_embeddings": 128,
    }
    (d / "config.json").write_text(json.dumps(config))

    # vocab.json — only IDs 0..255 (matching vocab_size=256)
    vocab = {f"tok_{i}": i for i in range(256)}
    # Add common words mapped to IDs within range
    vocab["hello"] = 100
    vocab["world"] = 101
    vocab[" "] = 10
    vocab["!"] = 11
    (d / "vocab.json").write_text(json.dumps(vocab))

    # merges.txt
    merges = [
        "#version: 0.2",
        "h e",
        "l l",
        "o w",
        "w o",
        "o r",
        "r l",
        "l d",
        "h el",
        "el l",
        "ll o",
        "wo rld",
        "he llo",
    ]
    (d / "merges.txt").write_text("\n".join(merges))

    # tokenizer_config.json
    tok_cfg = {
        "eos_token": "!",
        "bos_token": "tok_0",
        "pad_token": "tok_0",
    }
    (d / "tokenizer_config.json").write_text(json.dumps(tok_cfg))

    return d


# ── Quantized GGUF builder ─────────────────────────────────────────

GGML_TYPE_Q8_0 = 8
GGML_TYPE_Q4_0 = 2
GGML_TYPE_F16 = 1


def _quantize_to_q8_0(arr: np.ndarray) -> bytes:
    """Quantize a flat float32 array to Q8_0 blocks."""
    flat = arr.ravel().astype(np.float32)
    n = len(flat)
    n_blocks = (n + 31) // 32
    # Pad to block boundary
    padded = np.zeros(n_blocks * 32, dtype=np.float32)
    padded[:n] = flat
    blocks = padded.reshape(n_blocks, 32)

    scales = np.abs(blocks).max(axis=1, keepdims=True).astype(np.float32)
    scales = np.clip(scales, 1e-10, None)
    indices = np.clip(np.round(blocks / scales), -128, 127).astype(np.int8)

    out = bytearray()
    for b in range(n_blocks):
        out += scales[b].tobytes()       # fp32 scale
        out += indices[b].tobytes()      # 32 × int8
    return bytes(out)


def _quantize_to_q4_0(arr: np.ndarray) -> bytes:
    """Quantize a flat float32 array to Q4_0 blocks."""
    flat = arr.ravel().astype(np.float32)
    n = len(flat)
    n_blocks = (n + 31) // 32
    padded = np.zeros(n_blocks * 32, dtype=np.float32)
    padded[:n] = flat
    blocks = padded.reshape(n_blocks, 32)

    amax = np.abs(blocks).max(axis=1, keepdims=True)
    scales_f32 = np.clip(amax / 8.0, 1e-10, None).astype(np.float32)
    scales = scales_f32.astype(np.float16)
    with np.errstate(divide="ignore", invalid="ignore"):
        indices = np.clip(np.round(blocks / scales_f32), -8, 7).astype(np.int8)

    out = bytearray()
    for b in range(n_blocks):
        out += scales[b].tobytes()       # fp16 scale
        lo = indices[b, 0::2].astype(np.uint8) & 0x0F
        hi = (indices[b, 1::2].astype(np.uint8) & 0x0F) << 4
        packed = (lo | hi).astype(np.uint8)
        out += packed.tobytes()          # 16 packed bytes
    return bytes(out)


def build_quantized_gguf(
    path: Path,
    quant_type: int = GGML_TYPE_Q8_0,
    n_layers: int = 2,
    dim: int = 16,
    vocab_size: int = 256,
) -> None:
    """Build a GGUF with quantized tensors (Q8_0 or Q4_0)."""
    rng = np.random.RandomState(42)

    # All tensors as flat arrays for easy quantization
    tensors_raw = []
    tensors_raw.append(("token_embd.weight", [vocab_size, dim],
                        rng.randn(vocab_size, dim).astype(np.float32) * 0.02))
    tensors_raw.append(("output_norm.weight", [dim],
                        np.ones(dim, dtype=np.float32)))
    tensors_raw.append(("output.weight", [vocab_size, dim],
                        rng.randn(vocab_size, dim).astype(np.float32) * 0.02))
    for i in range(n_layers):
        tensors_raw.append((f"blk.{i}.attn_norm.weight", [dim],
                            np.ones(dim, dtype=np.float32)))
        tensors_raw.append((f"blk.{i}.ffn_down.weight", [dim, dim],
                            rng.randn(dim, dim).astype(np.float32) * 0.02))

    # Quantize each tensor
    quantized = []
    for name, shape, arr in tensors_raw:
        if quant_type == GGML_TYPE_Q8_0:
            qbytes = _quantize_to_q8_0(arr)
        else:
            qbytes = _quantize_to_q4_0(arr)
        quantized.append((name, shape, quant_type, qbytes))

    # Build KV pairs
    kv_pairs = [("general.alignment", 32)]

    # Estimate header size
    header_end = _estimate_header_size(
        [(n, s) for n, s, _, _ in quantized], kv_pairs
    )
    data_start = _align(header_end)

    # Compute offsets
    tensor_info = []
    data_pos = data_start
    for name, shape, qtype, qbytes in quantized:
        offset = _align(data_pos)
        tensor_info.append((name, shape, qtype, offset, qbytes))
        data_pos = offset + len(qbytes)

    with open(path, "wb") as f:
        f.write(struct.pack("<I", 0x46554747))  # magic
        f.write(struct.pack("<I", 3))            # version
        f.write(struct.pack("<Q", len(tensor_info)))  # n_tensors
        f.write(struct.pack("<Q", len(kv_pairs)))  # n_kv

        for key, val in kv_pairs:
            _write_gguf_string(f, key)
            _write_gguf_value(f, val)

        for name, shape, qtype, offset, qbytes in tensor_info:
            _write_gguf_string(f, name)
            f.write(struct.pack("<Q", len(shape)))
            for d in shape:
                f.write(struct.pack("<Q", d))
            f.write(struct.pack("<I", qtype))
            f.write(struct.pack("<Q", offset))

        cur = f.tell()
        if cur < data_start:
            f.write(b"\x00" * (data_start - cur))

        for name, shape, qtype, offset, qbytes in tensor_info:
            cur = f.tell()
            if cur < offset:
                f.write(b"\x00" * (offset - cur))
            f.write(qbytes)


@pytest.fixture
def q8_gguf(tmp_path: Path) -> Path:
    """Create a GGUF file with Q8_0 quantized tensors."""
    path = tmp_path / "q8.gguf"
    build_quantized_gguf(path, quant_type=GGML_TYPE_Q8_0)
    return path


@pytest.fixture
def q4_gguf(tmp_path: Path) -> Path:
    """Create a GGUF file with Q4_0 quantized tensors."""
    path = tmp_path / "q4.gguf"
    build_quantized_gguf(path, quant_type=GGML_TYPE_Q4_0)
    return path
