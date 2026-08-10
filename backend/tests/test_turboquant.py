"""Tests for the TurboQuant KV cache compression (app.engines.shared.turboquant).

Covers:
- PolarQuant / QJL roundtrips
- Bit-packing of indices (3.5-bit codes into uint32 words) + unpacked fallback
- KV manager roundtrip (shape + reconstruction MSE)
- Incremental hot-buffer update semantics (the O(n^2) requant regression)
- Flush correctness: chunked updates are BIT-EXACT with a one-shot update
  (each token is quantized exactly once; history is never re-quantized)
- Chunk-count bound (O(n / chunk_size))
- Seq-length bookkeeping across chunks and the raw buffer
- Compression ratio > 1 (packed indices) — the real P1 claim
- Edge cases: empty update, get(device=...), update-after-clear, batch > 1
- Default-off config flag (P1)
"""
import math
import torch
import pytest

from app.engines.shared.turboquant import (
    TurboQuantConfig,
    TurboQuantKVCacheManager,
    get_rotation_matrix,
    apply_rotation,
    inverse_rotation,
    get_lloyd_max_centroids,
    quantize_polar,
    get_qjl_projection,
    qjl_encode,
    qjl_decode,
    pack_qjl_bits,
    unpack_qjl_bits,
)
from app.engines.shared.turboquant.kv_cache import pack_indices, unpack_indices, _per_word_for
from app.config import settings


def _kv(batch: int, nh: int, seq: int, hd: int, seed: int = 0):
    g = torch.Generator().manual_seed(seed)
    k = torch.randn(batch, nh, seq, hd, generator=g, dtype=torch.float16)
    v = torch.randn(batch, nh, seq, hd, generator=g, dtype=torch.float16)
    return k, v


class TestPolarQuant:
    def test_roundtrip_mse(self):
        d = 64
        x = torch.randn(200, d)
        x = x / x.norm(dim=-1, keepdim=True)  # unit vectors, PolarQuant's assumption

        R = get_rotation_matrix(d)
        centroids = get_lloyd_max_centroids(d, 3.5)

        x_rot = apply_rotation(x, R)
        _, x_quant = quantize_polar(x_rot, centroids)
        x_recon = inverse_rotation(x_quant, R)

        mse = ((x_recon - x) ** 2).mean().item()
        assert mse < 0.1, f"PolarQuant MSE too high: {mse}"

    def test_centroids_deterministic_and_cached(self):
        c1 = get_lloyd_max_centroids(64, 3.5)
        c2 = get_lloyd_max_centroids(64, 3.5)
        assert torch.equal(c1, c2)
        assert len(c1) == int(2 ** 3.5)  # 11 levels


class TestQJL:
    def test_roundtrip_error_small(self):
        d = 64
        P = get_qjl_projection(d, d)
        residual = torch.randn(100, d) * 0.1
        codes = qjl_encode(residual, P)
        recon = qjl_decode(codes, P)
        err = ((recon - residual) ** 2).mean().item()
        assert err < 0.05, f"QJL MSE too high: {err}"

    def test_decode_applies_tuned_scale(self):
        """Regression pin on the ablation-tuned decode constant c=1/32
        (protects against drift back to the old 1/d' or the textbook
        1/sqrt(d'))."""
        d = 64
        P = get_qjl_projection(d, d)
        codes = (torch.randint(0, 2, (10, d)) * 2 - 1).to(torch.int8)
        expected = codes.to(torch.float32) @ P / 32.0
        assert torch.allclose(qjl_decode(codes, P), expected)




class TestKVCacheManager:
    NH, HD = 4, 32

    def _manager(self, chunk_size: int = 64, **cfg_overrides):
        cfg_kwargs = {"bits_per_coord": 3.5, "enable_qjl": True, "device": "cpu"}
        cfg_kwargs.update(cfg_overrides)
        config = TurboQuantConfig(**cfg_kwargs)
        return TurboQuantKVCacheManager(
            config,
            num_layers=2,
            num_heads=self.NH,
            head_dim=self.HD,
            device="cpu",
            chunk_size=chunk_size,
        )

    def test_roundtrip_shape_and_mse(self):
        mgr = self._manager()
        k, v = _kv(1, self.NH, 64, self.HD)
        mgr.update(0, k, v)
        k_recon, v_recon = mgr.get(0)
        assert k_recon is not None
        assert k_recon.shape == k.shape, f"{k_recon.shape} vs {k.shape}"
        assert v_recon.shape == v.shape
        mse = ((k_recon.float() - k.float()) ** 2).mean().item()
        assert mse < 0.3, f"KV cache K MSE too high: {mse}"

    def test_get_empty_returns_none(self):
        mgr = self._manager()
        assert mgr.get(0) == (None, None)
        assert mgr.get_seq_length(0) == 0

    def test_qjl_tuned_gain_beats_off_at_default_bits(self):
        """The ablation-driven decision, pinned as a test: at the default 3.5
        bits, QJL-on (with the tuned c=1/32 gain) must beat QJL-off on
        reconstruction fidelity. This is the measured property that says
        'keep QJL' - see benchmarks/qjl_ablation.py (attn NMSE 0.275 vs 0.494)."""
        mgr_on = self._manager()  # enable_qjl=True, tuned gain
        mgr_off = self._manager(enable_qjl=False)
        k, v = _kv(1, self.NH, 64, self.HD)
        mgr_on.update(0, k, v)
        mgr_off.update(0, k, v)
        k_on, _ = mgr_on.get(0)
        k_off, _ = mgr_off.get(0)
        mse_on = ((k_on.float() - k.float()) ** 2).mean().item()
        mse_off = ((k_off.float() - k.float()) ** 2).mean().item()
        assert mse_on < mse_off * 0.8, f"QJL-on ({mse_on:.4f}) not beating off ({mse_off:.4f})"

    def test_incremental_matches_single_shot_exactly(self):
        """Chunked hot-buffer updates reconstruct BIT-EXACTLY the same result as
        one big update: each token is quantized exactly once (at flush), so the
        incremental path introduces zero extra error."""
        mgr = self._manager(chunk_size=16)
        mgr_single = self._manager(chunk_size=64)
        k, v = _kv(1, self.NH, 64, self.HD)

        mgr_single.update(0, k, v)  # one-shot -> single 64-token chunk
        step = 16
        for s in range(0, 64, step):  # 4 x 16-token updates -> 4 flushes
            mgr.update(0, k[:, :, s : s + step], v[:, :, s : s + step])

        k_c, v_c = mgr.get(0)
        k_s, v_s = mgr_single.get(0)
        assert k_c.shape == k_s.shape
        assert torch.equal(k_c.float(), k_s.float())
        assert torch.equal(v_c.float(), v_s.float())
        assert mgr.get_seq_length(0) == 64
        assert len(mgr.k_cache[0]) == 4

    def test_update_appends_without_requantizing_history(self):
        """Regression test for the O(n^2) bug: appending must never touch an
        existing chunk. Proven by object identity: the flushed chunk object is
        the SAME object after later updates."""
        mgr = self._manager(chunk_size=8)
        k, v = _kv(1, self.NH, 16, self.HD)
        mgr.update(0, k[:, :, :4], v[:, :, :4])  # buffer 4
        mgr.update(0, k[:, :, 4:8], v[:, :, 4:8])  # buffer 8 -> flush chunk(8)
        first_chunk = mgr.k_cache[0][0]
        mgr.update(0, k[:, :, 8:12], v[:, :, 8:12])  # buffer 4
        mgr.update(0, k[:, :, 12:], v[:, :, 12:])  # buffer 8 -> flush chunk(8)
        assert len(mgr.k_cache[0]) == 2
        assert mgr.k_cache[0][0] is first_chunk  # untouched, not re-quantized
        assert mgr.get_seq_length(0) == 16

    def test_many_flushes_match_single_shot(self):
        """Long run of 1-token updates with chunk_size dividing n (every token
        flushed): quality is bit-exact with one-shot, chunk count stays
        O(n / chunk_size), seq bookkeeping stays correct."""
        n, chunk = 300, 60
        mgr = self._manager(chunk_size=chunk)
        mgr_single = self._manager(chunk_size=n)
        k, v = _kv(1, self.NH, n, self.HD)
        for i in range(n):
            mgr.update(0, k[:, :, i : i + 1], v[:, :, i : i + 1])
        mgr_single.update(0, k, v)

        assert len(mgr.k_cache[0]) == n // chunk  # all flushed, buffer empty
        assert mgr.get_seq_length(0) == n
        k_recon, _ = mgr.get(0)
        assert k_recon.shape == (1, self.NH, n, self.HD)
        k_single, _ = mgr_single.get(0)
        assert torch.equal(k_recon.float(), k_single.float())

    def test_partial_buffer_included_in_get(self):
        """Tokens still in the raw hot buffer (not yet flushed) must be served
        by get() with correct shape and sequence position."""
        mgr = self._manager(chunk_size=16)
        k, v = _kv(1, self.NH, 20, self.HD)
        mgr.update(0, k[:, :, :16], v[:, :, :16])  # flush -> chunk(16)
        mgr.update(0, k[:, :, 16:], v[:, :, 16:])  # buffer 4
        assert mgr.get_seq_length(0) == 20
        k_recon, _ = mgr.get(0)
        assert k_recon.shape == (1, self.NH, 20, self.HD)

    def test_empty_update_is_noop(self):
        mgr = self._manager()
        k, v = _kv(1, self.NH, 0, self.HD)
        mgr.update(0, k, v)
        assert mgr.get(0) == (None, None)
        assert mgr.get_seq_length(0) == 0
        assert mgr.get_size_mb() == 0.0

    def test_get_with_device(self):
        mgr = self._manager()
        k, v = _kv(1, self.NH, 16, self.HD)
        mgr.update(0, k, v)
        dev = torch.device("cpu")
        k_out, v_out = mgr.get(0, device=dev)
        assert k_out is not None and v_out is not None
        assert k_out.device == dev
        assert k_out.shape == k.shape

    def test_update_after_clear(self):
        mgr = self._manager()
        k, v = _kv(1, self.NH, 8, self.HD)
        mgr.update(0, k, v)
        mgr.clear()
        mgr.update(0, k, v)  # reuse after clear
        assert mgr.get_seq_length(0) == 8
        k_recon, _ = mgr.get(0)
        assert k_recon.shape == k.shape

    def test_multiple_layers_are_independent(self):
        mgr = self._manager()
        k, v = _kv(1, self.NH, 16, self.HD)
        mgr.update(0, k, v)
        mgr.update(1, k, v)
        assert mgr.get_seq_length(0) == 16
        assert mgr.get_seq_length(1) == 16
        mgr.clear()
        assert mgr.get_seq_length(0) == 0 and mgr.get_seq_length(1) == 0

    def test_clear_resets(self):
        mgr = self._manager()
        k, v = _kv(1, self.NH, 8, self.HD)
        mgr.update(0, k, v)
        mgr.clear()
        assert mgr.get(0) == (None, None)
        assert mgr.get_seq_length(0) == 0
        assert mgr.get_size_mb() == 0.0

    def test_get_size_mb_counts_chunks_and_buffer(self):
        mgr = self._manager(chunk_size=16)
        k, v = _kv(1, self.NH, 20, self.HD)
        mgr.update(0, k, v)  # flush 16 + 4 in buffer
        assert mgr.get_size_mb() > 0

    def test_compression_ratio_above_3(self):
        """P1: packed indices + 1-bit QJL + fp16 scales put the shipped cache
        at ~3.8x (hd=32); the assert floor of 3x locks in the real win vs the
        old 1.0-1.4x state."""
        mgr = self._manager()
        k, v = _kv(1, self.NH, 64, self.HD)
        mgr.update(0, k, v)
        fp16_bytes = (k.numel() + v.numel()) * 2
        ratio = fp16_bytes / (mgr.get_size_mb() * 1024 * 1024)
        assert ratio > 3.0, f"Compression ratio too low: {ratio:.2f}x"

    def test_compression_ratio_qjl_off(self):
        """With QJL off only the index+scale tax remains: ~4x at hd=32."""
        mgr = self._manager(enable_qjl=False)
        k, v = _kv(1, self.NH, 64, self.HD)
        mgr.update(0, k, v)
        fp16_bytes = (k.numel() + v.numel()) * 2
        ratio = fp16_bytes / (mgr.get_size_mb() * 1024 * 1024)
        assert ratio > 3.5, f"QJL-off ratio too low: {ratio:.2f}x"

    def test_batch_greater_than_one_raises(self):
        mgr = self._manager()
        k, v = _kv(2, self.NH, 8, self.HD)
        with pytest.raises(ValueError):
            mgr.update(0, k, v)

    def test_qjl_disabled_path(self):
        mgr = self._manager(chunk_size=8, enable_qjl=False, bits_per_coord=4.0)
        k, v = _kv(1, self.NH, 16, self.HD)
        mgr.update(0, k, v)
        k_recon, _ = mgr.get(0)
        assert k_recon.shape == k.shape

    def test_qjl_dim_different_from_head_dim(self):
        """qjl_dim != hd exercises the nh*seq*qjl_dim unpack bookkeeping through
        both pack and unpack (codes are packed at qjl_dim width, not hd)."""
        mgr = self._manager(chunk_size=16, qjl_dim=16)  # hd=32
        k, v = _kv(1, self.NH, 20, self.HD)
        mgr.update(0, k, v)
        chunk = mgr.k_cache[0][0]
        assert chunk.packed is True
        assert chunk.k_qjl.dtype == torch.uint32
        k_recon, v_recon = mgr.get(0)
        assert k_recon.shape == k.shape
        assert v_recon.shape == v.shape
        mse = ((k_recon.float() - k.float()) ** 2).mean().item()
        assert mse < 0.3

    def test_default_path_is_packed(self):
        mgr = self._manager()
        k, v = _kv(1, self.NH, 64, self.HD)
        mgr.update(0, k, v)
        chunk = mgr.k_cache[0][0]
        assert chunk.packed is True
        assert chunk.k_indices.dtype == torch.uint32
        assert chunk.k_qjl.dtype == torch.uint32  # 1-bit QJL, 32 codes/word
        assert chunk.k_scale.dtype == torch.float16  # shrunk scales
        assert chunk.levels == 11  # 3.5 bits

    def test_unpacked_fallback_bit_pack_off(self):
        """bit_pack=False restores the legacy layout entirely: uint8 indices,
        int8 QJL codes, float32 scales."""
        mgr = self._manager(bit_pack=False)
        k, v = _kv(1, self.NH, 64, self.HD)
        mgr.update(0, k, v)
        chunk = mgr.k_cache[0][0]
        assert chunk.packed is False
        assert chunk.k_indices.dtype == torch.uint8
        assert chunk.k_qjl.dtype == torch.int8
        # Scales are norms of the fp16 engine input, so fp16 in BOTH paths;
        # the packed path forces it explicitly for fp32 engine inputs.
        assert chunk.k_scale.dtype == torch.float16
        k_recon, _ = mgr.get(0)
        assert k_recon.shape == k.shape
        mse = ((k_recon.float() - k.float()) ** 2).mean().item()
        assert mse < 0.3


class TestBitPacking:
    def test_pack_unpack_roundtrip_padded(self):
        """n not divisible by 9 exercises the zero-pad / trim path."""
        levels, n = 11, 100
        idx = torch.randint(0, levels, (n,))
        packed = pack_indices(idx, levels)
        assert packed.dtype == torch.uint32
        assert packed.numel() == math.ceil(n / 9)
        out = unpack_indices(packed, levels, n)
        assert torch.equal(out, idx)

    def test_pack_unpack_roundtrip_divisible(self):
        levels, n = 11, 9 * 64
        idx = torch.randint(0, levels, (n,))
        packed = pack_indices(idx, levels)
        assert packed.numel() == n // 9
        assert torch.equal(unpack_indices(packed, levels, n), idx)

    def test_per_word_for(self):
        assert _per_word_for(11) == 9  # 3.5 bits: 11^9 < 2^32
        assert _per_word_for(16) == 8  # 4 bits: 16^8 = 2^32 exactly fits
        assert _per_word_for(2) == 32
        assert _per_word_for(1) == 1  # no packing possible

    def test_packed_smaller_than_unpacked(self):
        """Packed uint32 words must beat 1 byte/index for real savings."""
        levels, n = 11, 9 * 64
        idx = torch.randint(0, levels, (n,))
        packed = pack_indices(idx, levels)
        assert packed.numel() * packed.element_size() < n

    def test_qjl_pack_unpack_roundtrip(self):
        """1-bit QJL codes roundtrip losslessly (32 per uint32 word)."""
        n = 100  # not divisible by 32 -> padding path
        codes = (torch.randint(0, 2, (n,)) * 2 - 1).to(torch.int8)
        packed = pack_qjl_bits(codes)
        assert packed.dtype == torch.uint32
        assert packed.numel() == math.ceil(n / 32)
        out = unpack_qjl_bits(packed, n)
        assert out.dtype == torch.int8
        assert torch.equal(out, codes)

    def test_qjl_packed_smaller_than_int8(self):
        """32 codes/word must beat 1 byte/code."""
        n = 32 * 64
        codes = (torch.randint(0, 2, (n,)) * 2 - 1).to(torch.int8)
        packed = pack_qjl_bits(codes)
        assert packed.numel() * packed.element_size() < n

    def test_qjl_pack_divisible(self):
        n = 32 * 4
        codes = (torch.randint(0, 2, (n,)) * 2 - 1).to(torch.int8)
        packed = pack_qjl_bits(codes)
        assert packed.numel() == n // 32
        assert torch.equal(unpack_qjl_bits(packed, n), codes)


class TestAffineScheme:
    """KIVI-style per-channel affine quantizer (config.quant_scheme='affine'):
    K per-(head,dim) scales, V per-(head,token) scales, no rotation/QJL."""

    NH, HD = 4, 32

    def _manager(self, chunk_size: int = 64, **cfg_overrides):
        cfg_kwargs = {"bits_per_coord": 4.0, "quant_scheme": "affine", "device": "cpu"}
        cfg_kwargs.update(cfg_overrides)
        config = TurboQuantConfig(**cfg_kwargs)
        return TurboQuantKVCacheManager(
            config, num_layers=2, num_heads=self.NH, head_dim=self.HD,
            device="cpu", chunk_size=chunk_size,
        )

    def _structured_kv(self, batch: int, nh: int, seq: int, hd: int, seed: int = 0):
        """K with per-channel magnitudes (x20 spread across hd), V with
        per-token magnitudes (x10 spread across seq) — the structure that
        per-channel scales exist for (KIVI's premise)."""
        g = torch.Generator().manual_seed(seed)
        k = torch.randn(batch, nh, seq, hd, generator=g) * torch.linspace(0.1, 2.0, hd).view(1, 1, 1, hd)
        v = torch.randn(batch, nh, seq, hd, generator=g) * torch.linspace(0.2, 2.0, seq).view(1, 1, seq, 1)
        return k, v

    def test_roundtrip_shape_and_nmse(self):
        mgr = self._manager()
        k, v = self._structured_kv(1, self.NH, 64, self.HD)
        mgr.update(0, k, v)
        k_recon, v_recon = mgr.get(0)
        assert k_recon.shape == k.shape and v_recon.shape == v.shape
        nmse_k = ((k_recon - k) ** 2).mean().item() / (k ** 2).mean().item()
        nmse_v = ((v_recon - v) ** 2).mean().item() / (v ** 2).mean().item()
        assert nmse_k < 0.02, f"affine K NMSE too high: {nmse_k:.4f}"
        assert nmse_v < 0.06, f"affine V NMSE too high: {nmse_v:.4f}"

    def test_affine_beats_polar_on_structured_data(self):
        """The KIVI premise pinned: on channel/token-structured data, 4-bit
        affine must beat 4-bit polar (which rotates the structure away) by a
        wide margin on K reconstruction."""
        k, v = self._structured_kv(1, self.NH, 64, self.HD)
        mgr_aff = self._manager()
        mgr_pol = self._manager(quant_scheme="polar", enable_qjl=False)
        mgr_aff.update(0, k, v)
        mgr_pol.update(0, k, v)
        k_aff, _ = mgr_aff.get(0)
        k_pol, _ = mgr_pol.get(0)
        nmse_aff = ((k_aff - k) ** 2).mean().item() / (k ** 2).mean().item()
        nmse_pol = ((k_pol - k) ** 2).mean().item() / (k ** 2).mean().item()
        assert nmse_aff < nmse_pol * 0.5, \
            f"affine {nmse_aff:.4f} not < 0.5x polar {nmse_pol:.4f}"

    def test_incremental_consistent_within_same_chunking(self):
        """Affine scales are per-chunk, so bit-exactness holds for the SAME
        flush boundaries regardless of arrival pattern (4x16 vs 16x4)."""
        mgr_a = self._manager(chunk_size=16)
        mgr_b = self._manager(chunk_size=16)
        k, v = self._structured_kv(1, self.NH, 64, self.HD)
        for s in range(0, 64, 16):
            mgr_a.update(0, k[:, :, s:s + 16], v[:, :, s:s + 16])
        for s in range(0, 64, 4):
            mgr_b.update(0, k[:, :, s:s + 4], v[:, :, s:s + 4])
        ka, va = mgr_a.get(0)
        kb, vb = mgr_b.get(0)
        assert torch.equal(ka.float(), kb.float())
        assert torch.equal(va.float(), vb.float())
        assert len(mgr_a.k_cache[0]) == 4

    def test_chunked_close_to_one_shot(self):
        """Different chunk boundaries shift the per-chunk scales, so NOT
        bit-exact — but quality must stay within 1.5x NMSE of the one-shot
        flush (per-chunk scales from 16 vs 64 tokens are near-equivalent)."""
        mgr_chunked = self._manager(chunk_size=16)
        mgr_one = self._manager(chunk_size=64)
        k, v = self._structured_kv(1, self.NH, 64, self.HD)
        for s in range(0, 64, 16):
            mgr_chunked.update(0, k[:, :, s:s + 16], v[:, :, s:s + 16])
        mgr_one.update(0, k, v)
        k_c, _ = mgr_chunked.get(0)
        k_o, _ = mgr_one.get(0)
        nmse_c = ((k_c - k) ** 2).mean().item() / (k ** 2).mean().item()
        nmse_o = ((k_o - k) ** 2).mean().item() / (k ** 2).mean().item()
        assert nmse_c < nmse_o * 1.5 + 1e-6

    def test_scale_shapes_and_packing(self):
        mgr = self._manager(chunk_size=16)
        k, v = self._structured_kv(1, self.NH, 16, self.HD)
        mgr.update(0, k, v)
        kc, vc = mgr.k_cache[0][0], mgr.v_cache[0][0]
        assert kc.scheme == "affine" and vc.scheme == "affine"
        assert kc.k_scale.shape == (self.NH, 1, self.HD)   # per-channel
        assert vc.k_scale.shape == (self.NH, 16, 1)        # per-token
        assert kc.levels == 16  # 4 bits
        assert kc.packed is True and kc.k_indices.dtype == torch.uint32
        assert kc.k_scale.dtype == torch.float16

    def test_odd_levels_3_5_bits(self):
        mgr = self._manager(bits_per_coord=3.5)
        k, v = self._structured_kv(1, self.NH, 64, self.HD)
        mgr.update(0, k, v)
        assert mgr.k_cache[0][0].levels == 11  # int(2**3.5)
        k_recon, _ = mgr.get(0)
        assert k_recon.shape == k.shape
        nmse = ((k_recon - k) ** 2).mean().item() / (k ** 2).mean().item()
        assert nmse < 0.06

    def test_asymmetric_kv_bits(self):
        """KIVI-style asymmetric budgets: k_bits=3 (8 levels) + v_bits=5 (32
        levels) flow into the per-entry levels and pack/unpack correctly."""
        mgr = self._manager(bits_per_coord=4.0, k_bits=3.0, v_bits=5.0)
        k, v = self._structured_kv(1, self.NH, 64, self.HD)
        mgr.update(0, k, v)
        assert mgr.k_cache[0][0].levels == 8
        assert mgr.v_cache[0][0].levels == 32
        k_recon, v_recon = mgr.get(0)
        assert k_recon.shape == k.shape and v_recon.shape == v.shape

    def test_compression_ratio_above_3(self):
        """4-bit affine: ~3.7x at hd=32 (indices 8/word + fp16 scales)."""
        mgr = self._manager()
        k, v = self._structured_kv(1, self.NH, 64, self.HD)
        mgr.update(0, k, v)
        fp16_bytes = (k.numel() + v.numel()) * 2
        ratio = fp16_bytes / (mgr.get_size_mb() * 1024 * 1024)
        assert ratio > 3.0, f"affine ratio too low: {ratio:.2f}x"

    def test_no_requant_identity(self):
        """Same invariant as polar: flushed chunks are never re-quantized by
        later updates (object identity)."""
        mgr = self._manager(chunk_size=8)
        k, v = self._structured_kv(1, self.NH, 16, self.HD)
        mgr.update(0, k[:, :, :8], v[:, :, :8])
        first = mgr.k_cache[0][0]
        mgr.update(0, k[:, :, 8:], v[:, :, 8:])
        assert mgr.k_cache[0][0] is first

    def test_default_scheme_is_polar(self):
        assert TurboQuantConfig().quant_scheme == "polar"
        assert TurboQuantConfig().k_bits is None and TurboQuantConfig().v_bits is None


class TestConfigDefault:
    def test_turboquant_defaults_off(self):
        """P1: the feature must be off by default until the 6x claim is validated."""
        assert settings.turboquant_enabled is False

    def test_bit_pack_defaults_on(self):
        assert TurboQuantConfig().bit_pack is True
