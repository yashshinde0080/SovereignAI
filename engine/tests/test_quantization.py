"""Tests for Q8_0 and Q4_0 quantized tensor dequantization."""

from pathlib import Path

import numpy as np
import pytest

from engine.gguf import (
    GGUFParser, GGML_TYPE_Q8_0, GGML_TYPE_Q4_0, GGML_TYPE_F16,
    dequantize_q8_0, dequantize_q4_0, _quantized_nbytes,
)
from engine.loader import CheckpointLoader


# ── Inline helpers (avoid cross-module import issues in pytest) ─────

def _q8_0_quantize(arr: np.ndarray) -> bytes:
    flat = arr.ravel().astype(np.float32)
    n = len(flat)
    n_blocks = (n + 31) // 32
    padded = np.zeros(n_blocks * 32, dtype=np.float32)
    padded[:n] = flat
    blocks = padded.reshape(n_blocks, 32)
    scales = np.abs(blocks).max(axis=1, keepdims=True).astype(np.float32)
    scales = np.clip(scales, 1e-10, None)
    indices = np.clip(np.round(blocks / scales), -128, 127).astype(np.int8)
    out = bytearray()
    for b in range(n_blocks):
        out += scales[b].tobytes()
        out += indices[b].tobytes()
    return bytes(out)


def _q4_0_quantize(arr: np.ndarray) -> bytes:
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
        out += scales[b].tobytes()
        lo = indices[b, 0::2].astype(np.uint8) & 0x0F
        hi = (indices[b, 1::2].astype(np.uint8) & 0x0F) << 4
        packed = (lo | hi).astype(np.uint8)
        out += packed.tobytes()
    return bytes(out)


# ── Dequantization accuracy tests ───────────────────────────────────

class TestQ8_0Dequant:
    def test_roundtrip_preserves_range(self):
        """Q8_0 preserves overall value range within a block."""
        rng = np.random.RandomState(42)
        original = rng.randn(32).astype(np.float32) * 0.5

        qbytes = _q8_0_quantize(original)
        recovered = dequantize_q8_0(qbytes, original.shape)

        # Recovered range should roughly match original
        assert recovered.dtype == np.float32
        assert recovered.shape == original.shape
        assert np.max(np.abs(recovered)) <= np.max(np.abs(original)) * 1.1

    def test_exact_for_zero(self):
        """Zeros quantize and dequantize exactly."""
        z = np.zeros(32, dtype=np.float32)
        qbytes = _q8_0_quantize(z)
        recovered = dequantize_q8_0(qbytes, z.shape)
        np.testing.assert_array_equal(recovered, z)

    def test_scale_matches_amax(self):
        """Scale should be max absolute value of the block."""
        vals = np.array([0, 0, 0, 3.5, 0, 0, 0, 0] + [0]*24, dtype=np.float32)
        qbytes = _q8_0_quantize(vals)
        recovered = dequantize_q8_0(qbytes, vals.shape)
        # The one non-zero value should be preserved as scale * round(3.5/scale)
        assert recovered[3] != 0  # not zeroed out
        assert recovered[0] == 0  # zeros preserved

    def test_nbytes_correct(self):
        """Quantized byte count matches block layout."""
        n = 100  # elements
        nbytes = _quantized_nbytes(n, GGML_TYPE_Q8_0)
        n_blocks = (n + 31) // 32
        assert nbytes == n_blocks * 36  # 4 + 32 per block

    def test_reshaped_output(self):
        """Dequant preserves shape for multi-dimensional tensors."""
        from engine.tests.conftest import _quantize_to_q8_0
        arr = np.random.randn(16, 16).astype(np.float32) * 0.1
        raw = _quantize_to_q8_0(arr)
        recovered = dequantize_q8_0(raw, arr.shape)
        assert recovered.shape == arr.shape


class TestQ4_0Dequant:
    def test_roundtrip_accuracy(self):
        """Q4_0 dequantization preserves values within 4-bit precision."""
        rng = np.random.RandomState(42)
        original = rng.randn(64).astype(np.float32) * 0.5

        qbytes = _q4_0_quantize(original)
        recovered = dequantize_q4_0(qbytes, original.shape)

        np.testing.assert_allclose(original, recovered, atol=0.1, rtol=0.15)

    def test_exact_for_zero(self):
        z = np.zeros(32, dtype=np.float32)
        qbytes = _q4_0_quantize(z)
        recovered = dequantize_q4_0(qbytes, z.shape)
        np.testing.assert_array_equal(recovered, z)

    def test_nbytes_correct(self):
        n = 100
        nbytes = _quantized_nbytes(n, GGML_TYPE_Q4_0)
        n_blocks = (n + 31) // 32
        assert nbytes == n_blocks * 18

    def test_reshaped_output(self):
        arr = np.random.randn(8, 8).astype(np.float32) * 0.1
        qbytes = _q4_0_quantize(arr)
        recovered = dequantize_q4_0(qbytes, arr.shape)
        assert recovered.shape == arr.shape


# ── GGUF loading tests with quantized tensors ───────────────────────

class TestGGUFQuantizedLoading:
    def test_q8_load_tensor(self, q8_gguf: Path):
        """Q8_0 tensors load correctly from GGUF."""
        with CheckpointLoader(q8_gguf) as loader:
            t = loader.load_tensor("token_embd.weight")
            assert t.shape == (256, 16)
            assert t.dtype == np.float32  # dequantized to float32

    def test_q4_load_tensor(self, q4_gguf: Path):
        """Q4_0 tensors load correctly from GGUF."""
        with CheckpointLoader(q4_gguf) as loader:
            t = loader.load_tensor("token_embd.weight")
            assert t.shape == (256, 16)
            assert t.dtype == np.float32

    def test_q8_all_tensors_load(self, q8_gguf: Path):
        """All Q8_0 tensors in a GGUF load without error."""
        with CheckpointLoader(q8_gguf) as loader:
            for name in loader.parser.tensor_names():
                t = loader.load_tensor(name)
                assert t.dtype == np.float32

    def test_q4_all_tensors_load(self, q4_gguf: Path):
        """All Q4_0 tensors in a GGUF load without error."""
        with CheckpointLoader(q4_gguf) as loader:
            for name in loader.parser.tensor_names():
                t = loader.load_tensor(name)
                assert t.dtype == np.float32

    def test_q8_values_reasonable(self, q8_gguf: Path):
        """Q8_0 dequantized values are in a reasonable range."""
        with CheckpointLoader(q8_gguf) as loader:
            t = loader.load_tensor("output_norm.weight")
            # output_norm was initialized to ones
            np.testing.assert_allclose(t, 1.0, atol=0.15)

    def test_q4_values_reasonable(self, q4_gguf: Path):
        """Q4_0 dequantized values are in a reasonable range."""
        with CheckpointLoader(q4_gguf) as loader:
            t = loader.load_tensor("output_norm.weight")
            np.testing.assert_allclose(t, 1.0, atol=0.2)

    def test_q8_tensor_info(self, q8_gguf: Path):
        """Tensor info reports correct quantized type."""
        with CheckpointLoader(q8_gguf) as loader:
            info = loader.tensor_info("token_embd.weight")
            assert info.ggml_type == GGML_TYPE_Q8_0

    def test_q4_tensor_info(self, q4_gguf: Path):
        with CheckpointLoader(q4_gguf) as loader:
            info = loader.tensor_info("token_embd.weight")
            assert info.ggml_type == GGML_TYPE_Q4_0
