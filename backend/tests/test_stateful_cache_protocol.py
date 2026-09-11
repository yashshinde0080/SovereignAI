"""StatefulCache must satisfy the transformers 5.x hybrid cache protocol.

Regression for the 2026-09-11 breakage: transformers 5.x Qwen3_5 reads
``cache.has_previous_state(layer_idx)`` as a METHOD (4.x used a property),
reads state via ``cache.layers[i].conv_states / .recurrent_states``, and
writes via ``cache.update_conv_state / update_recurrent_state``. The old
4.x-only shape raised ``TypeError: 'bool' object is not callable`` mid-
generation on every hybrid (Qwen3.5) LayerStream request.

These tests replay the exact call sequence modeling_qwen3_5 makes, using
Qwen3.5-0.8B's real layer_types (3 linear + 1 full, repeated).
"""
import torch

from app.engines.layerstream.kv_cache import StatefulCache

LAYER_TYPES = [
    "linear_attention", "linear_attention", "linear_attention", "full_attention",
] * 2  # 8 layers, same 3:1 pattern as Qwen3.5-0.8B


def _cache():
    return StatefulCache(num_layers=len(LAYER_TYPES), layer_types=list(LAYER_TYPES))


def test_has_previous_state_is_callable_with_layer_idx():
    """5.x: method taking layer_idx. Breaks as property (bool not callable)."""
    cache = _cache()
    assert callable(cache.has_previous_state)
    assert cache.has_previous_state(0) is False  # linear layer, no state yet
    assert cache.has_previous_state(3) is False


def test_linear_layer_state_round_trip():
    """5.x read/write sequence used by Qwen3_5GatedDeltaNet.forward."""
    cache = _cache()
    conv = torch.randn(1, 2, 4, 8)          # (batch, channels, kernel, dim)
    rec = torch.randn(1, 4, 8, 16)          # (batch, heads, k_dim, v_dim)

    assert cache.has_previous_state(0) is False
    cache.update_conv_state(conv, 0)
    cache.update_recurrent_state(rec, 0)

    # reads go through cache.layers[i] directly
    assert torch.equal(cache.layers[0].conv_states, conv)
    assert torch.equal(cache.layers[0].recurrent_states, rec)
    assert cache.layers[0].has_previous_state is True
    assert cache.has_previous_state(0) is True
    # untouched sibling layer unaffected
    assert cache.has_previous_state(1) is False


def test_full_attention_kv_append():
    """Full-attention layers use the standard DynamicCache-style update()."""
    cache = _cache()
    k1 = torch.randn(1, 2, 3, 8)  # (batch, heads, seq, dim)
    v1 = torch.randn(1, 2, 3, 8)
    k2 = torch.randn(1, 2, 1, 8)

    k_all, v_all = cache.update(k1, v1, layer_idx=3)
    assert k_all.shape[2] == 3
    k_all, v_all = cache.update(k2, torch.randn(1, 2, 1, 8), layer_idx=3)
    assert k_all.shape[2] == 4
    assert cache.get_seq_length(3) == 4
    # position bookkeeping used by execute_forward
    assert cache._seq_length == 0  # only set by the executor


def test_clear_resets_all_state():
    cache = _cache()
    cache.update_conv_state(torch.randn(1, 2, 4, 8), 0)
    cache.update(torch.randn(1, 2, 1, 8), torch.randn(1, 2, 1, 8), layer_idx=3)
    cache._seq_length = 9

    cache.clear()

    assert cache.has_previous_state(0) is False
    assert cache.layers[0].conv_states is None
    assert cache.key_cache[3] is None
    assert cache._seq_length == 0
    # layers list fully rebuilt (fresh slots, correct count)
    assert len(cache.layers) == len(LAYER_TYPES)


def test_get_mask_sizes_distinguishes_layer_kinds():
    """Mask builders need real KV sizes for attention layers and a skip
    signal (0, 0) for linear ones."""
    cache = _cache()
    k = torch.randn(1, 2, 5, 8)
    cache.update(k, torch.randn(1, 2, 5, 8), layer_idx=3)

    assert cache.get_mask_sizes(1, 3) == (5, 6)   # full attention: kv, kv+query
    assert cache.get_mask_sizes(1, 0) == (0, 0)   # linear: skip
