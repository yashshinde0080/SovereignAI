"""Phase A tests: bounded LRU loader cache + deep prefetch + mask caching.

Builds tiny synthetic per-layer safetensors files in a tmp dir so the tests
run on any machine with no model downloads.
"""
import os
import time
from pathlib import Path

import pytest
import torch
from safetensors.torch import save_file

from app.engines.layerstream.loader import LayerWeightLoader
from app.engines.layerstream.layer_executor import LayerExecutor


@pytest.fixture()
def layer_dir(tmp_path: Path):
    """A split-style dir: embed, 5 layers, norm, lm_head. Each ~small tensor."""
    n_layers = 5
    for name in ["embed", "norm", "lm_head"] + [f"layer_{i}" for i in range(n_layers)]:
        save_file(
            {"weight": torch.randn(8, 8, dtype=torch.float32), "bias": torch.zeros(8)},
            str(tmp_path / f"{name}.safetensors"),
        )
    (tmp_path / "quant_config.json").write_text('{"quant_method": "none", "bits": 16}')
    return tmp_path


def _paths(d: Path, n_layers: int = 5):
    return [str(d / f"layer_{i}.safetensors") for i in range(n_layers)]


def test_loader_evicts_beyond_budget(layer_dir):
    """Non-pinned entries over the byte budget get LRU-evicted."""
    loader = LayerWeightLoader(str(layer_dir), prefetch_depth=1, cache_budget_mb=0.001)
    paths = _paths(layer_dir)
    for p in paths:
        loader.get_weights(p)
    # Budget is tiny (~1KB); only a fraction of the layers can be resident.
    assert len(loader.cpu_cache) < len(paths)
    stats = loader.get_cache_stats()
    assert stats["cached_mb"] <= 0.001 + 1e-6


def test_pinned_paths_never_evicted(layer_dir):
    """embed/norm/lm_head are pinned: they survive even a tiny budget."""
    loader = LayerWeightLoader(
        str(layer_dir), prefetch_depth=1, cache_budget_mb=0.001,
        pinned_paths={str(layer_dir / "embed.safetensors"),
                      str(layer_dir / "norm.safetensors"),
                      str(layer_dir / "lm_head.safetensors")},
    )
    pinned = {str(layer_dir / "embed.safetensors"), str(layer_dir / "norm.safetensors"),
              str(layer_dir / "lm_head.safetensors")}
    for p in pinned:
        loader.get_weights(p)
    for p in _paths(layer_dir):
        loader.get_weights(p)
    for p in pinned:
        assert p in loader.cpu_cache, f"pinned {p} was evicted"


def test_eviction_is_lru(layer_dir):
    """The least-recently-used layer goes first, not an arbitrary one."""
    # Each layer is 8x8 fp32 (256B) + 8 fp32 bias (32B) = 288B. Budget 800B
    # holds ~2 layers, so loading 3 forces exactly one eviction.
    loader = LayerWeightLoader(str(layer_dir), prefetch_depth=1, cache_budget_mb=800 / (1024 ** 2))
    paths = _paths(layer_dir)
    loader.get_weights(paths[0])
    loader.get_weights(paths[1])
    loader.get_weights(paths[2])  # evicts the LRU = layer 0
    resident = set(loader.cpu_cache.keys())
    assert paths[0] not in resident
    assert paths[1] in resident and paths[2] in resident


def test_prefetch_depth_bounds_in_flight(layer_dir):
    """prefetch_async never exceeds prefetch_depth in-flight futures."""
    loader = LayerWeightLoader(str(layer_dir), prefetch_depth=2)
    paths = _paths(layer_dir)
    for p in paths:
        loader.prefetch_async(p)
    # futures dict may hold <= depth entries (completed ones get reaped only
    # on the next prefetch_async/get_weights call)
    assert len(loader.futures) <= 2
    # Consuming all paths still returns every layer's weights correctly
    for p in paths:
        assert "weight" in loader.get_weights(p)


def test_prefetch_async_loads_completed_futures(layer_dir):
    """Completed futures are reaped into the cache on the next call."""
    loader = LayerWeightLoader(str(layer_dir), prefetch_depth=2)
    paths = _paths(layer_dir)
    loader.prefetch_async(paths[0])
    loader.prefetch_async(paths[1])
    # Wait for the futures to complete (poll, don't guess a sleep duration)
    deadline = time.monotonic() + 10
    while not all(f.done() for f in loader.futures.values()) and time.monotonic() < deadline:
        time.sleep(0.01)
    loader.prefetch_async(paths[2])
    # The two completed futures were reaped into the cache
    assert paths[0] in loader.cpu_cache or paths[1] in loader.cpu_cache


def test_get_weights_waits_for_prefetch(layer_dir):
    """get_weights consumes an in-flight future for the same path."""
    loader = LayerWeightLoader(str(layer_dir), prefetch_depth=1)
    p = str(layer_dir / "layer_0.safetensors")
    loader.prefetch_async(p)
    sd = loader.get_weights(p)
    assert "weight" in sd
    assert p not in loader.futures  # consumed


def _mini_exec(layer_dir, **kw):
    return LayerExecutor({"layers": []}, layer_dir, str(layer_dir), "cpu", **kw)


def test_attention_mask_cached(layer_dir):
    """Same (shape, past_length, dtype) returns the same tensor object."""
    exec = _mini_exec(layer_dir)
    m1 = exec._create_attention_mask((1, 1), 5, torch.float32)
    m2 = exec._create_attention_mask((1, 1), 5, torch.float32)
    assert m1 is m2
    # Different past_length -> different mask
    m3 = exec._create_attention_mask((1, 1), 6, torch.float32)
    assert m1 is not m3


def test_attention_mask_cache_bounded(layer_dir):
    """Cache never grows past its cap (64 shapes)."""
    exec = _mini_exec(layer_dir)
    for i in range(80):
        exec._create_attention_mask((1, 1), i, torch.float32)
    assert len(exec._mask_cache) <= 64


def test_pinned_bytes_exempt_from_budget(layer_dir):
    """Pinned bytes don't consume the layer-window budget."""
    pinned = {str(layer_dir / "embed.safetensors")}
    loader = LayerWeightLoader(str(layer_dir), prefetch_depth=1,
                               cache_budget_mb=0.001, pinned_paths=pinned)
    # Load a pinned path (exempt) and force layer evictions (charged to budget)
    loader.get_weights(str(layer_dir / "embed.safetensors"))
    for p in _paths(layer_dir):
        loader.get_weights(p)
    # Budget tracked only non-pinned bytes; pinned stayed resident
    assert str(layer_dir / "embed.safetensors") in loader.cpu_cache
    assert loader._pinned_bytes > 0
    assert loader._cached_bytes <= loader.budget_bytes + 1


def test_layer_executor_constructs_loader_with_budget(layer_dir):
    """LayerExecutor threads prefetch_depth + budget into the loader."""
    exec = _mini_exec(layer_dir, prefetch_depth=4, cache_budget_mb=1.0)
    assert exec.loader.prefetch_depth == 4
    assert exec.loader.budget_bytes == 1.0 * (1024 ** 2)


def test_compute_dtype_gate(monkeypatch, layer_dir):
    """CPU compute dtype: bf16 only on capable CPUs, fp32 otherwise."""
    import app.engines.layerstream.layer_executor as le
    monkeypatch.setattr(le, "_cpu_bf16_capable", lambda: True)
    assert _mini_exec(layer_dir).compute_dtype == torch.bfloat16
    monkeypatch.setattr(le, "_cpu_bf16_capable", lambda: False)
    assert _mini_exec(layer_dir).compute_dtype == torch.float32


def test_splitter_skips_small_tensors():
    """Buffers/small tensors (< 1024 elems) stay fp, never get scale keys."""
    from app.engines.layerstream.splitter import _quantize_int8, _quantize_int4
    big, small = torch.randn(32, 64), torch.randn(16)
    for qf in (_quantize_int8, _quantize_int4):
        q = qf({"big": big, "small": small})
        assert f"big.scale" in q
        assert q["small"].dtype == torch.float32
        assert "small.scale" not in q


def test_int8_device_dequant_matches_cpu():
    """Device dequant is bit-identical to the old CPU path."""
    from app.engines.layerstream.splitter import _quantize_int8
    from app.engines.layerstream.loader import dequantize_on_device
    x = torch.randn(32, 64)
    q = _quantize_int8({"w": x})
    old = q["w"].to(torch.float32) * q["w.scale"]  # legacy CPU dequant
    new = dequantize_on_device(q["w"], q["w.scale"], "cpu", torch.float32, x.shape)
    assert torch.allclose(old, new)


def test_int4_roundtrip():
    """Group-32 int4: packed halved, per-group fp16 scales, NMSE small."""
    from app.engines.layerstream.splitter import _quantize_int4
    from app.engines.layerstream.loader import dequantize_on_device
    torch.manual_seed(0)
    x = torch.randn(64, 128)
    q = _quantize_int4({"w": x})
    packed, scale = q["w"], q["w.scale"]
    assert packed.dtype == torch.uint8
    assert packed.shape == (64, 64)  # cols halved
    assert scale.shape == (64, 4)    # 128 cols / 32 per group
    x_hat = dequantize_on_device(packed, scale, "cpu", torch.float32, x.shape)
    nmse = ((x - x_hat) ** 2).mean() / (x ** 2).mean()
    assert nmse < 0.02


def test_int4_padded_cols_roundtrip():
    """cols % 32 != 0: padding is stripped by dequant via target shape."""
    from app.engines.layerstream.splitter import _quantize_int4
    from app.engines.layerstream.loader import dequantize_on_device
    torch.manual_seed(1)
    x = torch.randn(32, 40)  # numel 1280 >= gate; 40 % 32 = 8 -> padded to 64
    q = _quantize_int4({"w": x})
    packed, scale = q["w"], q["w.scale"]
    assert packed.shape == (32, 32)  # (40+24)/2
    assert scale.shape == (32, 2)    # 64 padded cols / 32
    x_hat = dequantize_on_device(packed, scale, "cpu", torch.float32, x.shape)
    assert x_hat.shape == x.shape
    nmse = ((x - x_hat) ** 2).mean() / (x ** 2).mean()
    assert nmse < 0.02


def test_int4_assign_weights_end_to_end(tmp_path):
    """Packed int4 weights dequantize to the right shape/dtype in assign_weights."""
    from app.engines.layerstream.splitter import _quantize_int4
    torch.manual_seed(2)
    x = torch.randn(32, 64)
    q = _quantize_int4({"w": x})

    class _Mod(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.w = torch.nn.Parameter(torch.zeros(32, 64))

    m = _Mod()
    _mini_exec(tmp_path).assign_weights(m, q)
    assert m.w.shape == (32, 64) and m.w.dtype == torch.float32
    nmse = ((x - m.w.detach()) ** 2).mean() / (x ** 2).mean()
    assert nmse < 0.02


def test_loader_keeps_int8_raw(tmp_path):
    """Phase B: loader stops CPU-dequantizing; int8 + scale stay in RAM."""
    from app.engines.layerstream.splitter import _quantize_int8
    x = torch.randn(32, 64)
    save_file(_quantize_int8({"w": x}), str(tmp_path / "layer_0.safetensors"))
    (tmp_path / "quant_config.json").write_text('{"quant_method": "int8", "bits": 8}')
    loader = LayerWeightLoader(str(tmp_path), prefetch_depth=1)
    out = loader.get_weights(str(tmp_path / "layer_0.safetensors"))
    assert out["w"].dtype == torch.int8
    assert "w.scale" in out
    # and the executor dequantizes on device when assigning
    exec = _mini_exec(tmp_path)
    from app.engines.layerstream.splitter import _quantize_int8 as q8
    class _Mod(torch.nn.Module):
        def __init__(self):
            super().__init__()
            self.w = torch.nn.Parameter(torch.zeros(32, 64))
    m = _Mod()
    exec.assign_weights(m, q8({"w": x}))
    assert m.w.dtype == torch.float32 and m.w.shape == (32, 64)
